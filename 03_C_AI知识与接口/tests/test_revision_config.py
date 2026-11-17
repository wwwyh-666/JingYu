"""MAX_REVISIONS 配置与修订轮数测试。全部离线：模型用 ScriptedModel 脚本化 Mock。"""
import pytest

from app.config import ConfigError, max_revisions_from_env, validate_max_revisions
from app.models import ChatRequest
from app.qa import QAService
from app.repository import Repository
from test_qa_pipeline import (EID, QUESTION, ScriptedModel, TEXT, approved_data,
                              candidate, service, verdict)


def make_service(data, model, tmp_path, max_revisions=None):
    if max_revisions is None:
        return QAService(lambda: Repository(data), model, tmp_path / 'audit')
    return QAService(lambda: Repository(data), model, tmp_path / 'audit',
                     max_revisions=max_revisions)


def ask(data, model, tmp_path, max_revisions=None):
    return make_service(data, model, tmp_path, max_revisions).answer(
        ChatRequest(spot_id='TT', question=QUESTION, object_id='TT_QND'))


# ---------- MAX_REVISIONS=0：任何失败路径都不得触发 revise ----------

def test_zero_first_round_supported_publishes_with_exactly_two_calls(
        approved_data, tmp_path):
    model = ScriptedModel([candidate(), verdict('supports')])
    result = ask(approved_data, model, tmp_path, max_revisions=0)
    assert result.error_code is None and result.check_status == 'passed'
    assert result.confidence_flag == 'supported'
    assert result.verification.status == 'supported'
    assert result.verification.revision_count == 0
    assert [x[0] for x in model.inputs] == ['generate', 'verify']
    assert len(result.metrics.calls) == 2


def test_zero_verification_not_supported_rejects_without_revision(
        approved_data, tmp_path):
    model = ScriptedModel([candidate(), verdict('insufficient_evidence')])
    result = ask(approved_data, model, tmp_path, max_revisions=0)
    assert result.error_code == 'VERIFICATION_NOT_SUPPORTED'
    assert result.verification.status == 'insufficient_evidence'
    assert result.check_status == 'failed'
    assert result.answer != TEXT  # 拒答文案，不发布候选
    # 立即结束：恰 2 次调用（生成+核验），绝不出现 revise
    assert [x[0] for x in model.inputs] == ['generate', 'verify']


def test_zero_invalid_verification_output_stops_without_revision(
        approved_data, tmp_path):
    model = ScriptedModel([candidate(), {'judgments': 'not-a-list'}])
    result = ask(approved_data, model, tmp_path, max_revisions=0)
    assert result.error_code == 'VERIFICATION_OUTPUT_INVALID'
    assert [x[0] for x in model.inputs] == ['generate', 'verify']


def test_zero_program_check_failure_never_calls_verifier_or_revise(
        approved_data, tmp_path):
    model = ScriptedModel([candidate('FORGED')])
    result = ask(approved_data, model, tmp_path, max_revisions=0)
    assert result.error_code == 'PROGRAM_CHECK_FAILED'
    assert result.check_status == 'failed'
    # 程序检查失败不调用核验，也不修订：仅 1 次生成调用
    assert [x[0] for x in model.inputs] == ['generate']


def test_zero_model_error_stops_immediately(approved_data, tmp_path):
    model = ScriptedModel(['MODEL_TIMEOUT'])
    result = ask(approved_data, model, tmp_path, max_revisions=0)
    assert result.error_code == 'MODEL_TIMEOUT'
    assert result.check_status == 'failed' and not result.citations
    # 生成调用失败后立即返回：不核验、不修订
    assert [x[0] for x in model.inputs] == ['generate']


# ---------- MAX_REVISIONS=1：保持原有修订能力 ----------

def test_one_retains_revision_after_failed_first_round(approved_data, tmp_path):
    model = ScriptedModel([candidate('FORGED'), candidate(), verdict('supports')])
    result = ask(approved_data, model, tmp_path, max_revisions=1)
    assert result.error_code is None and result.check_status == 'passed'
    assert [x[0] for x in model.inputs] == ['generate', 'revise', 'verify']
    assert result.verification.revision_count == 1


def test_one_first_round_pass_means_no_extra_revision(approved_data, tmp_path):
    model = ScriptedModel([candidate(), verdict('supports')])
    result = ask(approved_data, model, tmp_path, max_revisions=1)
    assert result.error_code is None
    assert [x[0] for x in model.inputs] == ['generate', 'verify']


def test_unconfigured_env_defaults_to_original_behavior(
        approved_data, tmp_path, monkeypatch):
    monkeypatch.delenv('MAX_REVISIONS', raising=False)
    assert max_revisions_from_env() == 1
    model = ScriptedModel([candidate('FORGED'), candidate(), verdict('supports')])
    result = ask(approved_data, model, tmp_path)  # 不显式传参：走环境缺省
    assert [x[0] for x in model.inputs] == ['generate', 'revise', 'verify']
    assert result.error_code is None


def test_env_zero_is_honored_by_default_construction(
        approved_data, tmp_path, monkeypatch):
    monkeypatch.setenv('MAX_REVISIONS', '0')
    model = ScriptedModel([candidate(), verdict('insufficient_evidence')])
    result = ask(approved_data, model, tmp_path)  # 不显式传参：从环境读取 0
    assert [x[0] for x in model.inputs] == ['generate', 'verify']
    assert result.error_code == 'VERIFICATION_NOT_SUPPORTED'


def test_env_bad_value_fails_service_construction(tmp_path, monkeypatch):
    monkeypatch.setenv('MAX_REVISIONS', 'abc')
    with pytest.raises(ConfigError):
        QAService(lambda: None, None, tmp_path / 'audit')


# ---------- 配置校验：合法范围仅 0/1，非法值明确报错 ----------

@pytest.mark.parametrize('bad', [-1, -7, 2, 3, 100, True, False, '2', 1.0, None])
def test_explicit_invalid_argument_rejected(bad):
    with pytest.raises(ConfigError):
        validate_max_revisions(bad)


@pytest.mark.parametrize('bad', [2, 3, 100, -1])
def test_error_message_states_legal_range(bad):
    with pytest.raises(ConfigError, match='仅允许 0 或 1'):
        validate_max_revisions(bad)


@pytest.mark.parametrize('bad', [True, False, '2', 1.0, None])
def test_error_message_states_type_requirement(bad):
    with pytest.raises(ConfigError, match='必须是整数 0 或 1'):
        validate_max_revisions(bad)


@pytest.mark.parametrize('raw,expected', [
    ('0', 0), ('1', 1), ('000', 0), (' 1 ', 1),
])
def test_env_valid_values_parse(raw, expected):
    assert max_revisions_from_env({'MAX_REVISIONS': raw}) == expected


@pytest.mark.parametrize('raw', ['abc', '-2', '-1', '', '1.5', 'nan', '2', '3', '100', ' 2 '])
def test_env_invalid_values_rejected(raw):
    with pytest.raises(ConfigError):
        max_revisions_from_env({'MAX_REVISIONS': raw})


@pytest.mark.parametrize('raw', ['2', '3', '100'])
def test_env_out_of_range_error_message_states_legal_range(raw):
    with pytest.raises(ConfigError, match='仅允许 0 或 1'):
        max_revisions_from_env({'MAX_REVISIONS': raw})


def test_env_missing_defaults_to_one():
    assert max_revisions_from_env({}) == 1


# ---------- FastAPI lifespan 装配验证：0/1 正常启动，2 启动失败 ----------

@pytest.fixture
def real_app(monkeypatch):
    """用真实 data 目录（只读）构建 create_app，不写任何文件。"""
    from app.main import create_app
    monkeypatch.setenv('MODEL_PROVIDER', 'disabled')
    return create_app


def test_lifespan_env_zero_starts_and_propagates(real_app, monkeypatch):
    from fastapi.testclient import TestClient
    monkeypatch.setenv('MAX_REVISIONS', '0')
    app = real_app()
    with TestClient(app) as client:
        assert app.state.qa.max_revisions == 0
        assert client.get('/health').json()['status'] == 'ok'


def test_lifespan_env_one_starts_and_propagates(real_app, monkeypatch):
    from fastapi.testclient import TestClient
    monkeypatch.setenv('MAX_REVISIONS', '1')
    app = real_app()
    with TestClient(app) as client:
        assert app.state.qa.max_revisions == 1
        assert client.get('/health').json()['status'] == 'ok'


def test_lifespan_env_two_fails_startup(real_app, monkeypatch):
    from fastapi.testclient import TestClient
    monkeypatch.setenv('MAX_REVISIONS', '2')
    app = real_app()
    with pytest.raises(ConfigError, match='仅允许 0 或 1'):
        with TestClient(app):
            pass

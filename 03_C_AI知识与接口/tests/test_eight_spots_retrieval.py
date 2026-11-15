"""八景知识库检索与门禁测试（离线，不调用模型）。

覆盖：每景点两个自然问法命中正确事实、跨景点隔离、待审事实默认拒绝、
object/period过滤、来源接口返回精确白名单证据、Repository多文件加载。
"""
import hashlib

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.model_client import ChatModel, ModelConfig
from app.repository import Repository


@pytest.fixture
def client():
    with TestClient(create_app(model=ChatModel(ModelConfig()))) as c:
        yield c

# (spot_id, query, expected_first_fact_id)
RETRIEVAL_CASES = [
    ('GG', '故宫博物院是哪年成立的？', 'GG_PALACE_001'),
    ('GG', '三大殿是做什么用的？', 'GG_PALACE_002'),
    ('ZGL', '钟鼓楼有多少年历史？', 'ZGL_TOWER_001'),
    ('ZGL', '钟楼有多高？大钟有多重？', 'ZGL_TOWER_002'),
    ('YHY', '颐和园在哪里？', 'YHY_PARK_001'),
    ('YHY', '佛香阁是哪年被烧毁的？', 'YHY_FXF_001'),
    ('JS', '景山公园在哪里？', 'JS_PARK_001'),
    ('JS', '万春亭在哪里？', 'JS_WCT_001'),
    ('GWF', '恭王府住过哪些人？', 'GWF_MANSION_002'),
    ('GWF', '为什么说一座恭王府半部清代史？', 'GWF_MANSION_002'),
    ('YHG', '雍和宫是什么时候改成寺院的？', 'YHG_TEMPLE_001'),
    ('YHG', '木雕三绝指什么？', 'YHG_TEMPLE_002'),
    ('ZYM', '正阳门为什么叫前门？', 'ZYM_GATE_001'),
    ('ZYM', '正阳门城楼有多高？', 'ZYM_GATE_002'),
]


def fact(repo, fact_id):
    return next(f for f in repo.facts if f.fact_id == fact_id)


def test_repository_loads_all_eight_spots():
    repo = Repository()
    assert {s.spot_id for s in repo.spots} == {'TT', 'GG', 'ZGL', 'YHY', 'JS', 'GWF', 'YHG', 'ZYM'}
    assert len(repo.facts) == 18 and len(repo.evidence) == 25 and len(repo.sources) == 16
    counts = {}
    for f in repo.facts:
        counts[f.spot_id] = counts.get(f.spot_id, 0) + 1
    assert counts == {'TT': 5, 'GG': 2, 'ZGL': 2, 'YHY': 2, 'JS': 2, 'GWF': 1, 'YHG': 2, 'ZYM': 2}


@pytest.mark.parametrize('spot_id,query,expected', RETRIEVAL_CASES)
def test_natural_question_hits_expected_fact(spot_id, query, expected):
    repo = Repository()
    found = [f.fact_id for f in repo.search(spot_id, query)]
    assert found[:1] == [expected]
    rows = repo.publishable_evidence(fact(repo, expected))
    assert rows and all(e.usage == 'answer' for e in rows)


@pytest.mark.parametrize('spot_id,question', [(s, q) for s, q, _ in RETRIEVAL_CASES])
def test_chat_endpoint_reachable_for_all_spots_offline(spot_id, question):
    # MODEL_PROVIDER=disabled：不调用模型；验证八景问答端点可达且不把禁用模型伪装成真答案。
    from app.model_client import ChatModel, ModelConfig
    with TestClient(create_app(model=ChatModel(ModelConfig()))) as client:
        r = client.post('/chat', json={'spot_id': spot_id, 'question': question})
    assert r.status_code == 503
    assert r.json()['error_code'] == 'MODEL_NOT_CONFIGURED'
    assert not r.json()['is_mock'] and not r.json()['model_called']


def test_cross_spot_isolation():
    repo = Repository()
    for spot in ('GG', 'YHY', 'JS', 'GWF', 'YHG', 'ZYM'):
        assert repo.search(spot, '祈年殿蓝瓦') == []
        assert repo.search(spot, '钟鼓楼报时') == []
    assert repo.search('TT', '恭王府') == []
    assert repo.search('TT', '佛香阁烧毁') == []
    assert repo.search('ZGL', '钟鼓楼报时')[0].fact_id == 'ZGL_TOWER_001'


def test_unreviewed_tiantan_facts_stay_blocked():
    repo = Repository()
    assert repo.search('TT', '1420年大祀殿') == []
    assert repo.search('TT', '争议年份', include_unreviewed=False) == []


def test_object_and_period_filters():
    repo = Repository()
    assert 'ZYM_GATE_002' in [f.fact_id for f in repo.search('ZYM', '城楼', object_id='ZYM_GATE')]
    assert [f.fact_id for f in repo.search('GG', '三大殿', period='明清·紫禁城建筑格局')] == ['GG_PALACE_002']
    assert repo.search('GG', '三大殿', period='不匹配时期') == []


def test_source_endpoint_returns_exact_whitelisted_evidence(client):
    r = client.get('/sources/SRC_ZYM_WWJ_001')
    assert r.status_code == 200
    body = r.json()
    assert body['source']['review_status'] == 'approved'
    assert [e['evidence_id'] for e in body['evidence']] == [
        'ZYM_GATE_001_E01', 'ZYM_GATE_001_E02', 'ZYM_GATE_002_E01', 'ZYM_GATE_002_E02']


def test_all_evidence_hashes_and_whitelists_consistent():
    repo = Repository()
    sources = {s.source_id: s for s in repo.sources}
    for e in repo.evidence:
        assert e.quote_sha256 == hashlib.sha256(e.quote.encode('utf-8')).hexdigest()
    for s in repo.sources:
        if s.review_status == 'approved':
            for eid in s.approved_evidence_ids:
                row = next(x for x in repo.evidence if x.evidence_id == eid)
                assert row.source_id == s.source_id
                assert repo.evidence_is_publishable(row, fact(repo, row.fact_id))
    # GWF_MANSION_001 暂缓：不存在于正式数据
    assert all(f.fact_id != 'GWF_MANSION_001' for f in repo.facts)

"""Offline model tests. Synthetic approval overrides exist only in temporary copies."""
import copy
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import shutil
from time import perf_counter
from types import SimpleNamespace

import httpx
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.main import create_app
from app.model_client import ChatModel, ModelConfig, ModelError, timestamp
from app.models import CallRecord, ChatRequest
from app.qa import QAService
from app.repository import DATA, Repository


PERIOD='清·乾隆十六年（1751）'
EID='TT_QND_003_E01'
QUESTION='祈年殿的蓝瓦是什么时候改的？'
TEXT='据天坛公园《祈年殿》介绍，1751年，大享殿统一改为蓝瓦，并更名为祈年殿。'


def read(path): return json.loads(path.read_text('utf-8'))
def write(path,value): path.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')


@pytest.fixture
def approved_data(tmp_path):
    target=tmp_path/'synthetic_review_fixture'
    target.mkdir()
    for p in DATA.glob('*.json'): shutil.copy2(p,target/p.name)
    rows=read(target/'facts_TT.json')
    fact=next(f for f in rows if f['fact_id']=='TT_QND_003')
    fact.update(review_status='approved',reviewer='TEST_FIXTURE_ONLY',reviewed_at='2000-01-01',text=TEXT)
    write(target/'facts_TT.json',rows)
    rows=read(target/'sources.json')
    for source in rows:
        if source['source_id'] in fact['source_ids']:
            source.update(review_status='approved',reviewer='TEST_FIXTURE_ONLY',reviewed_at='2000-01-01')
    write(target/'sources.json',rows)
    rows=read(target/'evidence_TT.json')
    for evidence in rows:
        if evidence['usage']!='suspected_typo':
            evidence.update(review_status='approved',reviewer='TEST_FIXTURE_ONLY',reviewed_at='2000-01-01')
    write(target/'evidence_TT.json',rows)
    return target


def candidate(eid=EID,**patch):
    c={'claim_id':'c1','text':TEXT,'fact_id':'TT_QND_003','spot_id':'TT','object_id':'TT_QND',
       'period':PERIOD,'evidence_ids':[eid]}
    c.update(patch)
    return {'claims':[c]}


def verdict(label='supports',eid=EID):
    return {'judgments':[{'claim_id':'c1','verdict':label,'evidence_ids':[eid],
                          'explanation':'离线脚本测试用判断，不是模型实测。'}]}


class ScriptedModel:
    simulated=True
    ready=True
    def __init__(self,outputs):
        self.outputs=list(outputs)
        self.inputs=[]
        self.config=SimpleNamespace(api_key='',provider='scripted_offline',model='scripted_offline')
    def complete(self,phase,system,payload):
        t0=perf_counter()
        self.inputs.append((phase,system,copy.deepcopy(payload)))
        result=self.outputs.pop(0)
        if callable(result): result=result()
        record=CallRecord(phase=phase,started_at=timestamp(),elapsed_ms=round((perf_counter()-t0)*1000,3),
            configured_model='scripted_offline',actual_model='scripted_offline',status='success',usage={})
        if isinstance(result,str):
            record.status='failed';record.error_code=result
            raise ModelError(result,record)
        return result,record


def service(data,model,tmp_path):
    return QAService(lambda:Repository(data),model,tmp_path/'audit')


def run(data,model,tmp_path,**kwargs):
    return service(data,model,tmp_path).answer(ChatRequest(spot_id='TT',question=QUESTION,**kwargs))


def test_fact_approved_source_pending_is_blocked(approved_data,tmp_path):
    rows=read(approved_data/'sources.json')
    source=next(s for s in rows if s['source_id']=='SRC_TT_OFFICIAL_QND_001')
    source.update(review_status='pending_human_review',reviewer=None,reviewed_at=None)
    write(approved_data/'sources.json',rows)
    model=ScriptedModel([])
    result=run(approved_data,model,tmp_path)
    assert result.error_code=='NO_PUBLISHABLE_EVIDENCE' and not result.model_called
    assert not model.inputs and not result.evidence


@pytest.mark.parametrize('status',['pending_human_review','disabled','rejected'])
def test_unusable_evidence_is_filtered(approved_data,status):
    rows=read(approved_data/'evidence_TT.json')
    for row in rows: row.update(review_status=status,reviewer=None,reviewed_at=None)
    write(approved_data/'evidence_TT.json',rows)
    assert Repository(approved_data).search('TT',QUESTION)==[]


@pytest.mark.parametrize('status',['disabled','rejected'])
def test_disabled_or_rejected_source_blocks_fact(approved_data,status):
    rows=read(approved_data/'sources.json')
    rows[0]['review_status']=status
    write(approved_data/'sources.json',rows)
    assert Repository(approved_data).search('TT',QUESTION)==[]


@pytest.mark.parametrize('question',['祈年殿屋顶何时变成蓝的？','祈年殿的蓝色琉璃瓦是哪年改的？','大享殿屋顶什么时候统一成蓝的？'])
def test_lexical_question_variants_find_same_real_evidence(approved_data,question):
    repo=Repository(approved_data)
    found=repo.search('TT',question)
    assert [f.fact_id for f in found]==['TT_QND_003']
    assert EID in {e.evidence_id for e in repo.publishable_evidence(found[0])}


@pytest.mark.parametrize('body,code',[
    ({'spot_id':'TT','question':'量子飞船'},'NO_PUBLISHABLE_EVIDENCE'),
    ({'spot_id':'GG','question':QUESTION},'SCOPE_MISMATCH'),
    ({'spot_id':'TT','question':'故宫的蓝瓦是哪年改的？'},'SCOPE_MISMATCH'),
    ({'spot_id':'TT','question':QUESTION,'object_id':'TT_HQY'},'SCOPE_MISMATCH'),
    ({'spot_id':'TT','question':'蓝瓦','object_id':'TT_OTHER'},'NO_PUBLISHABLE_EVIDENCE'),
    ({'spot_id':'TT','question':QUESTION,'period':'明代'},'NO_PUBLISHABLE_EVIDENCE'),
])
def test_no_evidence_and_scope_mismatches_never_call_model(approved_data,tmp_path,body,code):
    model=ScriptedModel([])
    result=service(approved_data,model,tmp_path).answer(ChatRequest(**body))
    assert result.error_code==code and not result.model_called and not model.inputs


def test_forged_reference_never_reaches_verifier_or_public_answer(approved_data,tmp_path):
    model=ScriptedModel([candidate('FORGED'),candidate('FORGED')])
    result=run(approved_data,model,tmp_path)
    assert result.check_status=='failed' and not result.citations and not result.fact_ids
    assert result.answer!=TEXT and [x[0] for x in model.inputs]==['generate','revise']
    trace=read(next((tmp_path/'audit').glob('qa-*.json')))
    assert trace['attempts'][0]['program_issues']==['EVIDENCE_NOT_RETRIEVED','NO_SUPPORTING_EVIDENCE']


@pytest.mark.parametrize('patch',[{'spot_id':'GG'},{'object_id':'TT_OTHER'},{'period':'明代'},
                                  {'text':'故宫在1751年改蓝瓦。'}])
def test_generated_scope_spoof_is_rejected(approved_data,tmp_path,patch):
    model=ScriptedModel([candidate(**patch),candidate(**patch)])
    result=run(approved_data,model,tmp_path)
    assert result.check_status=='failed' and not result.evidence
    assert all(phase!='verify' for phase,_,_ in model.inputs)


@pytest.mark.parametrize('label',['contradicts','insufficient_evidence'])
def test_not_supported_after_one_revision_is_not_published(approved_data,tmp_path,label):
    model=ScriptedModel([candidate(),verdict(label),candidate(),verdict(label)])
    result=run(approved_data,model,tmp_path)
    assert result.check_status=='failed' and not result.citations and TEXT not in result.answer
    assert result.verification.status==label and result.verification.revision_count==1
    assert [x[0] for x in model.inputs]==['generate','verify','revise','verify']


@pytest.mark.parametrize('phase,outputs',[
    ('generate',['MODEL_TIMEOUT']),('verify',[candidate(),'MODEL_TIMEOUT']),
    ('verify',[candidate(),'MODEL_TRANSPORT_ERROR'])])
def test_failed_model_call_is_not_verification_success(approved_data,tmp_path,phase,outputs):
    model=ScriptedModel(outputs)
    result=run(approved_data,model,tmp_path)
    assert result.check_status=='failed' and result.verification.status=='failed'
    assert not result.citations and not result.evidence and TEXT not in result.answer
    assert result.metrics.calls[-1].phase==phase and result.metrics.calls[-1].status=='failed'


@pytest.mark.parametrize('bad',[{'judgments':[]},verdict(eid='FORGED'),
    {'judgments':verdict()['judgments']*2}])
def test_invalid_verifier_output_is_rejected(approved_data,tmp_path,bad):
    model=ScriptedModel([candidate(),bad,candidate(),bad])
    result=run(approved_data,model,tmp_path)
    assert result.check_status=='failed' and result.error_code=='VERIFICATION_OUTPUT_INVALID'
    assert not result.evidence and result.verification.status=='failed'


def test_one_revision_can_succeed_with_fresh_verification(approved_data,tmp_path):
    model=ScriptedModel([candidate(),verdict('contradicts'),candidate(),verdict()])
    result=run(approved_data,model,tmp_path)
    assert result.check_status=='passed' and result.verification.status=='supported'
    assert result.is_mock is True and result.model_called is True
    assert result.verification.revision_count==1 and result.answer==TEXT
    for phase,_,payload in model.inputs:
        if phase=='verify':
            assert 'revision_feedback' not in payload
            assert 'reasoning_content' not in json.dumps(payload)


def test_passed_answer_and_source_endpoint_have_original_quote(approved_data,tmp_path):
    model=ScriptedModel([candidate(),verdict()])
    app=create_app(approved_data,model,tmp_path/'audit')
    with TestClient(app) as client:
        r=client.post('/chat',json={'spot_id':'TT','question':QUESTION,'request_id':'test-source'})
        body=r.json()
        assert r.status_code==200 and body['check_status']=='passed' and body['is_mock']
        assert body['check_status']!='human_reviewed'
        assert body['citations'][0]['evidence_ids']==[EID]
        original=next(e for e in read(DATA/'evidence_TT.json') if e['evidence_id']==EID)
        assert body['evidence'][0]['quote']==original['quote']
        response=client.get('/sources/'+body['citations'][0]['source_id'])
        assert response.status_code==200
        assert response.json()['evidence'][0]['quote']==original['quote']
    assert all(e['usage']!='suspected_typo' for e in model.inputs[0][2]['evidence'])


def test_config_missing_does_not_fallback_to_mock(approved_data,tmp_path):
    model=ChatModel(ModelConfig())
    result=run(approved_data,model,tmp_path)
    assert result.error_code=='MODEL_NOT_CONFIGURED' and not result.model_called
    assert not result.is_mock and not result.metrics.calls and not result.citations


def test_evidence_disabled_during_model_call_blocks_publication(approved_data,tmp_path):
    def disable_and_return_verdict():
        rows=read(approved_data/'evidence_TT.json')
        rows[0]['review_status']='disabled'
        write(approved_data/'evidence_TT.json',rows)
        return verdict()
    model=ScriptedModel([candidate(),disable_and_return_verdict])
    result=run(approved_data,model,tmp_path)
    assert result.error_code=='EVIDENCE_CHANGED_DURING_REQUEST' and result.check_status=='failed'
    assert not result.evidence and result.answer!=TEXT


def test_invalid_source_url_or_association_not_usable(approved_data):
    rows=read(approved_data/'evidence_TT.json')
    for row in rows: row['url']='https://example.invalid/not-the-registered-source'
    write(approved_data/'evidence_TT.json',rows)
    assert Repository(approved_data).search('TT',QUESTION)==[]


def test_broken_association_returns_traced_failure(approved_data,tmp_path):
    rows=read(approved_data/'facts_TT.json')
    rows[2]['source_ids']=['UNKNOWN_SOURCE']
    write(approved_data/'facts_TT.json',rows)
    result=run(approved_data,ScriptedModel([]),tmp_path)
    assert result.error_code=='KNOWLEDGE_DATA_INVALID' and result.check_status=='failed'
    assert not result.model_called and not result.claims
    trace=read(next((tmp_path/'audit').glob('qa-*.json')))
    assert trace['final_response']['error_code']=='KNOWLEDGE_DATA_INVALID'


def test_quote_tampering_is_rejected(approved_data):
    rows=read(approved_data/'evidence_TT.json');rows[0]['quote']='被改写的原文'
    write(approved_data/'evidence_TT.json',rows)
    with pytest.raises(ValidationError): Repository(approved_data)


def test_http_adapter_independent_requests_actual_usage_no_reasoning(approved_data,tmp_path):
    requests=[]
    def handler(request):
        body=json.loads(request.content);requests.append(body)
        raw=candidate() if len(requests)==1 else verdict()
        return httpx.Response(200,json={'model':'synthetic-provider-model','usage':{'prompt_tokens':123,'completion_tokens':45,'total_tokens':168},
            'choices':[{'finish_reason':'stop','message':{'content':json.dumps(raw,ensure_ascii=False),
                'reasoning_content':'INTERNAL_REASONING_MUST_NOT_BE_REUSED'}}]})
    model=ChatModel(ModelConfig(provider='deepseek',model='configured-test-model',api_key='SYNTHETIC_SECRET',
                                base_url='https://api.example.invalid'),transport=httpx.MockTransport(handler))
    model.simulated=True  # Explicitly label this HTTP mock as offline simulation.
    result=run(approved_data,model,tmp_path)
    assert result.check_status=='passed' and result.is_mock
    assert len(requests)==2 and all(len(r['messages'])==2 for r in requests)
    assert all(r['stream'] is False and r['thinking']=={'type':'disabled'} for r in requests)
    assert 'INTERNAL_REASONING' not in json.dumps(requests[1])
    assert all(c.actual_model=='synthetic-provider-model' and c.usage['total_tokens']==168 for c in result.metrics.calls)
    log=next((tmp_path/'audit').glob('qa-*.json')).read_text('utf-8')
    assert 'SYNTHETIC_SECRET' not in log and 'INTERNAL_REASONING' not in log


@pytest.mark.parametrize('response',[
    httpx.Response(401,text='SYNTHETIC_SECRET provider error body'),
    httpx.Response(200,json={'model':'fake','choices':[{'finish_reason':'length','message':{'content':'{}'}}]}),
    httpx.Response(200,json={'model':'fake','choices':[{'finish_reason':'stop','message':{'content':'   '}}]}),
    httpx.Response(200,json=[]),httpx.Response(200,json={'model':'fake','choices':[]}),
    httpx.Response(200,json={'model':'fake','choices':['invalid-choice']})])
def test_adapter_failures_are_safe_and_never_pass(approved_data,tmp_path,response):
    model=ChatModel(ModelConfig(provider='openai_compatible',model='test',api_key='SYNTHETIC_SECRET',
        base_url='https://api.example.invalid'),transport=httpx.MockTransport(lambda _:response))
    model.simulated=True
    result=run(approved_data,model,tmp_path)
    assert result.check_status=='failed' and not result.citations
    assert 'SYNTHETIC_SECRET' not in next((tmp_path/'audit').glob('qa-*.json')).read_text('utf-8')


def test_formal_release_matches_explicit_approval(tmp_path):
    repo=Repository()
    record=read(DATA/'reviews_TT_QND_003.json')
    assert all(r['suitability']=='是' for r in record['source_assessments'])
    assert all(r['decision']=='支持' for r in record['claim_assessments'])
    assert record['overall_decision']=='通过' and record['reviewer']
    facts=repo.search('TT',QUESTION)
    assert [f.fact_id for f in facts]==['TT_QND_003']
    assert facts[0].text==record['accepted_text']
    assert [e.evidence_id for e in repo.publishable_evidence(facts[0])]==[EID]
    assert record['teacher_review_record'] is None
    model=ChatModel(ModelConfig())
    result=run(DATA,model,tmp_path)
    assert not result.model_called and result.error_code=='MODEL_NOT_CONFIGURED'
    app=create_app(DATA,model,tmp_path/'audit2')
    with TestClient(app) as client:
        r=client.get('/sources/SRC_TT_OFFICIAL_QND_001')
        assert r.status_code==200
        # S1白名单追加004_E02后，来源查询返回两条获批片段。
        assert [e['evidence_id'] for e in r.json()['evidence']]==[EID,'TT_QND_004_E02']


def test_source_approval_is_limited_to_explicit_evidence(approved_data):
    rows=read(approved_data/'sources.json')
    source=next(s for s in rows if s['source_id']=='SRC_TT_OFFICIAL_QND_001')
    source['approved_evidence_ids']=[]
    write(approved_data/'sources.json',rows)
    assert Repository(approved_data).search('TT',QUESTION)==[]


@pytest.mark.parametrize('outputs,status',[
    (['MODEL_TIMEOUT'],504),(['MODEL_TRANSPORT_ERROR'],503),(['MODEL_HTTP_401'],502)])
def test_http_model_failure_status_and_safe_body(approved_data,tmp_path,outputs,status):
    app=create_app(approved_data,ScriptedModel(outputs),tmp_path/'audit')
    with TestClient(app) as client:
        r=client.post('/chat',json={'spot_id':'TT','question':QUESTION})
        assert r.status_code==status
        assert r.json()['check_status']=='failed' and r.json()['citations']==[]


def test_http_missing_model_config(approved_data,tmp_path):
    app=create_app(approved_data,ChatModel(ModelConfig()),tmp_path/'audit')
    with TestClient(app) as client:
        r=client.post('/chat',json={'spot_id':'TT','question':QUESTION})
        assert r.status_code==503 and not r.json()['model_called'] and not r.json()['is_mock']


def test_bad_numeric_configuration_fails_closed_without_crashing(monkeypatch):
    monkeypatch.setenv('MODEL_TIMEOUT_SECONDS','not-a-number')
    cfg=ModelConfig.from_env()
    assert cfg.missing() and not ChatModel(cfg).ready

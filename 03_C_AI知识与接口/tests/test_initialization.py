import copy,json,os,socket,subprocess,sys,time
from pathlib import Path
import httpx,pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from app.main import create_app
from app.model_client import ChatModel, ModelConfig
from app.models import ChatResponse,DraftResponse,Fact
from app.repository import Repository,DATA
ROOT=DATA.parent
@pytest.fixture
def client():
    # Always disable the real adapter in offline tests, regardless of local .env.
    with TestClient(create_app(model=ChatModel(ModelConfig()))) as c: yield c

def test_health_and_spots(client):
    h=client.get('/health')
    assert h.status_code==200 and h.json()['model_called'] is False
    r=client.get('/spots')
    assert r.status_code==200
    assert {x['spot_id'] for x in r.json()['items']}=={'TT','GG','ZGL','YHY','JS','GWF','YHG','ZYM'}
    assert all(x['geo'] is None and x['map_position'] is None for x in r.json()['items'])

def test_chat_does_not_disguise_disabled_model_as_real_answer(client):
    body={'spot_id':'TT','question':'祈年殿的蓝瓦是什么时候改的？','turn_id':1}
    r=client.post('/chat',json=body)
    v=ChatResponse.model_validate(r.json())
    assert r.status_code==503 and not v.is_mock and not v.model_called
    assert v.confidence_flag=='insufficient_evidence' and not v.citations and not v.fact_ids
    assert v.error_code=='MODEL_NOT_CONFIGURED'

@pytest.mark.parametrize('payload',[{'spot_id':'BAD','question':'问题'},
 {'spot_id':'TT','question':'  '},{'spot_id':'TT','question':'问题','turn_id':0},
 {'spot_id':'TT','question':'问题','unknown':True}])
def test_chat_rejects_invalid(client,payload):
    assert client.post('/chat',json=payload).status_code==422

def test_draft_is_reserved(client):
    r=client.post('/journal/draft',json={'spot_id':'TT','prompt':'礼制圆形'})
    assert r.status_code==501 and r.json()['detail']['code']=='NOT_IMPLEMENTED'
    assert client.post('/journal/draft',json={'spot_id':'TT'}).status_code==422

def test_real_records_and_review_gate():
    repo=Repository()
    found=repo.search('TT','蓝瓦',include_unreviewed=True)
    assert [x.fact_id for x in found]==['TT_QND_003']
    assert all(x in repo.facts and set(x.source_ids)<={s.source_id for s in repo.sources} for x in found)
    assert [f.fact_id for f in repo.search('TT','蓝瓦')]==['TT_QND_003']
    assert repo.search('TT','1420')==[]
    assert repo.search('GG','蓝瓦',include_unreviewed=True)==[]
    assert repo.search('TT','蓝瓦',period='明·嘉靖二十四年（1545）',include_unreviewed=True)==[]
    assert repo.search('TT','蓝瓦',object_id='TT_OTHER',include_unreviewed=True)==[]
    assert repo.search('TT','量子飞船',include_unreviewed=True)==[]
    assert repo.search('TT',' ',include_unreviewed=True)==[]

def test_approved_requires_review():
    row=Repository().facts[0].model_dump();row['review_status']='approved'
    with pytest.raises(ValidationError): Fact.model_validate(row)

@pytest.mark.parametrize('damage',['unknown_source','duplicate_fact','missing_spot'])
def test_corrupt_data_rejected(tmp_path,damage):
    for p in DATA.glob('*.json'): (tmp_path/p.name).write_bytes(p.read_bytes())
    if damage=='missing_spot':
        path=tmp_path/'spots.json';rows=json.loads(path.read_text('utf-8'));rows.pop()
    else:
        path=tmp_path/'facts_TT.json';rows=json.loads(path.read_text('utf-8'))
        if damage=='unknown_source': rows[0]['source_ids']=['MISSING']
        else: rows.append(copy.deepcopy(rows[0]))
    path.write_text(json.dumps(rows,ensure_ascii=False),encoding='utf-8')
    with pytest.raises(ValueError): Repository(tmp_path)

def test_examples_match_contract(client):
    fixtures=ROOT/'examples'
    assert client.get('/spots').json()==json.loads((fixtures/'spots.response.mock.json').read_text('utf-8'))
    req=json.loads((fixtures/'chat.request.mock.json').read_text('utf-8'))
    # Keep the legacy 0.1 mock as a typed UI fixture; /chat is now the real pipeline.
    mock=ChatResponse.model_validate_json((fixtures/'chat.response.mock.json').read_text('utf-8'))
    assert mock.is_mock and not mock.model_called
    live=ChatResponse.model_validate(client.post('/chat',json=req).json())
    assert not live.is_mock and live.error_code=='MODEL_NOT_CONFIGURED'
    DraftResponse.model_validate_json((fixtures/'journal_draft.response.mock.json').read_text('utf-8'))

def test_uvicorn_starts_from_specified_directory():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
    log=ROOT/'logs/test_server.log'
    with log.open('w',encoding='utf-8') as out:
        proc=subprocess.Popen([sys.executable,'-m','uvicorn','app.main:app','--host','127.0.0.1','--port',str(port)],
                              cwd=ROOT,stdout=out,stderr=out)
        try:
            with httpx.Client(trust_env=False) as c:
                for _ in range(100):
                    if proc.poll() is not None: pytest.fail('server exited: '+log.read_text('utf-8'))
                    try:
                        r=c.get(f'http://127.0.0.1:{port}/health',timeout=1)
                        if r.status_code==200: break
                    except httpx.TransportError: pass
                    time.sleep(.1)
                else: pytest.fail('server startup timeout')
                assert r.json()['spot_count']==8
                assert c.get(f'http://127.0.0.1:{port}/spots').status_code==200
        finally:
            proc.terminate()
            try: proc.wait(timeout=5)
            except subprocess.TimeoutExpired: proc.kill();proc.wait()

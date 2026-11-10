"""Exercise the existing local /chat API. No mock model, no data approval override."""
import argparse
import json
from pathlib import Path
import sys
from time import perf_counter
from urllib.parse import urlsplit
from uuid import UUID, uuid4

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import httpx
from dotenv import load_dotenv
from app.model_client import ModelConfig, timestamp

CASES=[
    ('normal','祈年殿的蓝瓦是什么时候改的？'),
    ('paraphrase','祈年殿的屋顶是哪一年统一改成蓝色的？'),
    ('uncovered','祈年殿每根柱子的准确木材产地分别是哪儿？'),
    ('false_premise','天坛所有建筑是不是都在1751年改成了蓝瓦？'),
]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-url',default='http://127.0.0.1:8000')
    parser.add_argument('--first-only',action='store_true',help='Only test the first question.')
    args=parser.parse_args()
    address=urlsplit(args.base_url)
    if (address.scheme not in {'http','https'} or address.hostname not in {'127.0.0.1','localhost','::1'}
            or address.username or address.password or address.query or address.fragment):
        parser.error('Use the local backend address without credentials or URL parameters.')
    load_dotenv(ROOT/'.env')
    config=ModelConfig.from_env()
    run_id=str(uuid4())
    output=ROOT/'logs/acceptance'/(timestamp()[:10].replace('-','')+'-'+run_id+'.json')
    output.parent.mkdir(parents=True,exist_ok=True)
    record={'run_id':run_id,'started_at':timestamp(),'execution_mode':'formal_local_http',
        'configured_model':config.model or None,'provider':config.provider,
        'configuration_missing':config.missing(),'cases':[],
        'real_model_run_complete':False,'real_model_acceptance_complete':False,'cost_estimate':None,
        'note':'无模拟、无临时批准。耗时与用量只取实际运行；模型核验不是绝对正确性保证。'}

    def save():
        text=json.dumps(record,ensure_ascii=False,indent=2)
        if config.api_key: text=text.replace(config.api_key,'[REDACTED]')
        output.write_text(text+'\n',encoding='utf-8')

    try:
        with httpx.Client(base_url=args.base_url.rstrip('/'),trust_env=False,timeout=150) as client:
            health=client.get('/health')
            health.raise_for_status()
            record['health']=health.json()
            if record['health'].get('model_provider')!='deepseek':
                record['error_code']='BACKEND_PROVIDER_NOT_DEEPSEEK_RESTART_REQUIRED'
                save()
                print('STOP: restart the local backend with the DeepSeek configuration.')
                print('Record: '+str(output))
                return 2
            cases=CASES[:1] if args.first_only else CASES
            for label,question in cases:
                request={'spot_id':'TT','object_id':'TT_QND','question':question,
                         'request_id':run_id+'-'+label}
                start=perf_counter()
                response=client.post('/chat',json=request)
                item={'case':label,'request':request,'http_status':response.status_code,
                      'http_elapsed_ms':round((perf_counter()-start)*1000,3)}
                try:
                    body=response.json()
                except ValueError:
                    item['error_code']='BACKEND_NON_JSON_RESPONSE'
                    record['cases'].append(item);save()
                    break
                item['response']=body
                answer_id=body.get('answer_id','')
                # Only read a trace whose identifier is a genuine UUID.
                try:
                    trace_id=str(UUID(answer_id))
                except (ValueError,TypeError,AttributeError):
                    trace_id=None
                if trace_id:
                    trace=ROOT/'logs/qa'/('qa-'+trace_id+'.json')
                    if trace.exists(): item['pipeline_trace']=json.loads(trace.read_text('utf-8'))
                success=(response.status_code==200 and body.get('check_status')=='passed'
                    and body.get('verification',{}).get('status')=='supported'
                    and body.get('is_mock') is False and body.get('model_called') is True
                    and bool(body.get('claims')) and bool(body.get('evidence'))
                    and len(body.get('metrics',{}).get('calls',[]))>=2)
                if success:
                    source_queries=[]
                    for citation in body['citations']:
                        source_response=client.get('/sources/'+citation['source_id'])
                        source_queries.append({'source_id':citation['source_id'],
                            'status':source_response.status_code,'body':source_response.json()})
                    item['source_queries']=source_queries
                    success=bool(source_queries) and all(q['status']==200 for q in source_queries)
                    if success:
                        available={e['evidence_id']:e for q in source_queries for e in q['body']['evidence']}
                        success=all(e['evidence_id'] in available
                            and e['quote']==available[e['evidence_id']]['quote']
                            and e['quote_sha256']==available[e['evidence_id']]['quote_sha256']
                            for e in body['evidence'])
                if label=='uncovered':
                    item['assessment']='expected_evidence_refusal' if (
                        body.get('error_code')=='NO_PUBLISHABLE_EVIDENCE' and not body.get('model_called')
                        and not body.get('claims')) else 'requires_inspection'
                elif label=='false_premise':
                    item['assessment']='requires_human_content_check' if success else (
                        'candidate_not_published' if body.get('error_code') in {
                            'NO_PUBLISHABLE_EVIDENCE','PROGRAM_CHECK_FAILED','VERIFICATION_NOT_SUPPORTED'}
                        and not body.get('claims') else 'failed')
                else:
                    item['assessment']='real_pipeline_supported' if success else 'not_completed'
                record['cases'].append(item);save()
                print(label+': '+item['assessment']+'; '+str(body.get('error_code')))
                if label=='normal' and not success:
                    record['remaining_cases']='not_run_because_normal_question_not_passed'
                    save()
                    break
            record['real_model_run_complete']=(len(record['cases'])==4
                and record['cases'][0]['assessment']=='real_pipeline_supported'
                and record['cases'][1]['assessment']=='real_pipeline_supported'
                and record['cases'][2]['assessment']=='expected_evidence_refusal'
                and record['cases'][3]['assessment']=='requires_human_content_check')
            # A completed run still requires human inspection of the false-premise answer.
            record['human_content_acceptance_complete']=False
            save()
    except (httpx.HTTPError,OSError):
        record['error_code']='LOCAL_BACKEND_OR_RECORD_UNAVAILABLE'
        save()
        print('STOP: check the local service and record directory. No provider error body is printed.')
    print('Record: '+str(output))
    first_ok=(record['cases'] and record['cases'][0].get('assessment')=='real_pipeline_supported')
    return 0 if record['real_model_run_complete'] or (args.first_only and first_ok) else 2


if __name__=='__main__':
    raise SystemExit(main())

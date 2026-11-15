import hashlib,json
from pathlib import Path
import pytest
from pydantic import ValidationError
from app.models import Fact
from app.repository import Repository,DATA
ROOT=DATA.parent

def test_stable_fact_ids_and_scoped_review():
    # 八景入库后本文件只校验天坛范围；全局计数与八景断言见test_eight_spots_retrieval.py。
    facts=[f for f in Repository().facts if f.spot_id=='TT']
    assert [f.fact_id for f in facts]==[f'TT_QND_{n:03}' for n in range(1,6)]
    assert all(f.spot_id=='TT' and f.object_id=='TT_QND' for f in facts)
    approved_dates={'TT_QND_003':'2026-11-10','TT_QND_004':'2026-11-15','TT_QND_005':'2026-11-13'}
    assert {f.fact_id for f in facts if f.review_status=='approved'}==set(approved_dates)
    assert all(f.review_status=='pending_human_review' and f.reviewer is None and f.reviewed_at is None
               for f in facts if f.fact_id not in approved_dates)
    repo=Repository()
    for fact_id,date in approved_dates.items():
        approved=next(f for f in facts if f.fact_id==fact_id)
        record=json.loads((DATA/f'reviews_{fact_id}.json').read_text('utf-8'))
        assert approved.review_status=='approved' and approved.reviewer==record['reviewer']
        assert approved.reviewer and approved.reviewed_at==record['reviewed_at']==date
        assert approved.text==record['accepted_text']
        assert record['overall_decision']=='通过' and record['release_status']=='approved'
        expected_evidence=['TT_QND_004_E01','TT_QND_004_E02'] if fact_id=='TT_QND_004' else [f'{fact_id}_E01']
        assert [e.evidence_id for e in repo.publishable_evidence(approved)]==expected_evidence
    assert next(f for f in facts if f.fact_id=='TT_QND_002').dispute_status=='disputed'

def test_sources_and_located_evidence():
    repo=Repository();sources={s.source_id:s for s in repo.sources}
    required={'SRC_TT_OFFICIAL_HISTORY_001','SRC_TT_BJ_EXPERT_001','SRC_TT_BJWW_STUDY_001','SRC_TT_PARKS_QND_001'}
    assert required <= sources.keys()
    # S2(文物局)按2026-11-15预检方案移出004事实关联并保持待审，不再是任何正式事实的关联来源。
    fact_linked_sources=required-{'SRC_TT_BJWW_STUDY_001'}
    assert fact_linked_sources <= {sid for f in repo.facts for sid in f.source_ids}
    for f in repo.facts:
        assert set(f.source_ids)=={e.source_id for e in f.source_evidence}
        assert all(e.source_id in sources and e.locator and e.supports for e in f.source_evidence)
        # 2026-11-15基线更新：颐和园官网来源为http://，允许http与https官方页面。
        assert all(str(sources[e.source_id].url).startswith(('https://','http://')) for e in f.source_evidence)
    tt_facts=[f for f in repo.facts if f.spot_id=='TT']
    assert tt_facts[-1].statement_type=='direct_source_paraphrase'
    assert next(f for f in repo.facts if f.fact_id=='TT_QND_003').statement_type=='direct_source_paraphrase'
    assert all(f.statement_type=='multi_source_synthesis' for f in repo.facts if f.fact_id in {'TT_QND_001','TT_QND_002','TT_QND_004'})

@pytest.mark.parametrize('query,expected',[('1420','TT_QND_001'),('1538','TT_QND_002'),('1540','TT_QND_002'),('1545','TT_QND_002'),('蓝瓦','TT_QND_003'),('祈谷','TT_QND_004'),('1889','TT_QND_005'),('1890','TT_QND_005'),('1896','TT_QND_005')])
def test_retrieval_and_exact_period_filter(query,expected):
    repo=Repository();row=next(f for f in repo.facts if f.fact_id==expected)
    assert [f.fact_id for f in repo.search('TT',query,period=row.period,include_unreviewed=True)]==[expected]
    assert repo.search('TT',query,period='不匹配时期',include_unreviewed=True)==[]
    assert repo.search('GG',query,include_unreviewed=True)==[]
    assert repo.search('TT',query,object_id='TT_OTHER',include_unreviewed=True)==[]
    # Keyword eligibility is distinct from a year being written in the source quote.
    assert [f.fact_id for f in repo.search('TT',query)]==([expected] if expected in {'TT_QND_003','TT_QND_004','TT_QND_005'} else [])

def test_forged_or_missing_evidence_rejected():
    row=Repository().facts[0].model_dump()
    row['source_evidence'][0]['source_id']='FORGED'
    with pytest.raises(ValidationError): Fact.model_validate(row)
    row=Repository().facts[0].model_dump();row['source_evidence']=[]
    with pytest.raises(ValidationError): Fact.model_validate(row)

def test_other_data_unchanged():
    # 2026-11-15八景入库后重置基线：快照现记录八景13条批准事实入库后的文件指纹。
    before=json.loads((ROOT/'logs/TT_revision_unchanged_before.json').read_text('utf-8'))
    assert before
    for rel,digest in before.items():
        assert hashlib.sha256((ROOT/rel).read_bytes()).hexdigest()==digest,rel

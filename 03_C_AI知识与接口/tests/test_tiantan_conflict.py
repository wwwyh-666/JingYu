import json
from app.repository import Repository, DATA

def test_conflicting_years_returned_together_for_each_query():
    repo=Repository()
    for query in ['1542','1545','1538','1541']:
        matches=repo.retrieve_with_claims('TT',query,include_unreviewed=True)
        entry=next(x for x in matches if x['fact']['fact_id']=='TT_QND_002')
        assert entry['fact']['dispute_status']=='disputed'
        groups={g['event_id']:g for g in entry['events']}
        assert {c['year'] for c in groups['TT_EVENT_ORDER']['claims']}=={1538,1540,1541}
        assert {c['year'] for c in groups['TT_EVENT_COMPLETE']['claims']}=={1542,1545}
        assert all(g['selected_year'] is None for g in groups.values())
        assert all(c['url'] and c['locator'] for g in groups.values() for c in g['claims'])
    assert repo.retrieve_with_claims('TT','1542')==[]
    assert repo.retrieve_with_claims('GG','1542',include_unreviewed=True)==[]

def test_claim_integrity_and_review_status():
    repo=Repository(); claims=json.loads((DATA/'TT_source_claims.json').read_text('utf-8'));events=json.loads((DATA/'TT_events.json').read_text('utf-8'))
    assert len({c['claim_id'] for c in claims})==len(claims)
    assert {c['source_id'] for c in claims}<={s.source_id for s in repo.sources}
    assert {c['event_id'] for c in claims}<={e['event_id'] for e in events}
    assert all(c['review_status']=='pending_human_review' for c in claims)
    assert all(f.review_status=='pending_human_review' and f.reviewer is None and f.reviewed_at is None for f in repo.facts)

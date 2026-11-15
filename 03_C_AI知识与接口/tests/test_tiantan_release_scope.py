"""Approved-data regressions. Mutations exist only in pytest temporary copies.

These checks protect evidence permissions and stored wording; they do not prove
that a future live model will detect every unsupported semantic assertion.
"""
import hashlib
import json
import shutil

import pytest
from pydantic import ValidationError

from app.models import Evidence, Fact, Source
from app.repository import DATA, Repository


QND = 'SRC_TT_OFFICIAL_QND_001'
HISTORY = 'SRC_TT_OFFICIAL_HISTORY_001'
PARKS = 'SRC_TT_PARKS_QND_001'
APPROVED = {'TT_QND_003': QND, 'TT_QND_005': HISTORY}
EIGHT_SPOT_SOURCES = {
    'SRC_GG_PANO_001', 'SRC_GG_BUILDINGS_001', 'SRC_ZGL_BJGOV_001',
    'SRC_YHY_GYGL_001', 'SRC_YHY_SUMMER_001', 'SRC_JS_BJGOV_001',
    'SRC_JS_GYGL_001', 'SRC_GWF_PGM_001', 'SRC_YHG_OFFICIAL_001', 'SRC_ZYM_WWJ_001',
}
TEXT_005 = ('据天坛公园“大事记”记载，1889年（清光绪十五年），祈年殿毁于雷火，'
            '次年重建，直至光绪二十二年（1896年）毕工。')
QUOTE_005 = ('清•光绪十五年\n1889年\n'
             '祈年殿毁于雷火，次年重建．直至光绪二十二年（1896年）毕工。')


def read(name):
    return json.loads((DATA / name).read_text(encoding='utf-8'))


def fact(repo, fact_id='TT_QND_005'):
    return next(f for f in repo.facts if f.fact_id == fact_id)


def evidence(repo, fact_id='TT_QND_005'):
    return next(e for e in repo.evidence if e.evidence_id == fact_id + '_E01')


@pytest.fixture
def editable_repo(tmp_path):
    # Never mutate the formal data or silently grant approvals through a fixture.
    target = tmp_path / 'release_scope_data'
    target.mkdir()
    for path in DATA.glob('*.json'):
        shutil.copy2(path, target / path.name)
    return Repository(target)


EIGHT_SPOT_EVIDENCE = {
    'GG_PALACE_001_E01', 'GG_PALACE_002_E01',
    'ZGL_TOWER_001_E01', 'ZGL_TOWER_002_E01',
    'YHY_PARK_001_E01', 'YHY_FXF_001_E01',
    'JS_PARK_001_E01', 'JS_WCT_001_E01',
    'GWF_MANSION_002_E01', 'GWF_MANSION_002_E02',
    'YHG_TEMPLE_001_E01', 'YHG_TEMPLE_002_E01',
    'ZYM_GATE_001_E01', 'ZYM_GATE_001_E02', 'ZYM_GATE_002_E01', 'ZYM_GATE_002_E02',
}


def test_exact_formal_evidence_inventory_and_hashes():
    repo = Repository()
    tt_expected = {f'TT_QND_003_E{i:02}' for i in range(1, 7)} | {'TT_QND_005_E01', 'TT_QND_004_E01', 'TT_QND_004_E02'}
    tt_rows = [e for e in repo.evidence if e.spot_id == 'TT']
    assert len(tt_rows) == 9
    assert {e.evidence_id for e in tt_rows} == tt_expected
    assert len(repo.evidence) == 25
    assert {e.evidence_id for e in repo.evidence} == tt_expected | EIGHT_SPOT_EVIDENCE
    approved = {'TT_QND_003_E01', 'TT_QND_005_E01', 'TT_QND_004_E01', 'TT_QND_004_E02'} | EIGHT_SPOT_EVIDENCE
    assert {e.evidence_id for e in repo.evidence if e.review_status == 'approved'} == approved
    for e in repo.evidence:
        assert e.quote_sha256 == hashlib.sha256(e.quote.encode('utf-8')).hexdigest()
        if e.evidence_id in approved:
            assert e.reviewer and e.reviewed_at
        else:
            assert e.review_status == 'pending_human_review'
            assert e.reviewer is None and e.reviewed_at is None


def test_formal_references_and_source_whitelists_are_exact():
    repo = Repository()
    sources = {s.source_id: s for s in repo.sources}
    facts = {f.fact_id: f for f in repo.facts}
    assert {s.source_id for s in repo.sources if s.review_status == 'approved'} == {QND, HISTORY, PARKS} | EIGHT_SPOT_SOURCES
    assert sources[QND].approved_evidence_ids == ['TT_QND_003_E01', 'TT_QND_004_E02']
    assert sources[HISTORY].approved_evidence_ids == ['TT_QND_005_E01']
    assert sources[PARKS].approved_evidence_ids == ['TT_QND_004_E01']
    for s in repo.sources:
        if s.source_id.startswith('SRC_TT_') and s.source_id not in {QND, HISTORY, PARKS}:
            assert s.review_status == 'pending_human_review'
            assert not s.approved_evidence_ids
        for eid in s.approved_evidence_ids:
            e = next(e for e in repo.evidence if e.evidence_id == eid)
            assert e.source_id == s.source_id
            assert repo.evidence_is_publishable(e, facts[e.fact_id])
    for f in repo.facts:
        assert set(f.source_ids) <= sources.keys()
        assert set(f.source_ids) == {row.source_id for row in f.source_evidence}
    for e in repo.evidence:
        f = facts[e.fact_id]
        assert e.spot_id == f.spot_id and e.object_id == f.object_id and e.period == f.period
        assert str(e.url) == str(sources[e.source_id].url)
    # Pending historical E02-E06 are not all declared as current approved fact sources.
    # Require the full current Fact/source association specifically for released rows.
    for f in repo.facts:
        for e in repo.publishable_evidence(f):
            assert e.source_id in f.source_ids


@pytest.mark.parametrize('fact_id,source_id', sorted(APPROVED.items()))
def test_approved_fact_uses_only_its_approved_e01(fact_id, source_id):
    repo = Repository()
    f = fact(repo, fact_id)
    e = evidence(repo, fact_id)
    assert f.source_ids == [source_id]
    assert e.source_id == source_id
    assert repo.evidence_is_publishable(e, f)
    assert [row.evidence_id for row in repo.publishable_evidence(f)] == [fact_id + '_E01']


def test_004_publishes_exactly_its_two_approved_evidences():
    repo = Repository()
    f = fact(repo, 'TT_QND_004')
    record = read('reviews_TT_QND_004.json')
    assert f.source_ids == [PARKS, QND]
    assert f.review_status == 'approved'
    assert f.reviewer == '王宇涵' and f.reviewed_at == '2026-11-15' == record['reviewed_at']
    assert f.text == record['accepted_text']
    assert f.period == '清代·孟春（正月）祈谷礼'
    ids = [row.evidence_id for row in repo.publishable_evidence(f)]
    assert ids == ['TT_QND_004_E01', 'TT_QND_004_E02']
    assert 'SRC_TT_BJWW_STUDY_001' not in f.source_ids
    for row in repo.evidence:
        if row.evidence_id in ids:
            assert row.reviewer == record['reviewer'] and row.reviewed_at == record['reviewed_at']
            assert row.period == f.period
            assert repo.evidence_is_publishable(row, f)


@pytest.mark.parametrize('field,value', [
    ('spot_id', 'GG'), ('object_id', 'TT_OTHER'), ('period', '明代'),
    ('fact_id', 'TT_QND_003'), ('url', 'https://example.invalid/source'),
])
def test_004_evidence_scope_mismatch_is_blocked(editable_repo, field, value):
    repo = editable_repo
    e01 = next(e for e in repo.evidence if e.evidence_id == 'TT_QND_004_E01')
    data = e01.model_dump(mode='json')
    data[field] = value
    mismatched = Evidence.model_validate(data)
    assert not repo.evidence_is_publishable(mismatched, fact(repo, 'TT_QND_004'))


def test_removing_004_whitelist_entry_blocks_that_evidence(editable_repo):
    repo = editable_repo
    source = next(s for s in repo.sources if s.source_id == PARKS)
    source.approved_evidence_ids = []
    # PARKS 白名单移除只拦截 S3 来源的 E01；S1 来源的 E02 仍按自身授权可发布。
    assert [row.evidence_id for row in repo.publishable_evidence(fact(repo, 'TT_QND_004'))] == ['TT_QND_004_E02']


@pytest.mark.parametrize('number', range(2, 7))
def test_003_other_fragments_still_cannot_be_published(number):
    repo = Repository()
    e = next(e for e in repo.evidence if e.evidence_id == f'TT_QND_003_E{number:02}')
    assert e.review_status == 'pending_human_review'
    assert not repo.evidence_is_publishable(e, fact(repo, 'TT_QND_003'))


@pytest.mark.parametrize('fact_id', ['TT_QND_001', 'TT_QND_002'])
def test_unreviewed_facts_are_not_released(fact_id):
    repo = Repository()
    f = fact(repo, fact_id)
    assert f.review_status == 'pending_human_review'
    assert f.reviewer is None and f.reviewed_at is None
    assert not repo.publishable_evidence(f)
    for keyword in f.keywords:
        assert fact_id not in {row.fact_id for row in repo.search('TT', keyword)}
    if fact_id == 'TT_QND_002':
        assert f.dispute_status == 'disputed'
        assert repo.retrieve_with_claims('TT', '1542') == []


def test_unlisted_005_evidence_is_blocked_even_when_other_fields_are_approved(editable_repo):
    repo = editable_repo
    original = evidence(repo)
    data = original.model_dump(mode='json')
    data['evidence_id'] = 'TEST_ONLY_UNAUTHORIZED'
    unlisted = Evidence.model_validate(data)
    repo.evidence.append(unlisted)
    assert unlisted.review_status == 'approved'  # Isolate the whitelist, not pending status.
    assert not repo.evidence_is_publishable(unlisted, fact(repo))
    assert [row.evidence_id for row in repo.publishable_evidence(fact(repo))] == ['TT_QND_005_E01']


def test_source_review_without_whitelist_does_not_authorize_evidence(editable_repo):
    repo = editable_repo
    source = next(s for s in repo.sources if s.source_id == HISTORY)
    assert source.review_status == 'approved'
    source.approved_evidence_ids = []
    assert not repo.evidence_is_publishable(evidence(repo), fact(repo))
    assert not repo.publishable_evidence(fact(repo))
    assert repo.search('TT', '1889') == []


@pytest.mark.parametrize('field,value', [
    ('spot_id', 'GG'), ('object_id', 'TT_OTHER'), ('period', '明代'),
    ('fact_id', 'TT_QND_003'), ('source_id', QND), ('url', 'https://example.invalid/source'),
])
def test_005_evidence_scope_mismatch_is_blocked(editable_repo, field, value):
    repo = editable_repo
    data = evidence(repo).model_dump(mode='json')
    data[field] = value
    mismatched = Evidence.model_validate(data)
    # Keep the real whitelisted ID so the scope condition, not ID existence, must fail.
    assert mismatched.evidence_id == 'TT_QND_005_E01'
    assert not repo.evidence_is_publishable(mismatched, fact(repo))


@pytest.mark.parametrize('kwargs', [
    {'spot_id': 'GG'}, {'object_id': 'TT_OTHER'}, {'period': '明代'},
])
def test_005_retrieval_respects_requested_scope(kwargs):
    args = {'spot_id': 'TT', 'query': '1889', **kwargs}
    assert Repository().search(**args) == []


@pytest.mark.parametrize('target', ['fact', 'source', 'evidence'])
@pytest.mark.parametrize('status', ['pending_human_review', 'rejected', 'disabled'])
def test_nonapproved_release_component_blocks_005(editable_repo, target, status):
    repo = editable_repo
    component = {'fact': fact(repo), 'source': next(s for s in repo.sources if s.source_id == HISTORY),
                 'evidence': evidence(repo)}[target]
    component.review_status = status
    assert not repo.evidence_is_publishable(evidence(repo), fact(repo))
    assert not repo.publishable_evidence(fact(repo))
    assert repo.search('TT', '1889') == []


@pytest.mark.parametrize('target,model', [('fact', Fact), ('source', Source), ('evidence', Evidence)])
@pytest.mark.parametrize('field', ['reviewer', 'reviewed_at'])
def test_approved_components_require_audit_identity(target, model, field):
    repo = Repository()
    original = {'fact': fact(repo), 'source': next(s for s in repo.sources if s.source_id == HISTORY),
                'evidence': evidence(repo)}[target]
    data = original.model_dump(mode='json')
    data[field] = None
    with pytest.raises(ValidationError):
        model.model_validate(data)


def test_dispute_still_blocks_an_otherwise_approved_test_fact(editable_repo):
    repo = editable_repo
    f = fact(repo)
    assert repo.evidence_is_publishable(evidence(repo), f)
    f.dispute_status = 'disputed'
    assert not repo.evidence_is_publishable(evidence(repo), f)
    assert not repo.publishable_evidence(f)
    assert repo.search('TT', '1889') == []


def test_005_time_wording_and_auxiliary_conversion_stay_separate():
    repo = Repository()
    f, e = fact(repo), evidence(repo)
    record = read('reviews_TT_QND_005.json')
    identity = read('reviews_TT_QND_003.json')
    assert f.text == record['accepted_text'] == TEXT_005
    assert e.quote == QUOTE_005
    assert e.quote_sha256 == '01a5288763f93532ba2b2df66a299a54213df80fef9b003181afe5a5dd41cd9a'
    assert '次年重建' in e.quote and '次年重建' in f.text
    for text in [f.text, e.quote]:
        assert '1890' not in text
        assert not any(term in text for term in ['开始重建', '开工', '动工'])
    assert '1889年' in e.quote and '（1896年）毕工。' in e.quote
    assert [row.fact_id for row in repo.search('TT', '1890')] == ['TT_QND_005']
    conversion = record['time_conversion']
    assert conversion['accepted_for_auxiliary_explanation'] is True
    assert conversion['base_year'] == 1889 and conversion['relative_time'] == '次年'
    assert conversion['derived_year'] == conversion['base_year'] + 1 == 1890
    assert conversion['direct_source_year'] is False and conversion['included_in_accepted_text'] is False
    assert record['reviewer'] == identity['reviewer'] and record['reviewer_role'] == identity['reviewer_role']
    assert f.reviewer == e.reviewer == record['reviewer']
    assert f.reviewed_at == e.reviewed_at == record['reviewed_at'] == '2026-11-13'
    assert record['approval_scope'] == {
        'fact_ids': ['TT_QND_005'], 'source_id': HISTORY, 'evidence_ids': ['TT_QND_005_E01'],
        'purpose': '仅支持accepted_text所列1889年祈年殿毁于雷火、次年重建、1896年毕工',
        'whole_webpage_approved': False, 'other_facts_approved': False,
    }

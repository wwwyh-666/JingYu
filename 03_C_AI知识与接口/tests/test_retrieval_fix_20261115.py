"""2026-11-15 八景检索问题最小修复的针对性回归测试。

修复内容：仅追加检索元数据。
- TT_QND_004 keywords 追加“举行”“活动”（不添加“祈年殿”，避免与 TT_QND_003 竞争）。
- ZYM_GATE_002 keywords 追加“保留”“现存”“两座”“主体建筑”，query_aliases 追加两条自然问法。
不改 statement/period/Evidence/来源白名单/审核记录。
"""
import pytest

from app.repository import Repository

# 第一轮真实验收的8题（Q2、Q8为本次修复对象，其余6题为防退化对照）
ACCEPTANCE_CASES = [
    ('Q1', 'GG', '故宫博物院是哪一年成立的？', 'GG_PALACE_001'),
    ('Q2', 'TT', '祈年殿过去主要用于举行什么活动？', 'TT_QND_004'),
    ('Q3', 'ZGL', '钟楼上悬挂的报时铜钟有多重？', 'ZGL_TOWER_002'),
    ('Q4', 'YHY', '佛香阁在颐和园中有什么地位？', 'YHY_FXF_001'),
    ('Q5', 'JS', '景山公园里著名的观景亭是哪一座？', 'JS_WCT_001'),
    ('Q6', 'GWF', '恭王府先后有哪些著名主人？', 'GWF_MANSION_002'),
    ('Q7', 'YHG', '雍和宫是什么时候改为藏传佛教寺院的？', 'YHG_TEMPLE_001'),
    ('Q8', 'ZYM', '正阳门现在还保留哪两座主体建筑？', 'ZYM_GATE_002'),
]


def fact(repo, fact_id):
    return next(f for f in repo.facts if f.fact_id == fact_id)


@pytest.mark.parametrize('test_id,spot,question,expected', ACCEPTANCE_CASES)
def test_acceptance_question_retrieves_expected_fact(test_id, spot, question, expected):
    """修复后：8道验收题的预期事实都进入管线取的top3，且该事实有可发布证据。

    Q3/Q5在原验收中即为top3内命中（首选为同景点另一事实但模型正确引用目标事实），
    Q2/Q8的首选命中另由专门用例断言。
    """
    repo = Repository()
    hits = [f.fact_id for f in repo.search(spot, question)]
    assert expected in hits[:3], f'{test_id} 命中 {hits}'
    rows = repo.publishable_evidence(fact(repo, expected))
    assert rows and all(e.usage == 'answer' for e in rows)


def test_q2_activity_question_hits_004_without_generic_competing_keyword():
    """Q2 修复仅用“举行/活动”，未添加“祈年殿”这类会与003竞争的关键词。"""
    repo = Repository()
    q = '祈年殿过去主要用于举行什么活动？'
    assert [f.fact_id for f in repo.search('TT', q)][:1] == ['TT_QND_004']
    assert '祈年殿' not in fact(repo, 'TT_QND_004').keywords
    assert {'举行', '活动'} <= set(fact(repo, 'TT_QND_004').keywords)


def test_q8_existing_buildings_question_hits_002_before_001():
    """Q8 修复后，涉及“保留/现存/两座主体建筑”的问题优先命中002。"""
    repo = Repository()
    for q in ['正阳门现在还保留哪两座主体建筑？', '正阳门现存哪些建筑？']:
        hits = [f.fact_id for f in repo.search('ZYM', q)]
        assert hits[:1] == ['ZYM_GATE_002'], q
    assert {'保留', '现存', '两座', '主体建筑'} <= set(fact(repo, 'ZYM_GATE_002').keywords)


def test_blue_tile_question_still_prefers_003():
    """“蓝瓦”问题仍优先命中003，且004不参与竞争。"""
    repo = Repository()
    for q in ['祈年殿的蓝瓦是什么时候改的？', '蓝瓦']:
        hits = [f.fact_id for f in repo.search('TT', q)]
        assert hits[:1] == ['TT_QND_003'], q
        assert 'TT_QND_004' not in hits
    assert [f.fact_id for f in repo.search('TT', '蓝瓦')] == ['TT_QND_003']


def test_pending_tiantan_facts_still_blocked():
    """TT_QND_001/002 仍不能进入正式检索结果。"""
    repo = Repository()
    assert repo.search('TT', '1420') == []
    assert repo.search('TT', '1538') == []
    assert [f.fact_id for f in repo.search('TT', '祈谷')] == ['TT_QND_004']
    assert repo.retrieve_with_claims('TT', '1542') == []


@pytest.mark.parametrize('spot,query', [
    ('GG', '祈年殿举行什么活动'), ('ZGL', '祈年殿举行什么活动'),
    ('YHY', '祈年殿举行什么活动'), ('JS', '祈年殿举行什么活动'),
    ('GWF', '祈年殿举行什么活动'), ('YHG', '祈年殿举行什么活动'),
    ('ZYM', '祈年殿举行什么活动'), ('TT', '正阳门主体建筑'),
    ('GG', '正阳门主体建筑'), ('ZGL', '正阳门主体建筑'),
    ('YHY', '正阳门主体建筑'), ('JS', '正阳门主体建筑'),
    ('GWF', '正阳门主体建筑'), ('YHG', '正阳门主体建筑'),
])
def test_new_keywords_do_not_leak_across_spots(spot, query):
    """新增检索词只在所属景点内生效，跨景点隔离保持。"""
    repo = Repository()
    assert repo.search(spot, query) == []


def test_new_keywords_do_not_affect_scoped_filters():
    """对象/时期过滤语义不因新增关键词改变。"""
    repo = Repository()
    assert repo.search('ZYM', '主体建筑', object_id='ZYM_OTHER') == []
    assert [f.fact_id for f in repo.search('TT', '举行活动', period='清代·孟春（正月）祈谷礼')] == ['TT_QND_004']
    assert repo.search('TT', '举行活动', period='明清·紫禁城建筑格局') == []

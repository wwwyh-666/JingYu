import json
import re
from pathlib import Path
from .models import Evidence, Fact, Source, Spot
DATA = Path(__file__).resolve().parents[1] / 'data'
class Repository:
    def __init__(self, data_dir: Path = DATA):
        self.data_dir = data_dir
        read = lambda p: json.loads(p.read_text(encoding='utf-8'))
        self.spots = [Spot.model_validate(x) for x in read(data_dir/'spots.json')]
        self.sources = [Source.model_validate(x) for x in read(data_dir/'sources.json')]
        self.facts = [Fact.model_validate(x) for p in sorted(data_dir.glob('facts_*.json')) for x in read(p)]
        self.evidence = [Evidence.model_validate(x) for p in sorted(data_dir.glob('evidence_*.json')) for x in read(p)]
        for rows, key in [(self.spots,'spot_id'),(self.sources,'source_id'),(self.facts,'fact_id')]:
            values=[getattr(x,key) for x in rows]
            if len(values)!=len(set(values)): raise ValueError(f'duplicate {key}')
        if {s.spot_id for s in self.spots} != {'TT','GG','ZGL','YHY','JS','GWF','YHG','ZYM'}:
            raise ValueError('eight canonical spot IDs required')
        for fact in self.facts:
            if fact.spot_id not in {s.spot_id for s in self.spots}: raise ValueError('unknown spot')
            if not set(fact.source_ids) <= {s.source_id for s in self.sources}: raise ValueError('unknown source')
        if len({e.evidence_id for e in self.evidence}) != len(self.evidence):
            raise ValueError('duplicate evidence_id')

    def evidence_is_publishable(self, evidence: Evidence, fact: Fact) -> bool:
        sources = {s.source_id: s for s in self.sources}
        return bool(
            fact.review_status == 'approved' and fact.reviewer and fact.reviewed_at
            and fact.dispute_status != 'disputed'
            and all(sid in sources and sources[sid].review_status == 'approved'
                    and sources[sid].reviewer and sources[sid].reviewed_at for sid in fact.source_ids)
            and evidence.review_status == 'approved' and evidence.reviewer and evidence.reviewed_at
            and evidence.source_id in fact.source_ids and evidence.source_id in sources
            and evidence.evidence_id in sources[evidence.source_id].approved_evidence_ids
            and str(evidence.url) == str(sources[evidence.source_id].url)
            and evidence.fact_id == fact.fact_id and evidence.spot_id == fact.spot_id
            and evidence.object_id == fact.object_id and evidence.period == fact.period
            and evidence.usage != 'suspected_typo'
        )

    def publishable_evidence(self, fact: Fact) -> list[Evidence]:
        rows = [e for e in self.evidence if self.evidence_is_publishable(e, fact)]
        return rows if any(e.usage == 'answer' for e in rows) else []

    @staticmethod
    def normalize_query(query: str) -> str:
        query = re.sub(r'\s+', '', query).casefold()
        # Small, explicit Tiantan baseline: covers phrasing such as 屋顶何时变成蓝的.
        # This is lexical normalization, not a semantic retrieval claim.
        if '蓝' in query and any(w in query for w in ('屋顶','房顶','琉璃瓦','瓦片')):
            query += '蓝瓦'
        return query
    def search(self, spot_id: str, query: str, *, object_id: str | None = None,
               period: str | None = None, include_unreviewed: bool = False) -> list[Fact]:
        # 最小确定性关键词检索。只按登记的关键词匹配，不作语义理解或答案生成。
        query=self.normalize_query(query.strip())
        if not query: return []
        rows=[]
        for fact in self.facts:
            if fact.spot_id!=spot_id or fact.review_status in {'rejected','disabled'}: continue
            if object_id and fact.object_id!=object_id: continue
            if period and fact.period!=period: continue
            if not include_unreviewed and not self.publishable_evidence(fact): continue
            score=sum(k.casefold() in query for k in fact.keywords + fact.query_aliases)
            if score: rows.append((score,fact))
        return [f for _,f in sorted(rows,key=lambda x:(-x[0],x[1].fact_id))]

    def retrieve_with_claims(self, spot_id: str, query: str, *, include_unreviewed: bool = False):
        # Return all competing claims for any matched disputed fact; never choose a year.
        facts = self.search(spot_id, query, include_unreviewed=include_unreviewed)
        claims_path = self.data_dir / 'TT_source_claims.json'
        events_path = self.data_dir / 'TT_events.json'
        claims = json.loads(claims_path.read_text(encoding='utf-8')) if claims_path.exists() else []
        events = json.loads(events_path.read_text(encoding='utf-8')) if events_path.exists() else []
        ids = {f.fact_id for f in facts}
        sources = {s.source_id: s for s in self.sources}
        result = []
        for fact in facts:
            groups = []
            for event in events:
                matching = [c for c in claims if c['fact_id'] == fact.fact_id and c['event_id'] == event['event_id']]
                if matching:
                    groups.append({**event, 'claims': [{**c, 'source_title': sources[c['source_id']].title, 'url': str(sources[c['source_id']].url)} for c in matching]})
            result.append({'fact': fact.model_dump(), 'events': groups})
        return result

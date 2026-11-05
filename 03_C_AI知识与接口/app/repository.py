import json
from pathlib import Path
from .models import Fact, Source, Spot
DATA = Path(__file__).resolve().parents[1] / 'data'
class Repository:
    def __init__(self, data_dir: Path = DATA):
        self.data_dir = data_dir
        read = lambda p: json.loads(p.read_text(encoding='utf-8'))
        self.spots = [Spot.model_validate(x) for x in read(data_dir/'spots.json')]
        self.sources = [Source.model_validate(x) for x in read(data_dir/'sources.json')]
        self.facts = [Fact.model_validate(x) for p in sorted(data_dir.glob('facts_*.json')) for x in read(p)]
        for rows, key in [(self.spots,'spot_id'),(self.sources,'source_id'),(self.facts,'fact_id')]:
            values=[getattr(x,key) for x in rows]
            if len(values)!=len(set(values)): raise ValueError(f'duplicate {key}')
        if {s.spot_id for s in self.spots} != {'TT','GG','ZGL','YHY','JS','GWF','YHG','ZYM'}:
            raise ValueError('eight canonical spot IDs required')
        for fact in self.facts:
            if fact.spot_id not in {s.spot_id for s in self.spots}: raise ValueError('unknown spot')
            if not set(fact.source_ids) <= {s.source_id for s in self.sources}: raise ValueError('unknown source')
    def search(self, spot_id: str, query: str, *, object_id: str | None = None,
               period: str | None = None, include_unreviewed: bool = False) -> list[Fact]:
        # 最小确定性关键词检索。只按登记的关键词匹配，不作语义理解或答案生成。
        query=query.strip().casefold()
        if not query: return []
        rows=[]
        for fact in self.facts:
            if fact.spot_id!=spot_id or fact.review_status=='rejected': continue
            if object_id and fact.object_id!=object_id: continue
            if period and fact.period!=period: continue
            if not include_unreviewed and fact.review_status!='approved': continue
            score=sum(k.casefold() in query for k in fact.keywords)
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

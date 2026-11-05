from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator

SpotId = Literal['TT','GG','ZGL','YHY','JS','GWF','YHG','ZYM']
ReviewStatus = Literal['pending_human_review','approved','rejected']
class Model(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
class Position(Model):
    x: float = Field(ge=0, le=1920)
    y: float = Field(ge=0, le=1080)
class Geo(Model):
    lat: float = Field(ge=-90,le=90)
    lng: float = Field(ge=-180,le=180)
    crs: Literal['WGS84','GCJ02']
    source_url: HttpUrl
class Spot(Model):
    spot_id: SpotId
    name: str
    theme: str
    aesthetic_type: str
    depth: Literal['deep','basic']
    map_position: Position | None = None
    image_key: str
    asset_status: Literal['pending_A_B'] = 'pending_A_B'
    geo: Geo | None = None
    name_source: str
    review_status: ReviewStatus = 'pending_human_review'
class Source(Model):
    source_id: str = Field(min_length=1)
    title: str
    institution: str
    url: HttpUrl
    accessed_on: str
    published_on: str | None = None
    locator: str
    review_status: ReviewStatus
class FactEvidence(Model):
    source_id: str = Field(min_length=1)
    locator: str = Field(min_length=1)
    supports: str = Field(min_length=1)
    relation: Literal['supports','context_only','conflicts'] = 'supports'
class Fact(Model):
    fact_id: str = Field(min_length=1)
    spot_id: SpotId
    object_id: str
    period: str
    text: str = Field(min_length=1)
    source_ids: list[str] = Field(min_length=1)
    source_locator: str
    keywords: list[str] = Field(min_length=1)
    review_status: ReviewStatus
    reviewer: str | None = None
    reviewed_at: str | None = None
    notes: str
    dispute_status: Literal['disputed', 'not_assessed'] = 'not_assessed'
    statement_type: Literal['direct_source_paraphrase','multi_source_synthesis'] | None = None
    source_evidence: list[FactEvidence] = Field(default_factory=list)
    @model_validator(mode='after')
    def approved_requires_review(self):
        if self.statement_type is not None:
            evidence_ids=[e.source_id for e in self.source_evidence]
            if len(evidence_ids)!=len(set(evidence_ids)) or set(evidence_ids)!=set(self.source_ids):
                raise ValueError('each declared source must have exactly one located evidence entry')
            if not any(e.relation=='supports' for e in self.source_evidence):
                raise ValueError('at least one supporting source is required')
        if self.review_status == 'approved'  and not (self.reviewer and self.reviewed_at):
            raise ValueError('approved facts require reviewer and reviewed_at')
        return self
class ChatRequest(Model):
    spot_id: SpotId
    question: str = Field(min_length=1,max_length=2000)
    session_id: str | None = Field(default=None,max_length=100)
    turn_id: int = Field(default=1,ge=1,le=1000)
    object_id: str | None = Field(default=None,max_length=100)
class Citation(Model):
    source_id: str
    title: str
    url: HttpUrl
class ChatResponse(Model):
    spot_id: SpotId
    session_id: str | None
    turn_id: int
    answer: str
    fact_ids: list[str]
    citations: list[Citation]
    confidence_flag: Literal['mock','insufficient_evidence','supported']
    check_status: Literal['not_checked','human_reviewed']
    is_mock: bool
    model_called: bool
class SpotsResponse(Model):
    schema_version: str = '0.1.0'
    data_status: Literal['template'] = 'template'
    items: list[Spot]
class DraftRequest(Model):
    spot_id: SpotId
    prompt: str = Field(default='',max_length=2000)
    media_ids: list[str] = Field(default_factory=list,max_length=5)
    fact_ids: list[str] = Field(default_factory=list,max_length=20)
    visibility: Literal['private'] = 'private'
    @model_validator(mode='after')
    def input_required(self):
        if not self.prompt and not self.media_ids:
            raise ValueError('prompt or media_ids is required')
        return self
class DraftResponse(Model):
    spot_id: SpotId
    title: str
    template_id: str
    paragraphs: list[str]
    fact_ids: list[str]
    source_ids: list[str]
    visibility: Literal['private']
    is_mock: bool
    model_called: bool

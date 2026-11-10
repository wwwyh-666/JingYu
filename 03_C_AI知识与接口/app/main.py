import os
from contextlib import asynccontextmanager
from pathlib import Path
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from .models import ChatRequest, ChatResponse, DraftRequest, SourceResponse, SpotsResponse
from .model_client import ChatModel, ModelConfig
from .qa import QAService
from .repository import Repository
ROOT=Path(__file__).resolve().parents[1]
load_dotenv(ROOT/'.env')


def create_app(data_dir=None, model=None, audit_dir=None):
    factory=lambda: Repository(Path(data_dir) if data_dir is not None else ROOT/'data')
    model=model if model is not None else ChatModel(ModelConfig.from_env())
    @asynccontextmanager
    async def lifespan(app):
        factory()  # Validate current JSON on startup, then reload per request.
        app.state.qa=QAService(factory,model,audit_dir or ROOT/'logs'/'qa')
        yield
    app=FastAPI(title='京遇知识问答接口',version='0.2.0',lifespan=lifespan)
    app.add_middleware(CORSMiddleware,allow_origins=[x.strip() for x in os.getenv(
        'CORS_ORIGINS','http://localhost:5173,http://127.0.0.1:5173').split(',') if x.strip()],
        allow_methods=['GET','POST'],allow_headers=['Content-Type'])

    @app.get('/health')
    def health():
        repo=factory()
        return {'status':'ok','stage':'2026-11-09-single-turn-evidence-pipeline',
            'model_provider':getattr(getattr(model,'config',None),'provider','test_adapter'),
            'model_ready':model.ready,'model_called':False,'spot_count':len(repo.spots),
            'candidate_fact_count':len(repo.facts),
            'publishable_fact_count':sum(bool(repo.publishable_evidence(f)) for f in repo.facts)}

    @app.get('/spots',response_model=SpotsResponse)
    def spots():
        return SpotsResponse(items=factory().spots)

    @app.post('/chat',response_model=ChatResponse)
    def chat(body: ChatRequest):
        response=app.state.qa.answer(body)
        if response.error_code and response.error_code.startswith('MODEL_'):
            status=504 if response.error_code=='MODEL_TIMEOUT' else (
                503 if response.error_code in {'MODEL_NOT_CONFIGURED','MODEL_TRANSPORT_ERROR'} else 502)
            return JSONResponse(status_code=status,content=response.model_dump(mode='json'))
        return response

    @app.get('/sources/{source_id}',response_model=SourceResponse)
    def source_detail(source_id: str):
        repo=factory()
        source=next((s for s in repo.sources if s.source_id==source_id),None)
        evidence=[e for f in repo.facts for e in repo.publishable_evidence(f) if e.source_id==source_id]
        if source is None or not evidence:
            raise HTTPException(404,detail={'code':'SOURCE_NOT_PUBLISHABLE',
                'message':'该来源不存在或尚无符合审校要求的可发布原文。'})
        return {'source':source.model_dump(mode='json'),
                'evidence':[e.model_dump(mode='json') for e in evidence]}

    @app.post('/journal/draft',status_code=501)
    def draft(body: DraftRequest):
        raise HTTPException(501,detail={'code':'NOT_IMPLEMENTED','message':'仅预留合同，尚未实现手账生成',
                                       'is_mock':False,'model_called':False})
    return app


app=create_app()

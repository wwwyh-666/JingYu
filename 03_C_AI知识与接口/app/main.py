import os
from contextlib import asynccontextmanager
from pathlib import Path
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from .models import ChatRequest, ChatResponse, DraftRequest, SpotsResponse
from .repository import Repository
ROOT=Path(__file__).resolve().parents[1]
load_dotenv(ROOT/'.env')
@asynccontextmanager
async def lifespan(app):
    app.state.repository=Repository()
    yield
app=FastAPI(title='京遇 C 初始化接口',version='0.1.0',lifespan=lifespan)
app.add_middleware(CORSMiddleware,allow_origins=[x.strip() for x in os.getenv(
    'CORS_ORIGINS','http://localhost:5173,http://127.0.0.1:5173').split(',') if x.strip()],
    allow_methods=['GET','POST'],allow_headers=['Content-Type'])
@app.get('/health')
def health():
    repo=app.state.repository
    return {'status':'ok','stage':'2026-11-05-initialization','model_provider':'disabled',
            'model_called':False,'spot_count':len(repo.spots),'candidate_fact_count':len(repo.facts)}
@app.get('/spots',response_model=SpotsResponse)
def spots():
    return SpotsResponse(items=app.state.repository.spots)
@app.post('/chat',response_model=ChatResponse)
def chat(body: ChatRequest):
    return ChatResponse(spot_id=body.spot_id,session_id=body.session_id,turn_id=body.turn_id,
        answer='【模拟数据】接口已连通；文化内容待人工审校，尚未接入模型。',
        fact_ids=[],citations=[],confidence_flag='mock',check_status='not_checked',
        is_mock=True,model_called=False)
@app.post('/journal/draft',status_code=501)
def draft(body: DraftRequest):
    raise HTTPException(501,detail={'code':'NOT_IMPLEMENTED','message':'仅预留合同，尚未实现手账生成',
                                   'is_mock':False,'model_called':False})

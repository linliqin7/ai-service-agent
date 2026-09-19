from pathlib import Path
import os,threading,time,uuid,json
from fastapi import FastAPI,HTTPException,Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse,JSONResponse
from pydantic import BaseModel,Field,field_validator
from typing import Literal
from app.schemas import SessionState
from app.runtime.engine import Engine
from app.config import Settings
from app.llm.deepseek import DeepSeekClient
from app.data.repository import USERS,profile
from app.rag.retriever import records
from app.rag.governance import current
from app.storage import Store
ROOT=Path(__file__).resolve().parents[1]
settings=Settings()
app=FastAPI(title='经纪业务智能客服 Agent',version='0.2.0')
llm=DeepSeekClient(settings.deepseek_api_key,settings.deepseek_base_url,settings.deepseek_model) if settings.deepseek_api_key else None
engine=Engine(llm=llm)
store=Store(os.environ.get('AGENT_DB_PATH',str(ROOT/'var'/'agent.sqlite3')))
locks={}; guard=threading.Lock(); traffic={}

def session(sid):
    s=store.get(sid)
    if not s:raise HTTPException(404,'会话不存在或已超过24小时，请新建会话')
    return s

def lock_for(sid):
    with guard:return locks.setdefault(sid,threading.Lock())

@app.middleware('http')
async def limits(request:Request,call_next):
    # The server is a local personal application, not a public multi-tenant deployment.
    origin=request.headers.get('origin','')
    if origin and origin not in ('http://127.0.0.1:8000','http://localhost:8000','http://testserver'):
        return JSONResponse({'detail':'不允许跨站请求'},403)
    if request.method=='POST':
        host=request.client.host if request.client else 'local';now=time.monotonic()
        with guard:
            recent=[t for t in traffic.get(host,[]) if now-t<60]
            if len(recent)>=120:return JSONResponse({'detail':'请求过于频繁，请稍后重试'},429)
            traffic[host]=[*recent,now]
    response=await call_next(request)
    response.headers['X-Content-Type-Options']='nosniff'
    response.headers['Referrer-Policy']='no-referrer'
    response.headers['Cache-Control']='no-store'
    response.headers['Content-Security-Policy']="default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'"
    return response

class Message(BaseModel):
    content:str=Field(min_length=1,max_length=2000)
    @field_validator('content')
    @classmethod
    def nonempty(cls,v):
        if not v.strip():raise ValueError('请输入问题')
        return v.strip()
class Auth(BaseModel):user_id:str
class Feedback(BaseModel):
    trace_id:str=Field(min_length=1,max_length=100)
    rating:Literal['helpful','unhelpful']

@app.get('/api/health')
def health():return {'status':'ok','llm_enabled':bool(engine.llm),'model':settings.deepseek_model,'business_data':'simulation','knowledge_records':len(records()),'session_storage':'SQLite'}
@app.get('/api/profiles')
def profiles():return [{'user_id':u['user_id'],'asset_bucket':u['asset_bucket'],'lifecycle':u['lifecycle']} for u in USERS.values()]
@app.post('/api/sessions',response_model=SessionState)
def create():
    s=SessionState(session_id=str(uuid.uuid4()));store.save(s);return s
@app.get('/api/sessions/{sid}',response_model=SessionState)
def get(sid:str):return session(sid)
@app.delete('/api/sessions/{sid}')
def delete(sid:str):
    with lock_for(sid):session(sid);store.delete(sid)
    return {'deleted':True}
@app.post('/api/sessions/{sid}/auth',response_model=SessionState)
def auth(sid:str,body:Auth):
    if body.user_id not in USERS:raise HTTPException(400,'模拟账户不存在')
    with lock_for(sid):
        s=session(sid)
        # Switching identity must not carry private context from the previous persona.
        if s.user_id and s.user_id!=body.user_id:
            s.messages=[];s.pending_slots={};s.traces=[];store.clear_private(sid)
        s.user_id=body.user_id;s.authenticated=True;store.save(s)
    return s
@app.get('/api/sessions/{sid}/profile')
def user_profile(sid:str):
    s=session(sid)
    if not s.authenticated:raise HTTPException(401,'请先登录模拟账户')
    return profile(s.user_id)
@app.post('/api/sessions/{sid}/logout')
def logout(sid:str):
    with lock_for(sid):
        s=session(sid);store.clear_private(sid);s.authenticated=False;s.user_id=None;s.messages=[];s.traces=[];s.pending_slots={};store.save(s)
    return {'ok':True}
@app.post('/api/sessions/{sid}/messages')
def message(sid:str,body:Message):
    lock=lock_for(sid)
    if not lock.acquire(blocking=False):raise HTTPException(409,'上一条问题还在处理中')
    try:
        s=session(sid);response=engine.handle(s,body.content);s.traces.extend(response.trace);s.traces=s.traces[-1000:]
        if response.handoff:response.handoff=store.ticket(s,response.handoff['reason'])
        s.messages[-1]['response']=response.model_dump(mode='json')
        store.save(s);return response
    finally:lock.release()
@app.get('/api/sessions/{sid}/trace')
def trace(sid:str):return session(sid).traces
@app.post('/api/sessions/{sid}/handoff')
def handoff(sid:str):
    with lock_for(sid):return store.ticket(session(sid),'用户主动申请')
@app.get('/api/sessions/{sid}/tickets')
def tickets(sid:str):session(sid);return store.tickets(sid)
@app.post('/api/sessions/{sid}/feedback')
def feedback(sid:str,body:Feedback):
    session(sid);store.feedback(sid,body.trace_id,body.rating);return {'saved':True}
@app.get('/api/knowledge')
def knowledge():return [record for record in records() if current(record,audience='public')]
@app.get('/api/evaluation')
def evaluation():
    p=ROOT/'eval'/'report.json'
    return json.loads(p.read_text()) if p.exists() else {'status':'尚未运行评测'}
app.mount('/static',StaticFiles(directory=ROOT/'web'),name='static')
@app.get('/')
def home():return FileResponse(ROOT/'web'/'index.html')
@app.get('/favicon.ico',include_in_schema=False)
def favicon():return FileResponse(ROOT/'web'/'favicon.svg',media_type='image/svg+xml')

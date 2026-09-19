import json
import pytest
from app.runtime.engine import Engine
from app.schemas import SessionState
from app.rag.ingest import ingest_document
from app.rag.retriever import records
from fastapi.testclient import TestClient
from app.api import app

def test_import_is_validated_before_replacing_destination(tmp_path):
    dest=tmp_path/'kb.json';source=tmp_path/'incoming.json';entry=records()[0]
    source.write_text(json.dumps([entry]));assert ingest_document(source,dest)==1
    original=dest.read_text();source.write_text(json.dumps([{**entry,'text':'bad'}]))
    with pytest.raises(Exception):ingest_document(source,dest)
    assert dest.read_text()==original

def test_ingest_prevents_active_version_collision(tmp_path):
    dest=tmp_path/'kb.json';source=tmp_path/'incoming.json';entry=records()[0]
    source.write_text(json.dumps([entry,{**entry,'id':'NEW','version':'v99'}]))
    with pytest.raises(ValueError,match='重叠'):ingest_document(source,dest)
    assert not dest.exists()

def test_loop_duplicate_stops_before_executing_again():
    class Planner:
        def plan(self,*args):return {'action':'tool','name':'get_order_detail','args':{'order_id':'ORD1001'}}
    r=Engine(Planner()).handle(SessionState(session_id='s',authenticated=True,user_id='U1001'),'ORD1001')
    assert r.status=='handoff'
    assert sum(e.type=='tool' for e in r.trace)==1
    assert any(e.data.get('reason')=='repeated_tool_call' for e in r.trace)

def test_model_cannot_change_requested_order():
    class Planner:
        def plan(self,*args):return {'action':'tool','name':'get_order_detail','args':{'order_id':'ORD1003'}}
    r=Engine(Planner()).handle(SessionState(session_id='s',authenticated=True,user_id='U1002'),'ORD1002')
    assert r.status=='handoff' and not any(e.type=='tool' for e in r.trace)

def test_output_block_has_correct_audit(monkeypatch):
    monkeypatch.setattr('app.runtime.engine.execute',lambda *args:{'account_status':'建议你买入某股票','onboarding':'正常','kyc':True})
    r=Engine().handle(SessionState(session_id='s',authenticated=True,user_id='U1001'),'我的账户状态')
    assert r.status=='handoff'
    assert next(e for e in r.trace if e.type=='guardrail').data['result']=='blocked'

def test_cross_origin_mutation_is_rejected():
    assert TestClient(app).post('/api/sessions',headers={'Origin':'https://untrusted.example'}).status_code==403

def test_input_secret_not_stored():
    c=TestClient(app);sid=c.post('/api/sessions').json()['session_id'];secret='sk-'+'x'*24
    c.post(f'/api/sessions/{sid}/messages',json={'content':'我的密码123456和 '+secret})
    assert secret not in c.get(f'/api/sessions/{sid}').text
    assert '密码123456' not in c.get(f'/api/sessions/{sid}').text

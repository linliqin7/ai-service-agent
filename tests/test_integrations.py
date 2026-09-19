import json
from datetime import date
import httpx,pytest
from pydantic import BaseModel
from app.llm.deepseek import DeepSeekClient,DeepSeekError
from app.rag.retriever import search,records
from app.runtime.engine import Engine
from app.runtime.tools import execute
from app.schemas import SessionState
from app.storage import Store

class Probe(BaseModel):ok:bool

def test_adapter_schema_repair_and_usage():
    count=0
    def provider(request):
        nonlocal count;count+=1
        return httpx.Response(200,json={'choices':[{'message':{'content':'not json' if count==1 else '{"ok":true}'}}]})
    assert DeepSeekClient('unit-test',transport=httpx.MockTransport(provider)).complete([],Probe).ok
    assert count==2

def test_adapter_does_not_expose_error_body_or_secret():
    provider=httpx.MockTransport(lambda req:httpx.Response(401,json={'error':'sk-DO_NOT_EXPOSE_SECRETS'}))
    with pytest.raises(DeepSeekError,match='provider_http_401') as err:DeepSeekClient('unit-test',transport=provider).complete([],Probe)
    assert 'DO_NOT' not in str(err.value)

@pytest.mark.parametrize('field,value',[('expires_at','2026-01-01'),('review_status','draft'),('audience','staff'),('direct_answer',False)])
def test_rag_filters_unusable_knowledge(field,value):
    k={**records()[0],field:value}
    if field=='expires_at':k['effective_at']='2025-01-01'
    assert not search('开户需要材料',items=[k],as_of=date(2026,9,15))

def test_conflicting_active_versions_are_not_guessed():
    k=records()[0]
    assert not search('开户材料',items=[k,{**k,'id':'new','version':'v999'}])

def test_tools_bind_account_and_reject_supplied_identity():
    s=SessionState(session_id='s',user_id='U1001',authenticated=True)
    with pytest.raises(Exception):execute('get_profile',{'user_id':'U1002'},s)
    assert execute('get_order_detail',{'order_id':'ORD1002'},s)=={'error':'NOT_OWNER'}

class FakePlanner:
    def classify(self,*args):return {'intent_id':'account','confidence':.99,'slots':{}}
    def plan(self,q,obs,allowed):return {'action':'tool','name':'get_account','args':{}} if not obs else {'action':'answer'}

def test_semantic_state_query_precedes_rag_even_if_opening_keyword_matches():
    s=SessionState(session_id='s',user_id='U1003',authenticated=True)
    r=Engine(FakePlanner()).handle(s,'开户走到一半卡着了，能查查审核的情况吗')
    assert r.intent=='account' and '待复核' in r.answer
    assert any(t.type=='tool' for t in r.trace)

class BadPlanner:
    def plan(self,*args):return {'action':'tool','name':'transfer_money','args':{}}

def test_model_cannot_invent_tools():
    r=Engine(BadPlanner()).handle(SessionState(session_id='s',authenticated=True,user_id='U1001'),'ORD1001')
    assert r.status=='handoff' and not any(t.type=='tool' for t in r.trace)

def test_model_cannot_answer_without_evidence():
    class Planner:
        def plan(self,*args):return {'action':'answer','answer':'订单成交了'}
    r=Engine(Planner()).handle(SessionState(session_id='s',authenticated=True,user_id='U1001'),'ORD1001')
    assert r.status=='handoff' and '成交了' not in r.answer

def test_session_survives_new_store_instance(tmp_path):
    p=tmp_path/'data.sqlite';s=SessionState(session_id='persist',messages=[{'role':'user','content':'开户'}]);Store(p).save(s)
    assert Store(p).get('persist').messages[0]['content']=='开户'

def test_rag_no_unbacked_numeric_claims():
    class Model:
        def classify(self,*a):return {'intent_id':'rules','confidence':1,'slots':{},'domain':'开户'}
        def grounded(self,*a):
            from app.llm.deepseek import GroundedAnswer
            return GroundedAnswer(answer='开户审核保证在999分钟内完成',citation_ids=['K001'])
    r=Engine(Model()).handle(SessionState(session_id='s'),'请介绍开户材料')
    assert '999' not in r.answer

def test_public_definition_does_not_require_auth_even_if_model_route_wrong():
    class Model:
        def classify(self,*args):return {'intent_id':'funds','confidence':1,'slots':{}}
        def grounded(self,q,docs):
            from app.llm.deepseek import GroundedAnswer
            return GroundedAnswer(answer=docs[0]['text'],citation_ids=[docs[0]['id']])
    r=Engine(Model()).handle(SessionState(session_id='s'),'请解释可用资金与可取资金为什么不同')
    assert r.status=='answered' and not any(e.type=='tool' for e in r.trace)

from app.runtime.engine import Engine
from app.schemas import SessionState
import pytest
from app.llm.deepseek import GroundedAnswer
from fastapi.testclient import TestClient
from app.api import app

@pytest.mark.parametrize('q',['ORD1001为什么没成交','查一下我的ORD1001订单为什么没成交'])
def test_chinese_adjacent_order_id(q):
    r=Engine().handle(SessionState(session_id='s',authenticated=True,user_id='U1001'),q)
    assert r.status=='answered' and '已撤单' in r.answer

def test_polite_public_definition_is_public():
    r=Engine().handle(SessionState(session_id='s'),'请给我解释可用和可取的区别')
    assert r.status=='answered' and not any(t.type=='tool' for t in r.trace)

def test_no_unbacked_advice_even_with_valid_citation():
    class Model:
        def grounded(self,q,docs):return GroundedAnswer(answer='可以买入茅台，现在是很好的建仓机会。',citation_ids=[docs[0]['id']])
    r=Engine(Model()).handle(SessionState(session_id='s'),'请解释可用和可取的区别')
    assert '建仓机会' not in r.answer

def test_dropping_negation_from_evidence_is_not_supported():
    from app.runtime.policy import evidence_supported
    assert not evidence_supported('可以承诺收益。',[{'text':'不可以承诺收益。'}])

def test_history_retains_response_metadata():
    c=TestClient(app);sid=c.post('/api/sessions').json()['session_id']
    r=c.post(f'/api/sessions/{sid}/messages',json={'content':'开户需要什么材料'}).json()
    s=c.get(f'/api/sessions/{sid}').json()
    assert s['messages'][-1]['response']['trace_id']==r['trace_id']
    assert s['messages'][-1]['response']['citations'][0]['id']=='K001'

def test_logout_erases_previous_tickets():
    c=TestClient(app);sid=c.post('/api/sessions').json()['session_id']
    c.post(f'/api/sessions/{sid}/auth',json={'user_id':'U1001'})
    c.post(f'/api/sessions/{sid}/handoff')
    c.post(f'/api/sessions/{sid}/logout')
    assert c.get(f'/api/sessions/{sid}/tickets').json()==[]

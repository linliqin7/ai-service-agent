from app.runtime.engine import Engine
from app.schemas import SessionState

def test_rule_query_uses_retrieval():
 r=Engine().handle(SessionState(session_id='s'),'开户需要什么材料')
 assert r.status=='answered' and any(e.type=='retrieve' for e in r.trace)
def test_qualification_requires_auth():
 r=Engine().handle(SessionState(session_id='s'),'我能不能开创业板')
 assert r.status=='need_auth'
def test_qualification_uses_profile_after_auth():
 r=Engine().handle(SessionState(session_id='s',user_id='U1002',authenticated=True),'我能不能开创业板')
 assert r.status=='answered' and '交易经验' in r.answer
def test_high_risk_request_is_rejected():
 r=Engine().handle(SessionState(session_id='s'),'推荐我买哪只股票')
 assert r.status=='rejected'
def test_order_has_ownership_check():
 r=Engine().handle(SessionState(session_id='s',user_id='U1002',authenticated=True),'查 ORD1001 为什么没成交')
 assert r.status=='handoff' and '越权' in r.answer

from datetime import date

import pytest

from app.runtime.answerability import evaluate
from app.runtime.engine import Engine
from app.runtime.evidence import business_evidence, knowledge_evidence
from app.runtime.tools import execute
from app.rag.retriever import records
from app.schemas import EntityValue, SessionState, TaskState

AS_OF = date(2026, 9, 19)


def context():
    task = TaskState(task_type='order', objective='我的订单为什么没成交', entities={
        'order_id': EntityValue(name='order_id', value='ORD1001', source='user')})
    session = SessionState(session_id='gate', user_id='U1001', authenticated=True, active_task=task)
    result = execute('get_order_detail', {'order_id': 'ORD1001'}, session)
    task.evidence = [business_evidence(task, session, 'get_order_detail', {'order_id': 'ORD1001'}, result, as_of=AS_OF)]
    return task, session


def test_verified_order_facts_are_sufficient():
    task, session = context()
    decision = evaluate(task, session, as_of=AS_OF)
    assert decision.status == 'sufficient' and decision.next_action == 'answer'
    assert set(decision.required_supports) == {'ORDER_STATUS', 'ORDER_REASON'}
    assert decision.evidence_ids == [task.evidence[0].evidence_id]


def test_missing_order_id_requires_clarification():
    task, session = context()
    task.entities.clear()
    assert evaluate(task, session, as_of=AS_OF).status == 'missing_user_information'


def test_related_rule_and_order_status_cannot_invent_reason():
    task, session = context()
    result = {'order_id': 'ORD1001', 'user_id': 'U1001', 'status': 'NOT_FILLED'}
    task.evidence = [business_evidence(task, session, 'get_order_detail', {'order_id': 'ORD1001'}, result, as_of=AS_OF)]
    task.evidence += knowledge_evidence(task, [records()[2]], '未成交', as_of=AS_OF)
    decision = evaluate(task, session, as_of=AS_OF)
    assert decision.status == 'missing_business_evidence'
    assert decision.missing_supports == ['ORDER_REASON']
    assert decision.next_action == 'handoff'


def test_retrieve_is_bounded_pre_execution_action():
    task, session = context()
    task.evidence.clear()
    assert evaluate(task, session, as_of=AS_OF, can_retrieve=True).next_action == 'retrieve'
    assert evaluate(task, session, as_of=AS_OF).next_action == 'handoff'


def test_conflicting_verified_facts_fail_closed():
    task, session = context()
    evidence = task.evidence[0]
    task.evidence.append(evidence.model_copy(update={
        'evidence_id': 'conflict', 'content': {**evidence.content, 'status': '已成交'}}))
    assert evaluate(task, session, as_of=AS_OF).status == 'conflicting_evidence'


def test_expired_evidence_cannot_be_reused():
    task = TaskState(task_type='rules', objective='开户材料')
    session = SessionState(session_id='public', active_task=task)
    task.evidence = knowledge_evidence(task, [records()[0]], task.objective, as_of=AS_OF)
    decision = evaluate(task, session, as_of=date(2028, 1, 1))
    assert decision.status == 'expired_or_unusable_evidence'
    assert decision.next_action == 'handoff'


def test_owner_change_is_unauthorized():
    task, session = context()
    session.user_id = 'U1002'
    assert evaluate(task, session, as_of=AS_OF).status == 'unauthorized'


def test_unsafe_task_uses_existing_policy():
    task = TaskState(task_type='rules', objective='推荐我买哪只股票')
    decision = evaluate(task, SessionState(session_id='unsafe'), as_of=AS_OF)
    assert decision.status == 'unsafe' and decision.next_action == 'reject'


def test_unsupported_task_is_out_of_scope():
    task = TaskState(task_type='unsupported', objective='未知服务')
    assert evaluate(task, SessionState(session_id='scope'), as_of=AS_OF).status == 'out_of_scope'


def test_evidence_from_other_task_is_never_sufficient():
    old, session = context()
    new = TaskState(task_type='order', objective=old.objective, entities=old.entities, evidence=old.evidence)
    session.active_task = new
    decision = evaluate(new, session, as_of=AS_OF)
    assert decision.status != 'sufficient' and not decision.evidence_ids


@pytest.mark.parametrize('query,uid,status,label', [
    ('开户需要什么材料', None, 'answered', 'sufficient'),
    ('我的账户状态', 'U1001', 'answered', 'sufficient'),
    ('我的订单为什么没成交', None, 'clarify', 'missing_user_information'),
    ('查 ORD1001 为什么没成交', 'U1001', 'answered', 'sufficient'),
    ('推荐我买哪只股票', None, 'rejected', 'unsafe'),
    ('我要转人工', None, 'handoff', None),
])
def test_canonical_engine_paths(query, uid, status, label):
    session = SessionState(session_id='canonical', user_id=uid, authenticated=bool(uid))
    response = Engine().handle(session, query)
    assert response.status == status
    if label:
        assert response.answerability.status == label
        assert response.answerability.task_id == session.active_task.task_id
    else:
        assert response.answerability is None  # Explicit handoff bypasses the gate.


def test_multiturn_order_without_reason_never_guesses(monkeypatch):
    from app.data import repository
    monkeypatch.setitem(repository.ORDERS, 'ORD1001', {
        'order_id': 'ORD1001', 'user_id': 'U1001', 'status': 'NOT_FILLED'})
    session = SessionState(session_id='badcase', user_id='U1001', authenticated=True)
    assert Engine().handle(session, '我的订单为什么没成交').status == 'clarify'
    response = Engine().handle(session, 'ORD1001')
    assert response.status == 'handoff'
    assert response.answerability.status == 'missing_business_evidence'
    assert 'ORDER_REASON' in response.answerability.missing_supports
    assert not any(word in response.answer for word in ['资金不足', '价格不合适', '流动性不足'])


def test_task_switch_drops_order_evidence():
    session = SessionState(session_id='switch', user_id='U1001', authenticated=True)
    Engine().handle(session, 'ORD1001')
    old_task = session.active_task
    assert old_task.evidence
    response = Engine().handle(session, '基金赎回多久到账')
    assert session.active_task.task_id != old_task.task_id
    assert all(e.task_id == session.active_task.task_id for e in session.active_task.evidence)
    assert not any(e.entity_binding.get('order_id') for e in session.active_task.evidence)
    assert 'ORD1001' not in response.answer


@pytest.mark.parametrize('change', [{'audience': 'staff'}, {'review_status': 'draft'}, {'direct_answer': False}, {'expires_at': '2026-01-02'}])
def test_raw_unusable_search_results_cannot_bypass_gate(monkeypatch, change):
    monkeypatch.setattr('app.runtime.engine.search', lambda *a, **kw: [{**records()[0], **change}])
    response = Engine().handle(SessionState(session_id='invalid-knowledge'), '开户需要什么材料')
    assert response.status != 'answered'
    assert not response.citations
    assert response.answerability.status == 'expired_or_unusable_evidence'


def test_conflicting_knowledge_blocks_generation_and_fallback(monkeypatch):
    first = records()[0]
    second = {**first, 'id':'conflict', 'version':'different', 'text':'开户仅需测试文件，此条与其他材料规则冲突。'}
    monkeypatch.setattr('app.runtime.engine.search', lambda *a, **kw: [first,second])
    response = Engine().handle(SessionState(session_id='conflict'), '开户需要什么材料')
    assert response.status == 'handoff'
    assert response.answerability.status == 'conflicting_evidence'
    assert not response.citations


def test_engine_ownership_failure_is_unauthorized():
    session = SessionState(session_id='not-owner', user_id='U1002', authenticated=True)
    response = Engine().handle(session, 'ORD1001')
    assert response.status == 'handoff'
    assert response.answerability.status == 'unauthorized'
    assert not session.active_task.evidence


def test_planner_getting_definition_still_cannot_answer_missing_reason(monkeypatch):
    from app.data import repository
    monkeypatch.setitem(repository.ORDERS, 'ORD1001', {'order_id':'ORD1001','user_id':'U1001','status':'NOT_FILLED'})
    class Planner:
        def plan(self, q, observations, allowed):
            if not observations:return {'action':'tool','name':'get_order_detail','args':{'order_id':'ORD1001'}}
            if len(observations)==1:return {'action':'tool','name':'search_knowledge','args':{'query':'未成交'}}
            return {'action':'answer','answer':'因为资金不足'}
    session = SessionState(session_id='related-only', user_id='U1001', authenticated=True)
    response = Engine(Planner()).handle(session, 'ORD1001为什么没成交')
    assert response.status == 'handoff'
    assert response.answerability.status == 'missing_business_evidence'
    assert 'ORDER_RULE' in response.answerability.satisfied_supports
    assert '资金不足' not in response.answer


def test_two_unknown_turns_preserve_existing_handoff_behavior():
    session = SessionState(session_id='unknown')
    assert Engine().handle(session, '这个怎么弄').status == 'clarify'
    first_id = session.active_task.task_id
    response = Engine().handle(session, '就是那个')
    assert response.status == 'handoff'
    assert session.active_task.task_id == first_id
    assert response.answerability.next_action == 'handoff'


def test_simple_status_query_can_answer_without_invented_reason(monkeypatch):
    from app.data import repository
    monkeypatch.setitem(repository.ORDERS, 'ORD1001', {'order_id':'ORD1001','user_id':'U1001','status':'NOT_FILLED'})
    session = SessionState(session_id='status-only', user_id='U1001', authenticated=True)
    response = Engine().handle(session, '查 ORD1001 状态')
    assert response.status == 'answered'
    assert response.answerability.required_supports == ['ORDER_STATUS']
    assert '当前接口未提供原因' in response.answer


def test_staff_tool_knowledge_is_not_exposed_to_planner_or_response(monkeypatch):
    secret_record = {**records()[2], 'audience':'staff', 'text':'INTERNAL_STAFF_ONLY 此处为内部专用订单说明。'}
    monkeypatch.setattr('app.runtime.tools.search', lambda q: [secret_record])
    class Planner:
        def plan(self, q, observations, allowed):
            if not observations:return {'action':'tool','name':'get_order_detail','args':{'order_id':'ORD1001'}}
            if len(observations)==1:return {'action':'tool','name':'search_knowledge','args':{'query':'未成交'}}
            assert observations[-1]['result']['citations'] == []
            return {'action':'answer'}
    response = Engine(Planner()).handle(SessionState(session_id='private-doc',user_id='U1001',authenticated=True),'ORD1001为什么没成交')
    assert response.status == 'answered'  # Existing owner-bound facts suffice.
    assert not response.citations
    assert 'INTERNAL_STAFF_ONLY' not in response.model_dump_json()


def test_successful_tool_does_not_bypass_later_execution_failure():
    class Planner:
        def plan(self, q, observations, allowed):
            return {'action':'tool','name':'get_order_detail','args':{'order_id':'ORD1001'}}
    response = Engine(Planner()).handle(SessionState(session_id='repeat',user_id='U1001',authenticated=True),'ORD1001')
    assert response.status == 'handoff'
    assert response.answerability.status == 'missing_business_evidence'
    assert response.answerability.next_action == 'handoff'


def test_later_tool_error_cannot_leave_sufficient_decision(monkeypatch):
    def failing_search(name, args, session):
        if name == 'search_knowledge':return {'error': 'SEARCH_UNAVAILABLE'}
        return execute(name, args, session)
    monkeypatch.setattr('app.runtime.engine.execute', failing_search)
    class Planner:
        def plan(self, q, observations, allowed):
            if not observations:return {'action':'tool','name':'get_order_detail','args':{'order_id':'ORD1001'}}
            return {'action':'tool','name':'search_knowledge','args':{'query':'未成交'}}
    response = Engine(Planner()).handle(SessionState(session_id='tool-error',user_id='U1001',authenticated=True),'ORD1001为什么没成交')
    assert response.status == 'handoff'
    assert response.answerability.status == 'missing_business_evidence'
    assert response.answerability.next_action == 'handoff'


def test_grounded_model_is_not_called_when_gate_rejects_knowledge(monkeypatch):
    monkeypatch.setattr('app.runtime.engine.search', lambda *a, **kw: [{**records()[0], 'audience':'staff'}])
    class Model:
        def grounded(self, *args):raise AssertionError('must not generate before sufficient gate')
    response = Engine(Model()).handle(SessionState(session_id='no-generation'), '请解释开户材料')
    assert response.status == 'handoff'
    assert response.answerability.status == 'expired_or_unusable_evidence'
    assert not any(e.type=='fallback' and e.data['reason']=='AssertionError' for e in response.trace)

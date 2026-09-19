from datetime import date

import pytest

from app.rag.retriever import records
from app.runtime.evidence import business_evidence, knowledge_evidence
from app.runtime.tools import execute
from app.schemas import EntityValue, SessionState, TaskState

AS_OF = date(2026, 9, 19)


def order_context():
    task = TaskState(task_type='order', objective='为什么没成交', entities={
        'order_id': EntityValue(name='order_id', value='ORD1001', source='user')})
    return SessionState(session_id='evidence', user_id='U1001', authenticated=True, active_task=task)


def test_controlled_order_result_is_verified_and_bound():
    session = order_context()
    result = execute('get_order_detail', {'order_id': 'ORD1001'}, session)
    evidence = business_evidence(session.active_task, session, 'get_order_detail',
                                 {'order_id': 'ORD1001'}, result, as_of=AS_OF)
    assert evidence.verified
    assert evidence.task_id == session.active_task.task_id
    assert evidence.entity_binding == {'user_id': 'U1001', 'order_id': 'ORD1001'}
    assert 'ORDER_REASON' in evidence.supports


@pytest.mark.parametrize('failure', ['guest', 'other_owner', 'tool_error', 'invented_tool', 'wrong_order'])
def test_invalid_business_result_is_not_promoted(failure):
    session = order_context()
    result = execute('get_order_detail', {'order_id': 'ORD1001'}, session)
    name = 'get_order_detail'
    if failure == 'guest': session.authenticated = False
    if failure == 'other_owner': result['user_id'] = 'U1002'
    if failure == 'tool_error': result = {'error': 'NOT_OWNER'}
    if failure == 'invented_tool': name = 'model_generated_fact'
    if failure == 'wrong_order': result['order_id'] = 'ORD1002'
    assert business_evidence(session.active_task, session, name, {'order_id': 'ORD1001'}, result, as_of=AS_OF) is None


def test_public_knowledge_is_governed_and_task_bound():
    task = TaskState(task_type='rules', objective='开户材料')
    evidence = knowledge_evidence(task, [records()[0]], task.objective, as_of=AS_OF)
    assert len(evidence) == 1
    assert evidence[0].task_id == task.task_id
    assert evidence[0].source_id == 'K001'
    assert evidence[0].supports == ['PUBLIC_DEFINITION']


@pytest.mark.parametrize('changes', [
    {'audience': 'staff'}, {'expires_at': '2026-09-01'},
    {'direct_answer': False}, {'review_status': 'draft'},
    {'review_status': 'retired'}, {'id': ''},
])
def test_unusable_knowledge_is_not_promoted(changes):
    task = TaskState(task_type='rules', objective='开户材料')
    assert knowledge_evidence(task, [{**records()[0], **changes}], task.objective, as_of=AS_OF) == []


def test_unrelated_knowledge_does_not_cover_order_reason():
    task = order_context().active_task
    assert knowledge_evidence(task, [records()[0]], '开户材料', as_of=AS_OF) == []


def test_order_definition_is_only_rule_support_not_personal_reason():
    task = order_context().active_task
    evidence = knowledge_evidence(task, [records()[2]], '未成交', as_of=AS_OF)
    assert evidence and evidence[0].supports == ['ORDER_RULE']


def test_empty_holdings_and_zero_balances_are_valid_facts():
    session = order_context()
    session.user_id = 'U1003'
    for name, support in [('get_funds', 'ACCOUNT_BALANCE'), ('get_holdings', 'HOLDING_LIST')]:
        result = execute(name, {}, session)
        evidence = business_evidence(session.active_task, session, name, {}, result, as_of=AS_OF)
        assert support in evidence.supports

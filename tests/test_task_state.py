from app.runtime.engine import Engine
from app.schemas import SessionState, TaskStatus


def test_first_private_message_creates_active_order_task():
    session = SessionState(session_id='task-create')

    response = Engine().handle(session, '我的委托为什么没成交')

    assert response.status == 'clarify'
    assert session.active_task is not None
    assert session.active_task.task_id
    assert session.active_task.task_type == 'order'
    assert session.active_task.status == TaskStatus.CLARIFYING


def test_clarification_count_belongs_to_task_lifecycle():
    session = SessionState(session_id='task-clarification')

    first = Engine().handle(session, '这是一个无法识别的问题')
    first_task_id = session.active_task.task_id
    assert first.status == 'clarify'
    assert session.active_task.status == TaskStatus.CLARIFYING
    assert session.active_task.clarification_count == 1

    answered = Engine().handle(session, '开户需要什么材料')
    assert answered.status == 'answered'
    assert session.active_task.status == TaskStatus.COMPLETED

    next_unknown = Engine().handle(session, '另一个无法识别的问题')
    assert next_unknown.status == 'clarify'
    assert session.active_task.task_id != first_task_id
    assert session.active_task.clarification_count == 1


def test_successful_knowledge_task_is_completed():
    session = SessionState(session_id='task-complete')

    response = Engine().handle(session, '开户需要什么材料')

    assert response.status == 'answered'
    assert session.active_task.status == TaskStatus.COMPLETED
    assert session.active_task.completion_reason == 'answered'


def test_risk_request_rejects_active_task():
    session = SessionState(session_id='task-reject')

    response = Engine().handle(session, '推荐我买哪只股票')

    assert response.status == 'rejected'
    assert session.active_task.status == TaskStatus.REJECTED


def test_explicit_handoff_marks_active_task():
    session = SessionState(session_id='task-handoff')

    response = Engine().handle(session, '我要转人工')

    assert response.status == 'handoff'
    assert session.active_task.status == TaskStatus.HANDOFF


def test_new_task_replaces_unfinished_task_without_parallel_tasks():
    session = SessionState(session_id='task-switch')

    Engine().handle(session, '我的委托为什么没成交')
    old_task = session.active_task
    old_task_id = old_task.task_id

    response = Engine().handle(session, '开户需要什么材料')

    assert response.status == 'answered'
    assert old_task.status == TaskStatus.ABANDONED
    assert session.active_task.task_id != old_task_id
    assert session.active_task.task_type == 'rules'
    assert session.active_task.status == TaskStatus.COMPLETED


def test_order_entity_is_unconfirmed_until_owner_tool_validation():
    session = SessionState(session_id='task-entity')

    first = Engine().handle(session, '查 ORD1001 为什么没成交')
    assert first.status == 'need_auth'
    assert session.active_task.entities['order_id'].source == 'user'
    assert session.active_task.entities['order_id'].confirmed is False

    session.user_id = 'U1001'
    session.authenticated = True
    second = Engine().handle(session, '继续查询')

    assert second.status == 'answered'
    assert session.active_task.entities['order_id'].confirmed is True

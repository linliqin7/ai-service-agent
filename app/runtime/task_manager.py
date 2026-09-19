"""Small, deterministic lifecycle helpers for the active task."""

from datetime import datetime, timezone

from app.schemas import EntityValue, TaskState, TaskStatus


def _touch(task: TaskState) -> TaskState:
    task.updated_at = datetime.now(timezone.utc)
    return task


def create_task(task_type: str, objective: str, domain: str | None = None,
                required_slots: list[str] | None = None) -> TaskState:
    return TaskState(
        task_type=task_type,
        objective=objective,
        domain=domain,
        required_slots=list(required_slots or []),
        missing_slots=list(required_slots or []),
    )


def start_task(task: TaskState) -> TaskState:
    task.status = TaskStatus.EXECUTING
    task.completion_reason = None
    return _touch(task)


def set_clarifying(task: TaskState, missing_slots: list[str] | None = None) -> TaskState:
    task.status = TaskStatus.CLARIFYING
    if missing_slots is not None:
        update_missing_slots(task, missing_slots)
    return _touch(task)


def set_executing(task: TaskState) -> TaskState:
    return start_task(task)


def complete_task(task: TaskState, reason: str = 'answered') -> TaskState:
    task.status = TaskStatus.COMPLETED
    task.completion_reason = reason
    task.missing_slots = []
    return _touch(task)


def handoff_task(task: TaskState, reason: str = 'handoff') -> TaskState:
    task.status = TaskStatus.HANDOFF
    task.completion_reason = reason
    return _touch(task)


def reject_task(task: TaskState, reason: str = 'rejected') -> TaskState:
    task.status = TaskStatus.REJECTED
    task.completion_reason = reason
    return _touch(task)


def abandon_task(task: TaskState, reason: str = 'abandoned') -> TaskState:
    task.status = TaskStatus.ABANDONED
    task.completion_reason = reason
    return _touch(task)


def increment_clarification(task: TaskState) -> TaskState:
    task.clarification_count += 1
    task.status = TaskStatus.CLARIFYING
    return _touch(task)


def update_missing_slots(task: TaskState, missing_slots: list[str]) -> TaskState:
    task.missing_slots = list(dict.fromkeys(missing_slots))
    return _touch(task)


def set_entity(task: TaskState, entity: EntityValue) -> TaskState:
    task.entities[entity.name] = entity
    return _touch(task)

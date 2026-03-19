from app.schemas.task import TaskStatus


ALLOWED_TASK_TRANSITIONS: dict[TaskStatus, set[TaskStatus]] = {
    TaskStatus.QUEUED: {
        TaskStatus.RUNNING,
        TaskStatus.CANCELLED,
    },
    TaskStatus.RUNNING: {
        TaskStatus.WAITING_APPROVAL,
        TaskStatus.BLOCKED,
        TaskStatus.SUCCEEDED,
        TaskStatus.FAILED,
        TaskStatus.CANCELLED,
    },
    TaskStatus.WAITING_APPROVAL: {
        TaskStatus.RUNNING,
        TaskStatus.CANCELLED,
    },
    TaskStatus.BLOCKED: {
        TaskStatus.QUEUED,
        TaskStatus.CANCELLED,
    },
    TaskStatus.SUCCEEDED: set(),
    TaskStatus.FAILED: {
        TaskStatus.QUEUED,
        TaskStatus.CANCELLED,
    },
    TaskStatus.CANCELLED: set(),
}


def can_transition(current_status: TaskStatus, new_status: TaskStatus) -> bool:
    allowed_targets = ALLOWED_TASK_TRANSITIONS.get(current_status, set())
    return new_status in allowed_targets


def ensure_transition_allowed(current_status: TaskStatus, new_status: TaskStatus) -> None:
    if not can_transition(current_status, new_status):
        raise ValueError(
            f"Illegal task status transition: {current_status.value} -> {new_status.value}"
        )
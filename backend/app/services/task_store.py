"""In-memory detection task records."""

from dataclasses import dataclass, field

from ..models.contracts import ErrorItem


@dataclass
class TaskRecord:
    task_id: str
    filename: str
    size: int = 0
    status: str = "uploaded"
    progress: int = 0
    errors: list[ErrorItem] = field(default_factory=list)
    message: str = ""


class TaskStore:
    def __init__(self) -> None:
        self._tasks: dict[str, TaskRecord] = {}

    def put(self, task: TaskRecord) -> TaskRecord:
        self._tasks[task.task_id] = task
        return task

    def get(self, task_id: str) -> TaskRecord | None:
        return self._tasks.get(task_id)


store = TaskStore()

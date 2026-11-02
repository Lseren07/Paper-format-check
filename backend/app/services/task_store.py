"""In-memory detection task records."""

import time
from dataclasses import dataclass, field

from ..models.contracts import Document, ErrorItem


@dataclass
class TaskRecord:
    task_id: str
    filename: str
    size: int = 0
    status: str = "uploaded"
    progress: int = 0
    errors: list[ErrorItem] = field(default_factory=list)
    document: Document | None = None
    message: str = ""
    rule_set_id: str | None = None
    created_at: float = field(default_factory=time.time)


class TaskStore:
    def __init__(self) -> None:
        self._tasks: dict[str, TaskRecord] = {}

    def put(self, task: TaskRecord) -> TaskRecord:
        self._tasks[task.task_id] = task
        return task

    def get(self, task_id: str) -> TaskRecord | None:
        return self._tasks.get(task_id)

    def delete(self, task_id: str) -> TaskRecord | None:
        return self._tasks.pop(task_id, None)

    def cleanup(self, ttl_seconds: int) -> int:
        """删掉超过 TTL 的任务，返回清理条数。

        内存任务只是「本次检测的工作区」，历史与报告副本都在 Flask 侧，
        所以过期直接丢弃即可，不需要回调任何地方。
        """
        now = time.time()
        expired = [task_id for task_id, task in self._tasks.items() if now - task.created_at > ttl_seconds]
        for task_id in expired:
            self._tasks.pop(task_id, None)
        return len(expired)

    def __len__(self) -> int:
        return len(self._tasks)


store = TaskStore()

"""项目案例数据存储服务"""
import json
from pathlib import Path
from typing import Any
from uuid import uuid4

from ..models.contracts import ProjectCase


class CaseStore:
    """案例存储管理器，使用 JSON 文件持久化"""

    def __init__(self, data_dir: Path | str = "backend/data"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.cases_file = self.data_dir / "cases.json"
        self._ensure_file()

    def _ensure_file(self) -> None:
        """确保 JSON 文件存在"""
        if not self.cases_file.exists():
            self.cases_file.write_text("[]", encoding="utf-8")

    def _read_all(self) -> list[dict[str, Any]]:
        """读取所有案例"""
        content = self.cases_file.read_text(encoding="utf-8")
        return json.loads(content)

    def _write_all(self, cases: list[dict[str, Any]]) -> None:
        """写入所有案例"""
        self.cases_file.write_text(
            json.dumps(cases, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )

    def create(self, case: ProjectCase) -> ProjectCase:
        """创建新案例"""
        cases = self._read_all()
        case_dict = case.model_dump()
        cases.append(case_dict)
        self._write_all(cases)
        return case

    def get(self, case_id: str) -> ProjectCase | None:
        """获取单个案例"""
        cases = self._read_all()
        for case_dict in cases:
            if case_dict["case_id"] == case_id:
                return ProjectCase.model_validate(case_dict)
        return None

    def list_all(self) -> list[ProjectCase]:
        """获取所有案例"""
        cases = self._read_all()
        return [ProjectCase.model_validate(c) for c in cases]

    def update(self, case_id: str, updates: dict[str, Any]) -> ProjectCase | None:
        """更新案例"""
        cases = self._read_all()
        for i, case_dict in enumerate(cases):
            if case_dict["case_id"] == case_id:
                case_dict.update(updates)
                cases[i] = case_dict
                self._write_all(cases)
                return ProjectCase.model_validate(case_dict)
        return None

    def delete(self, case_id: str) -> bool:
        """删除案例"""
        cases = self._read_all()
        original_len = len(cases)
        cases = [c for c in cases if c["case_id"] != case_id]
        if len(cases) < original_len:
            self._write_all(cases)
            return True
        return False

    def generate_case_id(self) -> str:
        """生成唯一的案例 ID"""
        return f"case_{uuid4().hex[:12]}"


# 全局单例
_store: CaseStore | None = None


def get_case_store() -> CaseStore:
    """获取全局案例存储实例"""
    global _store
    if _store is None:
        _store = CaseStore()
    return _store

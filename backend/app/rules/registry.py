"""规则集注册表：目录扫描 + 可配置选择。

规则文件不再写死在代码里（曾经的 `rules/default.json`），改为：

- 扫描 `PAPER_RULES_DIR`（默认仓库根 `rules/`）下的每个 `*.json`；
- 规则集 id 取文件里的 `rule_set_id`，缺省回退到文件名（不含扩展名）；
- 默认使用哪一套由 `PAPER_RULES_DEFAULT`（默认 `default`）决定，
  单次检测也可以在 `/api/v1/detect/start` 里用 `rule_set_id` 覆盖。

这样往 `rules/` 里丢一个新学校的规范文件即可被识别，不会出现「文件躺在目录里但没人引用」的孤儿规则。
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from pydantic import BaseModel

from .contracts import RuleSet
from .loader import load_rules

REPO_ROOT = Path(__file__).resolve().parents[3]
RULES_DIR_ENV = "PAPER_RULES_DIR"
DEFAULT_RULE_SET_ENV = "PAPER_RULES_DEFAULT"
DEFAULT_RULE_SET_ID = "default"
# 以下划线 / 点开头的文件和 JSON Schema 片段不算独立规则集。
SKIP_PREFIXES = ("_", ".")
SKIP_SUFFIXES = (".schema.json",)


class RuleSetNotFoundError(LookupError):
    """规则集 id 在扫描结果里找不到。"""


class RuleSetInfo(BaseModel):
    """一个规则文件的元信息，供接口列出可选项。"""

    id: str
    name: str
    file: str
    path: str
    schema_version: str = ""
    description: str | None = None
    check_count: int = 0
    enabled_check_count: int = 0
    source_available: bool = False
    source_title: str | None = None
    source_document: str | None = None
    loadable: bool = True
    error: str | None = None


@dataclass(frozen=True)
class ResolvedRuleSet:
    """规则集本体 + 它的元信息（报告要展示规则文件名与 id）。"""

    rules: RuleSet
    info: RuleSetInfo


def rules_dir() -> Path:
    raw = os.getenv(RULES_DIR_ENV)
    return Path(raw).expanduser() if raw else REPO_ROOT / "rules"


def default_rule_set_id() -> str:
    return os.getenv(DEFAULT_RULE_SET_ENV) or DEFAULT_RULE_SET_ID


def clear_rule_cache() -> None:
    _RULE_CACHE.clear()


_RULE_CACHE: dict[str, tuple[int, RuleSet]] = {}


def _load_cached(path: Path) -> RuleSet:
    key = str(path)
    mtime = path.stat().st_mtime_ns
    cached = _RULE_CACHE.get(key)
    if cached is not None and cached[0] == mtime:
        return cached[1]
    rules = load_rules(path)
    _RULE_CACHE[key] = (mtime, rules)
    return rules


def _iter_rule_files(directory: Path) -> list[Path]:
    if not directory.is_dir():
        return []
    return sorted(
        path
        for path in directory.glob("*.json")
        if not path.name.startswith(SKIP_PREFIXES) and not path.name.endswith(SKIP_SUFFIXES)
    )


def _describe(path: Path, rules: RuleSet) -> RuleSetInfo:
    enabled = sum(1 for check in rules.checks if check.enabled)
    source = rules.source
    return RuleSetInfo(
        id=rules.rule_set_id or path.stem,
        name=rules.name,
        file=path.name,
        path=str(path),
        schema_version=rules.schema_version,
        description=rules.description,
        check_count=len(rules.checks),
        enabled_check_count=enabled,
        source_available=source is not None,
        source_title=source.title if source else None,
        source_document=source.document if source else None,
    )


def _describe_broken(path: Path, error: Exception) -> RuleSetInfo:
    return RuleSetInfo(
        id=path.stem,
        name=path.stem,
        file=path.name,
        path=str(path),
        loadable=False,
        error=f"{type(error).__name__}: {error}",
    )


def discover_rule_sets(directory: Path | None = None) -> list[RuleSetInfo]:
    """扫描目录下的规则文件；单个文件损坏只标记自己，不影响其余文件。"""
    infos: list[RuleSetInfo] = []
    for path in _iter_rule_files(directory or rules_dir()):
        try:
            infos.append(_describe(path, _load_cached(path)))
        except (OSError, ValueError, TypeError) as error:
            infos.append(_describe_broken(path, error))
    return infos


def available_rule_set_ids() -> list[str]:
    return [info.id for info in discover_rule_sets() if info.loadable]


def rule_set_info(rule_set_id: str | None = None) -> RuleSetInfo:
    return resolve_rule_set(rule_set_id).info


def load_rule_set(rule_set_id: str | None = None) -> RuleSet:
    """按 id 取规则集；id 为空时取配置的默认规则集。"""
    return resolve_rule_set(rule_set_id).rules


def resolve_rule_set(rule_set_id: str | None = None) -> ResolvedRuleSet:
    """取回规则集本体与元信息，找不到或不完整时抛 `RuleSetNotFoundError`。"""
    target = rule_set_id or default_rule_set_id()
    directory = rules_dir()
    for path in _iter_rule_files(directory):
        try:
            rules = _load_cached(path)
        except (OSError, ValueError, TypeError) as error:
            if path.stem == target:
                raise RuleSetNotFoundError(f"规则集 {target} 加载失败：{error}") from error
            continue
        info = _describe(path, rules)
        if info.id == target:
            return ResolvedRuleSet(rules=rules, info=info)
    raise RuleSetNotFoundError(f"规则集不存在：{target}（可选：{', '.join(available_rule_set_ids()) or '无'}）")

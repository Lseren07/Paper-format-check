"""Compatibility exports for the unified rule engine.

The canonical rule implementation lives in :mod:`backend.app.rules`.
规则集的选择由 :mod:`backend.app.rules.registry` 负责（目录扫描 + 环境变量配置）。
"""

from ..rules.contracts import CheckRule, RuleSet, RuleTarget
from ..rules.loader import load_rules
from ..rules.registry import (
    RuleSetNotFoundError,
    ResolvedRuleSet,
    discover_rule_sets,
    load_rule_set,
    resolve_rule_set,
    rules_dir,
)
from ..rules.service import check_document

__all__ = [
    "CheckRule",
    "RuleSet",
    "RuleTarget",
    "RuleSetNotFoundError",
    "ResolvedRuleSet",
    "check_document",
    "discover_rule_sets",
    "load_rule_set",
    "load_rules",
    "resolve_rule_set",
    "rules_dir",
]

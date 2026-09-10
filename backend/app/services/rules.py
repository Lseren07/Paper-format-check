"""Compatibility exports for the unified rule engine.

The canonical rule implementation lives in :mod:`backend.app.rules`.
"""

from ..rules.contracts import CheckRule, RuleSet, RuleTarget
from ..rules.loader import load_rules
from ..rules.service import check_document

__all__ = ["CheckRule", "RuleSet", "RuleTarget", "check_document", "load_rules"]

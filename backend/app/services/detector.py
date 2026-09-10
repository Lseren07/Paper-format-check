"""Compatibility exports for the unified rule engine.

Use ``backend.app.rules.check_document`` for all new callers. The previous
dictionary-based detector is intentionally no longer maintained.
"""

from ..rules.engine import DETECTORS, RuleEngine
from ..rules.errors import make_error

__all__ = ["DETECTORS", "RuleEngine", "make_error"]

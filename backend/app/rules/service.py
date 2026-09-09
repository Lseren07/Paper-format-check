from pathlib import Path

from ..models.contracts import Document, ErrorItem
from .contracts import RuleSet
from .engine import RuleEngine
from .loader import load_rules


def check_document(document: Document, rules: RuleSet | str | Path | dict) -> list[ErrorItem]:
    rule_set = rules if isinstance(rules, RuleSet) else load_rules(rules)
    return RuleEngine(document, rule_set).run()

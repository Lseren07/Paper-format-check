"""Run Word parsing and rule checks for an uploaded paper."""

from pathlib import Path

from ..models.contracts import Document, ErrorItem
from ..parser.word_parser import parse_docx
from ..rules.contracts import RuleSet
from ..rules.registry import load_rule_set
from ..rules.service import check_document
from .location import relocate_errors


def run_detection(
    path: Path,
    *,
    document_id: str,
    source_filename: str,
    rule_set: RuleSet | None = None,
) -> tuple[Document, list[ErrorItem]]:
    """按规则集执行检测；不传时取 `PAPER_RULES_DEFAULT` 指定的默认规则集。"""
    document = parse_docx(path, document_id=document_id, source_filename=source_filename)
    rules = rule_set if rule_set is not None else load_rule_set()
    return document, relocate_errors(document, check_document(document, rules))

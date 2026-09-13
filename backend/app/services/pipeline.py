"""Run Word parsing and rule checks for an uploaded paper."""

from pathlib import Path

from ..models.contracts import Document, ErrorItem
from ..parser.word_parser import parse_docx
from ..rules.service import check_document
from .location import relocate_errors

RULES_FILE = Path(__file__).resolve().parents[3] / "rules" / "default.json"


def run_detection(path: Path, *, document_id: str, source_filename: str) -> tuple[Document, list[ErrorItem]]:
    document = parse_docx(path, document_id=document_id, source_filename=source_filename)
    return document, relocate_errors(document, check_document(document, RULES_FILE))

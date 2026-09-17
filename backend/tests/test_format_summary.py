from backend.app.models.contracts import Document
from backend.app.parser.format_summary import build_format_summary


def test_build_format_summary_uses_majority_body_format() -> None:
    document = Document(
        document_id='D1',
        source_filename='x.docx',
        paragraphs=[{
            'paragraph_id': 'p-0001',
            'text': '正文',
            'structure': 'body',
            'heading': {'level': None},
            'format': {'line_spacing': 1.5},
            'runs': [{'text': '正文', 'font': {'effective': '宋体'}, 'size_pt': 12}],
        }],
        sections=[{'index': 0, 'margins_pt': {'top': 72, 'right': 72, 'bottom': 72, 'left': 72}}],
    )
    summary = build_format_summary(document)
    assert summary['structured']['body']['font'] == '宋体'
    assert summary['structured']['body']['size'] == '小四'
    assert summary['structured']['body']['line_spacing'] == '1.5倍'
    assert '正文格式：' in summary['text']
    assert '字体：宋体' in summary['text']
    assert '字号：小四' in summary['text']
    assert '行距：1.5倍' in summary['text']



def test_build_format_summary_includes_rendered_page_count() -> None:
    document = Document(
        document_id='D1',
        source_filename='x.docx',
        paragraphs=[{
            'paragraph_id': 'p-0001',
            'text': '正文',
            'structure': 'body',
            'heading': {'level': None},
            'format': {'line_spacing': 1.5},
            'runs': [{'text': '正文', 'font': {'effective': '宋体'}, 'size_pt': 12}],
        }],
        pages=[
            {'page_index': 0, 'page_number': 1, 'position': 'footer', 'number_format': 'decimal'},
            {'page_index': 1, 'page_number': 2, 'position': 'footer', 'number_format': 'decimal'},
        ],
    )
    summary = build_format_summary(document)
    assert '共2页' in summary['text']
    assert summary['structured']['page']['count'] == 2


def test_build_format_summary_translates_page_enum_values() -> None:
    document = Document(
        document_id='D1',
        source_filename='x.docx',
        pages=[
            {'page_index': 0, 'page_number': None, 'position': 'none', 'number_format': None},
        ],
    )

    summary = build_format_summary(document)

    assert summary['structured']['page']['page_number'] == '\u672a\u8bbe\u7f6e/\u9ed8\u8ba4\uff0c\u51711\u9875'
    assert 'none/default' not in summary['text']

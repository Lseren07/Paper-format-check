from pathlib import Path

from backend.app.models.contracts import Document
from backend.app.rules.detectors import detect_heading_numbering, detect_line_spacing, detect_page_margin
from backend.app.rules.loader import load_rules
from backend.app.rules.service import check_document
from backend.app.rules.contracts import CheckRule


RULES = Path('rules/default.json')


def test_default_rules_follow_cdu_page_and_heading_sizes() -> None:
    rules = load_rules(RULES)
    expected = {check.id: check.expected for check in rules.checks}
    assert rules.name == '电子科技大学成都学院本科毕业论文格式规范'
    assert expected['page-margin']['margin'] == {
        'top': '3.5cm', 'right': '3.0cm', 'bottom': '3.5cm', 'left': '3.0cm',
    }
    assert expected['page-margin']['header'] == '2.75cm'
    assert expected['page-margin']['footer'] == '1.75cm'
    assert expected['page-margin']['page'] == {'width_cm': 21.0, 'height_cm': 29.7}
    assert expected['body-line-spacing']['line_spacing'] == 20
    assert expected['title1-size']['size'] == '小三'
    assert expected['title3-size']['size'] == '小四'
    assert expected['title4-size']['size'] == '小四'
    assert expected['toc-title-size']['size'] == '小二'
    types = {check.type for check in rules.checks}
    assert {'required_sections', 'caption_format', 'keyword_format', 'header_text', 'paragraph_spacing'}.issubset(types)


def test_page_margin_detects_wrong_school_margin_and_header_distance() -> None:
    document = Document(document_id='D1', source_filename='x.docx', sections=[{
        'index': 0,
        'page_width_pt': 595.3,
        'page_height_pt': 841.9,
        'margins_pt': {'top': 72, 'right': 72, 'bottom': 72, 'left': 72},
        'header_distance_pt': 36,
        'footer_distance_pt': 36,
    }])
    errors = detect_page_margin(document, CheckRule(id='page-margin', type='page_margin', expected={
        'margin': {'top': '3.5cm'},
        'header': '2.75cm',
        'page': {'width_cm': 21.0, 'height_cm': 29.7},
    }))
    locations = {error.location for error in errors}
    assert 'section-0:margin-top' in locations
    assert 'section-0:header' in locations


def test_line_spacing_compares_exact_20pt_numerically() -> None:
    document = Document(document_id='D1', source_filename='x.docx', paragraphs=[{
        'paragraph_id': 'p-0001', 'text': '正文', 'heading': {'level': None},
        'style': {'name': 'Normal'}, 'format': {'line_spacing': 20.0},
        'runs': [],
    }])
    assert detect_line_spacing(document, CheckRule(id='s', type='line_spacing', target='body', expected={'line_spacing': 20})) == []


def test_heading_numbering_accepts_chinese_chapter_labels() -> None:
    document = Document(document_id='D1', source_filename='x.docx', paragraphs=[
        {'paragraph_id': 'p-0001', 'text': '第1章 绪论', 'heading': {'level': 1}, 'numbering': None, 'style': {'name': 'Heading 1'}},
        {'paragraph_id': 'p-0002', 'text': '第3章 分析', 'heading': {'level': 1}, 'numbering': None, 'style': {'name': 'Heading 1'}},
    ])
    errors = detect_heading_numbering(document, CheckRule(id='heading', type='heading_numbering', expected={}))
    assert errors[0].current == '3'
    assert errors[0].expected == '2'


def test_required_sections_and_keywords_and_captions_follow_spec() -> None:
    document = Document(document_id='D1', source_filename='x.docx', paragraphs=[
        {'paragraph_id': 'p-0001', 'text': '摘要', 'heading': {'level': None}, 'style': {'name': 'Normal'}, 'format': {}, 'runs': []},
        {'paragraph_id': 'p-0002', 'text': '关键词：排队', 'heading': {'level': None}, 'style': {'name': 'Normal'}, 'format': {}, 'runs': []},
        {'paragraph_id': 'p-0003', 'text': '图1 统计', 'heading': {'level': None}, 'style': {'name': 'Normal'},
         'format': {'alignment': 'left'},
         'runs': [{'text': '图1 统计', 'font': {'effective': '黑体'}, 'size_pt': 12, 'bold': None}]},
        {'paragraph_id': 'p-0004', 'text': '参考文献', 'heading': {'level': 1}, 'style': {'name': 'Heading 1'}, 'format': {}, 'runs': []},
    ], headers=[{'section_index': 0, 'variant': 'even', 'text': '页眉'}])
    errors = check_document(document, RULES)
    types = {error.type for error in errors}
    assert 'required_sections_error' in types
    assert 'keyword_format_error' in types
    assert 'caption_format_error' in types
    assert 'header_text_error' in types

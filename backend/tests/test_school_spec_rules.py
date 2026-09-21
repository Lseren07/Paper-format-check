from pathlib import Path

from backend.app.models.contracts import Document
from backend.app.rules.detectors import detect_heading_numbering, detect_line_spacing, detect_page_margin
from backend.app.rules.loader import load_rules
from backend.app.rules.service import check_document
from backend.app.rules.contracts import CheckRule
from backend.app.rules.spec_detectors import detect_keyword_format
from backend.app.rules.targets import paragraph_targets


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
    assert expected['body-size']['size'] == '小四'
    assert expected['abstract-en-first-line-indent']['first_line_indent'] == '1字符'
    assert expected['foreign-title-font']['font'] == '黑体'
    assert expected['foreign-title-size']['size'] == '小三'
    assert expected['foreign-body-font']['font'] == 'Times New Roman'
    assert expected['foreign-body-first-line-indent']['first_line_indent'] == '1字符'
    assert 'lowercase' not in expected['keywords-en-format']
    assert expected['page-number'] == {'position': 'footer', 'continuous': True}
    types = {check.type for check in rules.checks}
    assert {'required_sections', 'caption_format', 'keyword_format', 'header_text', 'paragraph_spacing'}.issubset(types)


def test_keyword_format_replaces_legacy_whole_paragraph_font_rules() -> None:
    rules = load_rules(RULES)
    checks = {check.id: check for check in rules.checks}

    assert not {'keywords-font', 'keywords-size', 'keywords-en-font', 'keywords-en-size'} & checks.keys()
    assert checks['keywords-zh'].expected == {
        'pattern': r'^关键词\s*[：:]',
        'min': 3,
        'max': 8,
        'required': True,
        'first_line_indent': 0,
        'label': {'font': '宋体', 'size': '小四', 'bold': True},
        'content': {'font': '宋体', 'size': '小四'},
    }
    assert checks['keywords-en-format'].expected == {
        'pattern': r'^Keywords\s*[：:]',
        'min': 3,
        'max': 8,
        'first_line_indent': 0,
        'label': {'font': 'Times New Roman', 'size': '小四', 'bold': True},
        'content': {'font': 'Times New Roman', 'size': '小四'},
    }


def test_keyword_content_checks_each_script_font_independently() -> None:
    text = '关键词：数据库；PostgreSQL；性能'
    document = Document(document_id='D1', source_filename='x.docx', paragraphs=[{
        'paragraph_id': 'p-0001', 'text': text, 'heading': {'level': None},
        'style': {'name': 'Normal'}, 'structure': 'keywords',
        'format': {'alignment': 'justify', 'first_line_indent_chars': 0},
        'runs': [
            {'text': '关键词：', 'font': {'effective': '宋体', 'ascii': '宋体', 'east_asia': '宋体'}, 'size_pt': 12, 'bold': True},
            {'text': '数据库；PostgreSQL；性能', 'font': {'effective': '宋体', 'ascii': 'Times New Roman', 'east_asia': '宋体'}, 'size_pt': 12, 'bold': False},
        ],
    }])
    rule = CheckRule(id='keywords-zh', type='keyword_format', target='keywords', expected={
        'pattern': r'^关键词\s*[：:]', 'required': True, 'min': 3, 'max': 8,
        'first_line_indent': 0,
        'label': {'font': '宋体', 'size': '小四', 'bold': True},
        'content': {'font': '宋体', 'size': '小四'},
    })

    assert detect_keyword_format(document, rule) == []


def test_keyword_mixed_run_reports_cjk_and_latin_as_separate_fragments() -> None:
    text = '关键词：数据库；PostgreSQL；性能'
    document = Document(document_id='D1', source_filename='x.docx', paragraphs=[{
        'paragraph_id': 'p-0001', 'text': text, 'heading': {'level': None},
        'style': {'name': 'Normal'}, 'structure': 'keywords',
        'format': {'first_line_indent_chars': 0},
        'runs': [
            {'text': '关键词：', 'font': {'effective': '宋体', 'ascii': '宋体', 'east_asia': '宋体'}, 'size_pt': 12, 'bold': True},
            {'text': '数据库；PostgreSQL；性能', 'font': {'effective': '宋体', 'ascii': '宋体', 'east_asia': 'Times New Roman'}, 'size_pt': 12, 'bold': False},
        ],
    }])
    rule = CheckRule(id='keywords-zh', type='keyword_format', target='keywords', expected={
        'pattern': r'^关键词\s*[：:]', 'required': True, 'min': 3, 'max': 8,
        'first_line_indent': 0,
        'label': {'font': '宋体', 'size': '小四', 'bold': True},
        'content': {'font': '宋体', 'size': '小四'},
    })

    errors = detect_keyword_format(document, rule)
    font_errors = [error for error in errors if ':font' not in error.location and error.expected in {'宋体', 'Times New Roman'}]

    assert len(font_errors) == 2
    assert any(error.location.endswith(':content:cjk') and '数据库' in error.content and error.expected == '宋体' for error in font_errors)
    assert any(error.location.endswith(':content:latin') and 'PostgreSQL' in error.content and error.expected == 'Times New Roman' for error in font_errors)


def test_english_keyword_label_allows_fullwidth_colon_in_latin_font() -> None:
    document = Document(document_id='D1', source_filename='x.docx', paragraphs=[{
        'paragraph_id': 'p-0001', 'text': 'Keywords：database; testing; system',
        'heading': {'level': None}, 'style': {'name': 'Normal'}, 'structure': 'keywords',
        'format': {'first_line_indent_chars': 0},
        'runs': [{
            'text': 'Keywords：database; testing; system',
            'font': {'effective': 'Times New Roman', 'ascii': 'Times New Roman', 'east_asia': '黑体'},
            'size_pt': 12, 'bold': True,
        }],
    }])
    rule = CheckRule(id='keywords-en-format', type='keyword_format', target='keywords-en', expected={
        'pattern': r'^Keywords\s*[：:]', 'min': 3, 'max': 8, 'first_line_indent': 0,
        'label': {'font': 'Times New Roman', 'size': '小四', 'bold': True},
        'content': {'font': 'Times New Roman', 'size': '小四'},
    })

    assert detect_keyword_format(document, rule) == []


def test_keyword_format_ignores_same_label_in_body() -> None:
    document = Document(document_id='D1', source_filename='x.docx', paragraphs=[{
        'paragraph_id': 'p-body', 'text': 'Keywords：正文中的术语说明',
        'heading': {'level': None}, 'style': {'name': 'Normal'},
        'structure': 'body', 'format': {'first_line_indent_chars': 2},
        'runs': [{'text': 'Keywords：正文中的术语说明', 'font': {'effective': '宋体'}, 'size_pt': 12, 'bold': False}],
    }])
    rule = CheckRule(id='keywords-en-format', type='keyword_format', target='keywords-en', expected={
        'pattern': r'^Keywords\s*[：:]', 'required': True, 'min': 3, 'max': 8,
        'first_line_indent': 0,
        'label': {'font': 'Times New Roman', 'size': '小四', 'bold': True},
        'content': {'font': 'Times New Roman', 'size': '小四'},
    })

    assert detect_keyword_format(document, rule) == []


def test_default_rules_skip_all_level_two_heading_format_checks_but_keep_toc_consistency() -> None:
    rules = load_rules(RULES)
    rule_ids = {check.id for check in rules.checks}

    assert not any(rule_id.startswith('title2-') for rule_id in rule_ids)
    assert 'toc-consistency' in rule_ids


def test_level_two_toc_entries_are_excluded_from_format_targets() -> None:
    document = Document(document_id='D1', source_filename='x.docx', paragraphs=[{
        'paragraph_id': 'p-toc-2', 'text': '1.1 研究背景\t12',
        'heading': {'level': 2}, 'style': {'name': 'TOC 2'},
        'structure': 'toc', 'format': {'alignment': 'center'}, 'runs': [],
    }], metadata={'toc_paragraphs': [{'text': '1.1 研究背景\t12', 'level': 2}]})

    assert 'toc-body' not in paragraph_targets(document)['p-toc-2']


def test_toc_consistency_ignores_numeric_body_text_and_matches_chapter_titles() -> None:
    document = Document(document_id='D1', source_filename='x.docx', paragraphs=[
        {'paragraph_id': 'p-0001', 'text': '第1章 绪论', 'heading': {'level': 1}, 'style': {'name': 'Heading 1'}, 'structure': 'body'},
        {'paragraph_id': 'p-0002', 'text': '1.1 研究背景', 'heading': {'level': 2}, 'style': {'name': 'Heading 2'}, 'structure': 'body'},
        {'paragraph_id': 'p-0003', 'text': '2026 年 4 月 15 日是测试日期', 'heading': {'level': None}, 'style': {'name': 'Normal'}, 'structure': 'body'},
    ], metadata={'toc_paragraphs': [
        {'text': '第1章 绪论\t1', 'level': 1},
        {'text': '1.1 研究背景\t1', 'level': 2},
    ]})

    errors = check_document(document, {
        'schema_version': '1.0', 'name': 'test', 'checks': [{
            'id': 'toc-consistency', 'type': 'toc_consistency', 'target': 'all', 'expected': {},
        }],
    })
    assert errors == []


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
        {'paragraph_id': 'p-0001', 'text': '摘要', 'heading': {'level': None}, 'style': {'name': 'Normal'}, 'structure': 'abstract', 'format': {}, 'runs': []},
        {'paragraph_id': 'p-0002', 'text': '关键词：排队', 'heading': {'level': None}, 'style': {'name': 'Normal'}, 'structure': 'keywords', 'format': {}, 'runs': []},
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

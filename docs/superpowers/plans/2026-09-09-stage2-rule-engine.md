# 阶段 2 规则引擎 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为已解析的 `Document` 建立可配置、可测试的规则引擎，输出符合冻结 `ErrorItem` 契约的格式检测结果。

**Architecture:** 规则文件采用 `schema_version`、规则元数据和 `checks` 数组的结构，由 Pydantic 模型负责加载与校验。规则引擎接收 `Document` 与规则集，按检测器注册表执行独立检查器；每个检查器只读取文档契约和对应规则，返回 `ErrorItem` 列表。阶段 2 先提供纯 Python API，上传 API 集成留到后续阶段。

**Tech Stack:** Python 3.12、Pydantic 2、pytest、python-docx、JSON。

**Spec:** `product-context.md`（“冻结契约”“下一步”与“风险”章节）。

## Global Constraints

- 不修改 `Document` 和 `ErrorItem` 的冻结顶层字段；`ErrorItem` 继续使用 `current` 与 `expected`，不增加 `required`。
- 不保存学生论文内容；规则引擎只处理内存中的 `Document`，不复制或持久化上传文件。
- 规则无法由当前解析结果可靠判断时返回人工核对状态/跳过结果，不伪造格式结论。
- 每个新增行为必须先写一个会失败的测试，再写最小实现并运行完整后端测试。
- 保留现有阶段 1 解析器行为和既有测试通过状态。

---

### Task 1: Define Rule Contracts and Loader

**Files:**
- Create: `backend/app/rules/__init__.py`
- Create: `backend/app/rules/contracts.py`
- Create: `backend/app/rules/loader.py`
- Modify: `rules/default.json`
- Test: `backend/tests/test_rule_loader.py`

**Interfaces:**
- Produces `RuleSet`, `CheckRule`, `RuleTarget` Pydantic models and `load_rules(source: str | Path | dict) -> RuleSet`.
- `RuleSet.schema_version` is a string; `RuleSet.name` is a string; `RuleSet.checks` is a list of `CheckRule`.
- `CheckRule.id`, `CheckRule.type`, `CheckRule.target` are required; `CheckRule.expected` is a dictionary; optional `enabled` defaults to `True`.

- [ ] **Step 1: Write the failing tests**

```python
def test_load_rules_accepts_stage2_schema(tmp_path):
    path = tmp_path / "rules.json"
    path.write_text(json.dumps({
        "schema_version": "1.0",
        "name": "test",
        "checks": [{"id": "body-font", "type": "font", "target": "body", "expected": {"font": "宋体"}}],
    }), encoding="utf-8")
    rules = load_rules(path)
    assert rules.checks[0].expected["font"] == "宋体"

def test_load_rules_rejects_missing_check_identity():
    with pytest.raises(ValidationError):
        load_rules({"schema_version": "1.0", "name": "test", "checks": [{"expected": {}}]})

def test_load_legacy_default_rule_file_maps_flat_fields():
    rules = load_rules(Path(__file__).parents[2] / "rules" / "default.json")
    assert any(check.type == "font" for check in rules.checks)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest backend/tests/test_rule_loader.py -q`
Expected: FAIL because the `backend.app.rules` package and loader do not exist.

- [ ] **Step 3: Implement the models, loader, and default rule migration**

Implement strict Pydantic models with `extra="forbid"` for rule identity fields, accept either a path, JSON object, or JSON text, and convert the current flat `rules/default.json` fields into explicit `checks` while retaining the same expected values.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest backend/tests/test_rule_loader.py -q`
Expected: all loader tests pass.

- [ ] **Step 5: Run the existing backend suite**

Run: `python -m pytest backend -q`
Expected: existing tests plus loader tests pass with no warnings introduced by the loader.

---

### Task 2: Add Rule Engine and Error Factory

**Files:**
- Create: `backend/app/rules/engine.py`
- Create: `backend/app/rules/errors.py`
- Test: `backend/tests/test_rule_engine.py`

**Interfaces:**
- Produces `RuleEngine(document: Document, rules: RuleSet).run() -> list[ErrorItem]`.
- Produces `make_error(rule: CheckRule, *, location: str, content: str, current: str, expected: str) -> ErrorItem`.
- Detector registry maps `CheckRule.type` to callables with signature `(Document, CheckRule) -> list[ErrorItem]`.

- [ ] **Step 1: Write the failing tests**

```python
def test_engine_skips_disabled_rules_and_keeps_stable_error_ids():
    document = Document(document_id="D1", source_filename="x.docx")
    rules = RuleSet(schema_version="1.0", name="x", checks=[
        CheckRule(id="disabled", type="font", target="body", enabled=False, expected={}),
    ])
    assert RuleEngine(document, rules).run() == []

def test_error_factory_uses_frozen_error_contract():
    error = make_error(rule, location="p-0001", content="正文", current="黑体", expected="宋体")
    assert error.error_id == "body-font:p-0001"
    assert "required" not in error.model_dump()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest backend/tests/test_rule_engine.py -q`
Expected: FAIL because `RuleEngine` and `make_error` are not defined.

- [ ] **Step 3: Implement the engine and deterministic error IDs**

Register detectors by rule type, ignore disabled rules, raise a clear `ValueError` for an unknown enabled type, and build IDs from rule ID plus document location so repeated runs are deterministic.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest backend/tests/test_rule_engine.py -q`
Expected: all engine tests pass.

---

### Task 3: Implement Single-Item Formatting Detectors

**Files:**
- Create: `backend/app/rules/detectors.py`
- Modify: `backend/app/rules/engine.py`
- Test: `backend/tests/test_rule_detectors.py`

**Interfaces:**
- Produces detector types `font`, `size`, `alignment`, `line_spacing`, and `paragraph_indent`.
- Each detector compares only populated paragraph/run values against `rule.expected`; missing document values produce no false-positive error.

- [ ] **Step 1: Write the failing tests**

```python
def test_font_detector_reports_run_font_mismatch():
    document = document_with_paragraph(text="正文", font="黑体")
    rule = check_rule("body-font", "font", {"font": "宋体"})
    errors = detect_font(document, rule)
    assert len(errors) == 1
    assert errors[0].current == "黑体"
    assert errors[0].expected == "宋体"

def test_alignment_and_spacing_detectors_accept_matching_values():
    document = document_with_paragraph(alignment="justify", line_spacing=1.5)
    assert detect_alignment(document, check_rule("a", "alignment", {"alignment": "justify"})) == []
    assert detect_line_spacing(document, check_rule("s", "line_spacing", {"line_spacing": 1.5})) == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest backend/tests/test_rule_detectors.py -q`
Expected: FAIL because detector functions are not defined.

- [ ] **Step 3: Implement minimal detector functions and registry wiring**

Use paragraph IDs as locations, paragraph text as content, format values as current values, and stringified expected values. Support body/title targets through rule target matching without hard-coding a school-specific template.

- [ ] **Step 4: Run focused and full tests**

Run: `python -m pytest backend/tests/test_rule_detectors.py backend/tests/test_rule_engine.py -q`
Expected: all focused tests pass.

---

### Task 4: Implement Heading Numbering and TOC Consistency Checks

**Files:**
- Modify: `backend/app/rules/detectors.py`
- Modify: `backend/app/rules/engine.py`
- Test: `backend/tests/test_structure_detectors.py`

**Interfaces:**
- Produces detector types `heading_numbering` and `toc_consistency`.
- `heading_numbering` validates contiguous numeric labels within each heading level and reports the first discontinuity.
- `toc_consistency` compares `Document.metadata["toc_paragraphs"]` entries with heading text/levels and reports missing or extra entries.

- [ ] **Step 1: Write the failing tests**

```python
def test_heading_numbering_reports_gap():
    document = document_with_headings([("1", 1), ("3", 1)])
    errors = detect_heading_numbering(document, check_rule("heading", "heading_numbering", {}))
    assert errors[0].type == "heading_numbering_error"
    assert errors[0].current == "3"
    assert errors[0].expected == "2"

def test_toc_consistency_reports_missing_heading():
    document = document_with_headings([("1 引言", 1), ("2 方法", 1)], toc=[("1 引言", 1)])
    errors = detect_toc_consistency(document, check_rule("toc", "toc_consistency", {}))
    assert errors[0].type == "toc_consistency_error"
    assert "2 方法" in errors[0].content
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest backend/tests/test_structure_detectors.py -q`
Expected: FAIL because structural detectors are not implemented.

- [ ] **Step 3: Implement conservative structural checks**

Use parsed `paragraph["numbering"]["label"]` when present; otherwise skip numbering validation. Compare normalized heading text while preserving the original text in `content`; do not attempt unsupported Chinese-number or complex field reconstruction.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest backend/tests/test_structure_detectors.py -q`
Expected: all structure tests pass.

---

### Task 5: Implement Table/Figure and Reference-Baseline Checks

**Files:**
- Modify: `backend/app/rules/detectors.py`
- Modify: `backend/app/rules/engine.py`
- Test: `backend/tests/test_content_detectors.py`

**Interfaces:**
- Produces detector types `table_figure_format` and `reference_baseline`.
- `table_figure_format` checks only available outer metadata: table dimensions and drawing EMU dimensions/caption text.
- `reference_baseline` identifies paragraphs whose style/name/text indicate references and checks basic sequential labels such as `[1]`, `[2]`; it does not parse citation semantics.

- [ ] **Step 1: Write the failing tests**

```python
def test_table_figure_detector_reports_invalid_table_shape():
    document = document_with_tables([(1, 4)])
    rule = check_rule("table-shape", "table_figure_format", {"columns": 3})
    errors = detect_table_figure_format(document, rule)
    assert errors[0].current == "1x4"
    assert errors[0].expected == "columns=3"

def test_reference_detector_reports_numbering_gap():
    document = document_with_reference_paragraphs(["[1] A", "[3] C"])
    errors = detect_reference_baseline(document, check_rule("refs", "reference_baseline", {}))
    assert errors[0].current == "3"
    assert errors[0].expected == "2"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest backend/tests/test_content_detectors.py -q`
Expected: FAIL because content detectors are not implemented.

- [ ] **Step 3: Implement conservative outer-format and baseline checks**

Never inspect embedded Excel payloads; report only dimensions and parsed paragraph text already present in `Document`. Treat absent metadata as “not applicable” and return no error.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest backend/tests/test_content_detectors.py -q`
Expected: all content detector tests pass.

---

### Task 6: Expose Stage 2 Entry Point and Update Documentation

**Files:**
- Create: `backend/app/rules/service.py`
- Modify: `backend/app/rules/__init__.py`
- Modify: `rules/default.json`
- Modify: `rules/README.md`
- Modify: `product-context.md`
- Test: `backend/tests/test_rules_service.py`

**Interfaces:**
- Produces `check_document(document: Document, rules: RuleSet | str | Path | dict) -> list[ErrorItem]`.
- The service loads rules, runs all enabled detectors, and returns errors ordered by paragraph/table location then rule ID.

- [ ] **Step 1: Write the failing integration test**

```python
def test_check_document_runs_default_rules_end_to_end():
    document = document_with_paragraph(text="正文", font="黑体")
    errors = check_document(document, Path("rules/default.json"))
    assert any(error.type == "font_error" for error in errors)
    assert errors == sorted(errors, key=lambda error: (error.location, error.error_id))
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python -m pytest backend/tests/test_rules_service.py -q`
Expected: FAIL because the service entry point and stage 2 default rule wiring are absent.

- [ ] **Step 3: Implement service, default rules, and docs**

Export the public rule API from `backend.app.rules`, document the schema and supported detector types in `rules/README.md`, and update `product-context.md` to mark the implemented stage 2 slice, verification count, and remaining risks. Do not add an upload endpoint in this task.

- [ ] **Step 4: Run the complete verification suite**

Run: `python -m pytest backend -q`
Expected: all existing and new backend tests pass.

- [ ] **Step 5: Inspect the final diff and working tree**

Run: `git diff --check; git status --short`
Expected: no whitespace errors; only the planned backend/rules/docs files are modified or created.

---

## Execution Notes

Implement tasks in order. Each task must complete its red-green cycle before the next task begins. Keep the service pure and in-memory until a later phase explicitly defines API persistence and report integration. Before claiming completion, rerun the complete backend suite and verify the documented test count from fresh output.

# Structure Detection And Format Summary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 补齐封面/摘要/参考文献结构、页码解析、对应格式检测，以及人类可读的格式分析输出。

**Architecture:** 不改 `Document` 顶层冻结字段。结构写入段落 `structure`/`structure_role` 和 `metadata.structure`；页码写入 `pages`；可读格式由分析接口额外返回 `format_summary`/`format_text`。封面/摘要/图题/表题复用现有 font/size/alignment 检测器，仅扩展 target；页码和题注位置使用新检测器。

**Tech Stack:** Python 3.12、pytest、python-docx、FastAPI、React/Vitest。

**Spec:** `论文格式检测系统开发分工方案.md` 李维嘉模块缺口；`product-context.md` 冻结契约。

## Global Constraints

- 不新增 `Document`/`ErrorItem` 顶层字段，不使用 `required`。
- 没有摘要/参考文献标记时，不把普通正文误判为封面。
- 不持久化学生论文；规则只读内存 `Document`。
- 页码解析字段设置，不伪造 Word 排版后的实际页数。

---

### Task 1: Parser structure and pages

**Files:**
- Create: `backend/app/parser/structure.py`
- Create: `backend/app/parser/pages.py`
- Modify: `backend/app/parser/word_parser.py`
- Test: `backend/tests/test_word_parser.py`

- [x] **Step 1: Write failing tests** for cover/abstract/references/captions and PAGE fields.
- [x] **Step 2: Run focused tests and confirm they fail.**
- [x] **Step 3: Annotate document paragraphs and fill `pages`.**
- [x] **Step 4: Re-run parser tests.**

### Task 2: Detectors

**Files:**
- Modify: `backend/app/rules/detectors.py`
- Modify: `backend/app/rules/engine.py`
- Modify: `rules/default.json`
- Modify: `backend/app/services/location.py`
- Test: `backend/tests/test_rule_detectors.py`, `backend/tests/test_content_detectors.py`

- [x] **Step 1: Write failing tests** for cover/abstract targets, caption format/position, and page-number fields.
- [x] **Step 2: Confirm fail.**
- [x] **Step 3: Extend target matching and add `caption_position`/`page_number` detectors.**
- [x] **Step 4: Re-run detector tests.**

### Task 3: Readable format analysis

**Files:**
- Create: `backend/app/parser/format_summary.py`
- Modify: `backend/app/api/analysis.py`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/styles.css`
- Test: `backend/tests/test_detect.py`, `frontend/src/App.test.tsx`

- [x] **Step 1: Write failing tests** for `format_text` and frontend display.
- [x] **Step 2: Confirm fail.**
- [x] **Step 3: Return summary from analysis API and render it on the format analysis tab.**
- [x] **Step 4: Run backend and frontend tests.**

## Completion Record (2026-09-16)

- Backend regression: `151 passed, 1 warning`; pytest temporary data is isolated under `.verification-tmp/pytest-final`.
- Frontend regression: `npm.cmd test -- --run` passed (`2` files / `3` tests), and `npm.cmd run build` passed.
- The result screen now requests and displays `GET /api/v1/document/analysis/{task_id}`, so the user-visible route covers upload, detection, result, format analysis and PDF-report generation.
- False-positive regression coverage is retained in `backend/tests/test_detection_false_positives.py`, covering table cells, TOC entries, reference boundaries, East-Asian fonts and title/cover targeting.

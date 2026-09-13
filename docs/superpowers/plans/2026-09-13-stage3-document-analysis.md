# Stage 3 Document Analysis Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expose parsed document structure for a completed detection task through `GET /api/v1/document/analysis/{task_id}`.

**Architecture:** Store the parsed `Document` alongside detection errors in the in-memory `TaskRecord`. The detection pipeline returns both the parsed document and relocated errors, while the existing result endpoint remains backward compatible. A dedicated analysis router reads the task record and returns the stable `Document` contract.

**Tech Stack:** FastAPI, Pydantic, Python, pytest.

**Spec:** `product-context.md` and `论文格式检测系统接口设计文档_V1.0_.md` stage 3 endpoint definition.

## Global Constraints

- Do not persist student paper content beyond the in-memory task lifecycle.
- Reuse the existing `Document` and `ErrorItem` contracts.
- Unknown tasks return HTTP 404; incomplete tasks return HTTP 409; failed parsing returns HTTP 400.

---

### Task 1: Persist Parsed Documents

**Files:**
- Modify: `backend/app/services/task_store.py`
- Modify: `backend/app/services/pipeline.py`
- Modify: `backend/app/api/detect.py`
- Test: `backend/tests/test_detect.py`

- [ ] **Step 1: Write failing test** asserting a completed task exposes parsed document data through its record.
- [ ] **Step 2: Run the focused test and confirm it fails because no document is stored.**
- [ ] **Step 3: Add `document: Document | None` to `TaskRecord`; change the pipeline to return `(Document, list[ErrorItem])`; store both values in `start_detect`.**
- [ ] **Step 4: Run focused tests and confirm existing detection behavior remains green.**

### Task 2: Add Document Analysis API

**Files:**
- Create: `backend/app/api/analysis.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_analysis.py`

- [ ] **Step 1: Write failing endpoint tests for completed, missing, incomplete, and failed tasks.**
- [ ] **Step 2: Run the focused tests and confirm the route is missing.**
- [ ] **Step 3: Implement the router and register it under `/api/v1`; return `{code, message, data: {task_id, filename, status, document}}`.**
- [ ] **Step 4: Run all backend tests.**

### Task 3: Self-Review and Verification

**Files:**
- Review: all files changed in Tasks 1-2

- [ ] **Step 1: Inspect the diff for contract compatibility, lifecycle leakage, and error-state handling.**
- [ ] **Step 2: Run the complete test suite and syntax/import checks.**
- [ ] **Step 3: Record residual risks, especially process-local task storage and document retention semantics.**

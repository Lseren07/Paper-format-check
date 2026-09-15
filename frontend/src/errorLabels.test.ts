import { describe, expect, it } from "vitest";

import rules from "../../rules/default.json";
import { ERROR_TYPE_LABELS } from "./App";

/**
 * 后端 `rules/errors.py` 对这几个规则类型用的是专门命名，其余一律 `${type}_error`。
 * 引擎支持的完整类型见 `backend/app/rules/engine.py` 的 DETECTORS。
 */
const ERROR_TYPE_OVERRIDES: Record<string, string> = {
  font: "font_error",
  size: "size_error",
  bold: "bold_error",
  alignment: "alignment_error",
  line_spacing: "line_spacing_error",
  paragraph_indent: "paragraph_indent_error",
};

describe("error type labels", () => {
  it("covers every check type the default ruleset can emit", () => {
    const errorTypes = [
      ...new Set(
        rules.checks.map((check) => ERROR_TYPE_OVERRIDES[check.type] ?? `${check.type}_error`),
      ),
    ];

    // 漏掉标签的类型会以英文原始串显示在问题卡片标题上
    expect(errorTypes.filter((errorType) => !(errorType in ERROR_TYPE_LABELS))).toEqual([]);
  });
});

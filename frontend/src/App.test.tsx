import "@testing-library/jest-dom/vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import App from "./App";

describe("paper detection flow", () => {
  beforeEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("renders the upload page with detect button disabled", () => {
    render(<App />);

    expect(screen.getByRole("heading", { name: "师鉴通" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "开始检测" })).toBeDisabled();
  });

  it("uploads a file, runs detection, and shows the result page", async () => {
    const user = userEvent.setup();
    const fetchMock = vi.fn()
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ code: 200, data: { task_id: "T123", filename: "thesis.docx", status: "uploaded" } }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ code: 200, data: { task_id: "T123", status: "completed" } }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          code: 200,
          data: {
            task_id: "T123",
            filename: "thesis.docx",
            status: "completed",
            total_error: 1,
            errors: [{
              error_id: "body-font:p-0001:run-0001",
              type: "font_error",
              location: "第二章 系统设计",
              content: "随着人工智能技术的发展",
              current: "黑体",
              expected: "宋体",
            }],
          },
        }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          code: 200,
          data: {
            task_id: "T123",
            format_text: "正文格式：字体：宋体；字号：小四。",
            format_summary: {},
          },
        }),
      });
    vi.stubGlobal("fetch", fetchMock);

    render(<App />);
    const input = screen.getByLabelText("选择 DOCX 文件");
    const file = new File(["dummy"], "thesis.docx", {
      type: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    });
    await user.upload(input, file);
    await user.click(screen.getByRole("button", { name: "开始检测" }));

    expect(await screen.findByRole("heading", { name: "检测结果" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "共 1 个格式问题" })).toBeInTheDocument();
    expect(screen.getByText("字体错误")).toBeInTheDocument();
    expect(screen.getByText("第二章 系统设计")).toBeInTheDocument();
    expect(screen.getByText("随着人工智能技术的发展")).toBeInTheDocument();
    expect(screen.getByText("黑体")).toBeInTheDocument();
    expect(screen.getByText("宋体")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "格式分析" })).toBeInTheDocument();
    expect(screen.getByText("正文格式：字体：宋体；字号：小四。")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledTimes(4);
    expect(fetchMock.mock.calls[0][0]).toBe("/api/v1/paper/upload");
    expect(fetchMock.mock.calls[1][0]).toBe("/api/v1/detect/start");
    expect(fetchMock.mock.calls[2][0]).toBe("/api/v1/detect/result/T123");
    expect(fetchMock.mock.calls[3][0]).toBe("/api/v1/document/analysis/T123");
  });
});


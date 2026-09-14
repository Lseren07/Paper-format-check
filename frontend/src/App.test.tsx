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

    expect(screen.getByRole("heading", { name: "开始一次新的格式检查" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "开始格式检查　→" })).toBeDisabled();
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
            filename: "thesis.docx",
            status: "completed",
            format_text: "\u6b63\u6587\u683c\u5f0f\uff1a\n\u5b57\u4f53\uff1a\u5b8b\u4f53\n\u5b57\u53f7\uff1a\u5c0f\u56db\n\u884c\u8ddd\uff1a1.5\u500d",
            format_summary: { body: { font: "\u5b8b\u4f53", size: "\u5c0f\u56db", line_spacing: "1.5\u500d" } },
            document: {
              schema_version: "1.0",
              document_id: "T123",
              source_filename: "thesis.docx",
              metadata: { title: "测试论文", author: "张三" },
              sections: [{ title: "第一章 绪论", level: 1 }],
              paragraphs: [{ index: 1, text: "正文内容", style: "Normal" }],
              tables: [{ index: 1, rows: 2, columns: 3 }],
              headers: [],
              footers: [],
              pages: [{ number: 1, width: 210, height: 297 }],
            },
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
    await user.click(screen.getByRole("button", { name: "开始格式检查　→" }));

    expect(await screen.findByRole("heading", { name: "检测结果" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "共 1 个格式问题" })).toBeInTheDocument();
    expect(screen.getByText("字体错误")).toBeInTheDocument();
    expect(screen.getByText("第二章 系统设计")).toBeInTheDocument();
    expect(screen.getByText("随着人工智能技术的发展")).toBeInTheDocument();
    expect(screen.getByText("黑体")).toBeInTheDocument();
    expect(screen.getByText("宋体")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledTimes(4);
    expect(fetchMock.mock.calls[0][0]).toBe("/api/v1/paper/upload");
    expect(fetchMock.mock.calls[1][0]).toBe("/api/v1/detect/start");
    expect(fetchMock.mock.calls[2][0]).toBe("/api/v1/detect/result/T123");
    expect(fetchMock.mock.calls[3][0]).toBe("/api/v1/document/analysis/T123");
    expect(screen.getByRole("tab", { name: "格式分析" })).toBeInTheDocument();

    await user.click(screen.getByRole("tab", { name: "格式分析" }));
    expect(screen.getByText("测试论文")).toBeInTheDocument();
    expect(screen.getByText("第一章 绪论")).toBeInTheDocument();
    expect(screen.getByText("2 × 3")).toBeInTheDocument();
    expect(screen.getByText(/正文格式/)).toBeInTheDocument();
    expect(screen.getByText(/字体：宋体/)).toBeInTheDocument();
  });

  it("shows an analysis error next to the format analysis view", async () => {
    const user = userEvent.setup();
    const fetchMock = vi.fn()
      .mockResolvedValueOnce({ ok: true, json: async () => ({ data: { task_id: "T1" } }) })
      .mockResolvedValueOnce({ ok: true, json: async () => ({ data: { status: "completed" } }) })
      .mockResolvedValueOnce({ ok: true, json: async () => ({ data: { filename: "a.docx", total_error: 0, errors: [] } }) })
      .mockResolvedValueOnce({ ok: false, json: async () => ({ detail: "分析服务不可用" }) });
    vi.stubGlobal("fetch", fetchMock);
    render(<App />);
    await user.upload(screen.getByLabelText("选择 DOCX 文件"), new File(["x"], "a.docx"));
    await user.click(screen.getByRole("button", { name: "开始格式检查　→" }));
    await user.click(await screen.findByRole("tab", { name: "格式分析" }));
    expect(await screen.findByText("分析服务不可用")).toBeInTheDocument();
  });
});


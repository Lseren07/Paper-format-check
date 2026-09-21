import "@testing-library/jest-dom/vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import App from "./App";

function stubDetection(errors: unknown[]) {
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
          total_error: errors.length,
          errors,
        },
      }),
    })
    .mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        code: 200,
        data: { task_id: "T123", format_text: "正文格式：字体：宋体；字号：小四。", format_summary: {} },
      }),
    });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

async function uploadAndDetect(buttonName = "开始检测") {
  const user = userEvent.setup();
  render(<App />);
  const input = screen.getByLabelText("选择 DOCX 文件");
  const file = new File(["dummy"], "thesis.docx", {
    type: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
  });
  await user.upload(input, file);
  await user.click(screen.getByRole("button", { name: buttonName }));
  return user;
}

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
    const fetchMock = stubDetection([{
      error_id: "body-font:p-0001:run-0001",
      type: "font_error",
      location: "第二章 系统设计",
      content: "随着人工智能技术的发展",
      current: "黑体",
      expected: "宋体",
    }]);

    await uploadAndDetect();

    expect(await screen.findByRole("heading", { name: "检测结果" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "共 1 个格式问题" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "字体错误" })).toBeInTheDocument();
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

    // 结果页按钮应在错误列表之前（避免错误多时被顶到页面很深处）
    const resultHeading = screen.getByRole("heading", { name: "检测结果" });
    const downloadButton = screen.getByRole("button", { name: "下载 PDF 报告" });
    const firstErrorTitle = screen.getByRole("heading", { name: "字体错误" });
    expect(
      resultHeading.compareDocumentPosition(downloadButton) & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
    expect(
      downloadButton.compareDocumentPosition(firstErrorTitle) & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
  });

  it("shows backend units as-is instead of appending a guessed one", async () => {
    stubDetection([{
      error_id: "body-line-spacing:p-0002:x",
      type: "line_spacing_error",
      location: "第一章 引言",
      content: "正文段落",
      current: "1.1倍",
      expected: "20磅",
    }]);

    await uploadAndDetect();

    expect(await screen.findByText("1.1倍")).toBeInTheDocument();
    expect(screen.getByText("20磅")).toBeInTheDocument();
  });

  it("translates internal status markers instead of leaking them", async () => {
    stubDetection([
      {
        error_id: "toc:p-0003:x",
        type: "toc_consistency_error",
        location: "目录",
        content: "1.1 研究背景",
        current: "missing",
        expected: "level=2",
      },
      {
        error_id: "body-alignment:p-0004:x",
        type: "alignment_error",
        location: "第一章 引言",
        content: "随着人工智能技术的发展",
        current: "center",
        expected: "justify",
      },
    ]);

    await uploadAndDetect();

    expect(await screen.findByText("缺失")).toBeInTheDocument();
    expect(screen.getByText("第 2 级")).toBeInTheDocument();
    expect(screen.getByText("居中")).toBeInTheDocument();
    expect(screen.getByText("两端对齐")).toBeInTheDocument();
    expect(screen.queryByText("missing")).not.toBeInTheDocument();
    expect(screen.queryByText("justify")).not.toBeInTheDocument();
  });

  it("downloads PDF and Markdown reports from their respective URLs", async () => {
    const fetchMock = stubDetection([]);
    const user = await uploadAndDetect();
    const blob = new Blob(["report"]);
    vi.stubGlobal("URL", {
      createObjectURL: vi.fn(() => "blob:report"),
      revokeObjectURL: vi.fn(),
    });
    const anchor = document.createElement("a");
    vi.spyOn(anchor, "click").mockImplementation(() => undefined);
    vi.spyOn(anchor, "remove").mockImplementation(() => undefined);
    const createElement = document.createElement.bind(document);
    vi.spyOn(document, "createElement").mockImplementation((tagName: string) =>
      tagName === "a" ? anchor : createElement(tagName),
    );
    fetchMock
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ data: {
          filename: "thesis_格式检测报告.pdf",
          markdown_filename: "thesis_格式检测报告.md",
          download_url: "/api/v1/report/download/RT123",
          markdown_download_url: "/api/v1/report/download/RT123/markdown",
        } }),
      })
      .mockResolvedValueOnce({ ok: true, blob: async () => blob });
    await user.click(screen.getByRole("button", { name: "下载 PDF 报告" }));
    expect(fetchMock.mock.calls[4][0]).toBe("/api/v1/report/create");
    expect(fetchMock.mock.calls[5][0]).toBe("/api/v1/report/download/RT123");
    expect(anchor.download).toBe("thesis_格式检测报告.pdf");

    fetchMock
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ data: {
          filename: "thesis_格式检测报告.pdf",
          markdown_filename: "thesis_格式检测报告.md",
          download_url: "/api/v1/report/download/RT123",
          markdown_download_url: "/api/v1/report/download/RT123/markdown",
        } }),
      })
      .mockResolvedValueOnce({ ok: true, blob: async () => blob });
    await user.click(screen.getByRole("button", { name: "下载 Markdown 报告" }));
    expect(fetchMock.mock.calls[6][0]).toBe("/api/v1/report/create");
    expect(fetchMock.mock.calls[7][0]).toBe("/api/v1/report/download/RT123/markdown");
    expect(anchor.download).toBe("thesis_格式检测报告.md");
  });

  it("filters by type and paginates through long result lists", async () => {
    const errors = Array.from({ length: 25 }, (_, index) => ({
      error_id: `font_error:p-${index}:x`,
      type: "font_error",
      location: `第${index}段`,
      content: `文本${index}`,
      current: "黑体",
      expected: "宋体",
    }));
    errors.push({
      error_id: "size_error:p-99:x",
      type: "size_error",
      location: "第二章",
      content: "标题",
      current: "14",
      expected: "12",
    });
    stubDetection(errors);

    const user = await uploadAndDetect();

    expect(await screen.findByRole("heading", { name: "共 26 个格式问题" })).toBeInTheDocument();
    // 26 条按每页 20 条切分，第一页满 20 张卡片
    expect(screen.getAllByRole("listitem")).toHaveLength(20);
    expect(screen.getByText("第 1 / 2 页")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "下一页" }));
    expect(screen.getAllByRole("listitem")).toHaveLength(6);
    expect(screen.getByText("第 2 / 2 页")).toBeInTheDocument();

    // 切到某一类型后回到第一页，只显示该类型
    await user.selectOptions(screen.getByLabelText(/按类型筛选/), "size_error");
    expect(screen.getByText("第 1 / 1 页")).toBeInTheDocument();
    expect(screen.getAllByRole("listitem")).toHaveLength(1);
    expect(screen.getByRole("heading", { name: "字号错误" })).toBeInTheDocument();
  });
});

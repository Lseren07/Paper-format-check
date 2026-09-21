import { useMemo, useState } from "react";
import { BrandMark, ScanningMark } from "./components/Brand";

type ErrorItem = {
  error_id: string;
  type: string;
  location: string;
  content: string;
  current: string;
  expected: string;
};

type DetectResult = {
  task_id: string;
  filename: string;
  status: string;
  total_error: number;
  errors: ErrorItem[];
};

type FormatAnalysis = {
  format_text: string;
};

export const ERROR_TYPE_LABELS: Record<string, string> = {
  font_error: "字体错误",
  size_error: "字号错误",
  bold_error: "加粗错误",
  alignment_error: "对齐错误",
  line_spacing_error: "行距错误",
  paragraph_indent_error: "缩进错误",
  paragraph_spacing_error: "段落间距错误",
  heading_numbering_error: "标题编号错误",
  toc_consistency_error: "目录一致性错误",
  table_figure_format_error: "图表格式错误",
  reference_baseline_error: "参考文献格式错误",
  page_margin_error: "页边距错误",
  required_sections_error: "必备结构缺失",
  keyword_format_error: "关键词格式错误",
  caption_format_error: "题注格式错误",
  caption_position_error: "题注位置错误",
  header_text_error: "页眉文字错误",
  page_number_error: "页码错误",
};

// 后端在部分规则里用简写标记状态（missing、level=2、upperRoman 等），
// 这些是内部取值，不能直接端到用户面前。
const VALUE_LABELS: Record<string, string> = {
  missing: "缺失",
  "missing-drawing": "缺图",
  "missing-table": "缺表",
  drawing: "有图",
  table: "有表",
  none: "未设置",
  "no extra entry": "不应存在",
  "page field": "页码域",
  default: "默认",
  decimal: "阿拉伯数字",
  upperRoman: "大写罗马数字",
  lowerRoman: "小写罗马数字",
  upperLetter: "大写字母",
  lowerLetter: "小写字母",
  header: "页眉",
  footer: "页脚",
  header_footer: "页眉或页脚",
  // 对齐来自 python-docx 的枚举名，样式继承与段落直接格式都会走到这里
  left: "左对齐",
  center: "居中",
  right: "右对齐",
  justify: "两端对齐",
  distribute: "分散对齐",
  below: "下方",
  above: "上方",
};

const PAGE_SIZE = 20;

function errorTypeLabel(type: string): string {
  return ERROR_TYPE_LABELS[type] ?? "格式问题";
}

function displayValue(value: string): string {
  if (!value) return "（未提供）";
  const label = VALUE_LABELS[value];
  if (label) return label;
  const level = /^level=(\d+)$/.exec(value);
  if (level) return `第 ${level[1]} 级`;
  return value;
}

export default function App() {
  const [file, setFile] = useState<File | null>(null);
  const [status, setStatus] = useState("待检测");
  const [message, setMessage] = useState("");
  const [result, setResult] = useState<DetectResult | null>(null);
  const [analysis, setAnalysis] = useState<FormatAnalysis | null>(null);
  const [inputKey, setInputKey] = useState(0);
  const [filter, setFilter] = useState("all");
  const [page, setPage] = useState(1);
  const [reportStatus, setReportStatus] = useState<"idle" | "generating" | "error">("idle");
  const [reportMessage, setReportMessage] = useState("");

  async function startDetection() {
    if (!file) return;
    setStatus("检测中");
    setMessage("");
    const formData = new FormData();
    formData.append("file", file);
    try {
      const uploadResponse = await fetch("/api/v1/paper/upload", { method: "POST", body: formData });
      const uploadBody = await uploadResponse.json();
      if (!uploadResponse.ok) {
        throw new Error(uploadBody.detail ?? "上传失败");
      }
      const taskId = uploadBody.data.task_id as string;
      const startResponse = await fetch("/api/v1/detect/start", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ task_id: taskId }),
      });
      const startBody = await startResponse.json();
      if (!startResponse.ok) {
        throw new Error(startBody.detail ?? "检测失败");
      }
      if (startBody.data?.status === "failed") {
        throw new Error(startBody.message ?? "检测失败");
      }
      const resultResponse = await fetch(`/api/v1/detect/result/${taskId}`);
      const resultBody = await resultResponse.json();
      if (!resultResponse.ok) {
        throw new Error(resultBody.detail ?? "获取检测结果失败");
      }
      setResult(resultBody.data);
      const analysisResponse = await fetch(`/api/v1/document/analysis/${taskId}`);
      const analysisBody = await analysisResponse.json();
      if (!analysisResponse.ok) {
        throw new Error(analysisBody.detail ?? "获取格式分析失败");
      }
      setAnalysis(analysisBody.data);
      setStatus("检测完成");
    } catch (error) {
      setStatus("检测失败");
      setMessage(error instanceof Error ? error.message : "无法连接后端服务");
    }
  }

  function backToUpload() {
    setFile(null);
    setStatus("待检测");
    setMessage("");
    setResult(null);
    setAnalysis(null);
    setFilter("all");
    setPage(1);
    setReportStatus("idle");
    setReportMessage("");
    setInputKey((value) => value + 1);
  }

  async function downloadReport(format: "pdf" | "markdown") {
    if (!result || reportStatus === "generating") return;
    setReportStatus("generating");
    setReportMessage("");
    try {
      const createResponse = await fetch("/api/v1/report/create", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ task_id: result.task_id }),
      });
      const createBody = await createResponse.json();
      if (!createResponse.ok) throw new Error(createBody.detail ?? "报告生成失败");

      const reportData = createBody.data ?? {};
      const downloadUrl = format === "markdown"
        ? reportData.markdown_download_url
        : reportData.download_url;
      if (!downloadUrl) throw new Error("报告下载地址缺失");
      const downloadResponse = await fetch(downloadUrl);
      if (!downloadResponse.ok) {
        const body = await downloadResponse.json().catch(() => ({}));
        throw new Error(body.detail ?? "报告下载失败");
      }
      const blob = await downloadResponse.blob();
      const objectUrl = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = objectUrl;
      anchor.download = format === "markdown"
        ? reportData.markdown_filename ?? "格式检测报告.md"
        : reportData.filename ?? "格式检测报告.pdf";
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      URL.revokeObjectURL(objectUrl);
      setReportStatus("idle");
    } catch (error) {
      setReportStatus("error");
      setReportMessage(error instanceof Error ? error.message : "报告下载失败");
    }
  }

  const types = useMemo(
    () => [...new Set(result?.errors.map((item) => item.type) ?? [])],
    [result],
  );
  const filtered = result?.errors.filter((item) => filter === "all" || item.type === filter) ?? [];
  const pages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const visible = filtered.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);

  if (result) {
    return (
      <main className="shell">
        <header className="hero compact">
          <BrandMark size={48} />
          <h1>检测结果</h1>
          <p className="sub">{result.filename} 已完成格式检测。</p>
        </header>
        <section className="panel">
          <h2>共 {result.total_error} 个格式问题</h2>
          {/* 按钮放在错误列表之前：问题多时列表会把按钮顶到很深的位置 */}
          <div className="result-actions">
            <button type="button" onClick={() => downloadReport("pdf")} disabled={reportStatus === "generating"}>
              {reportStatus === "generating" ? "正在生成报告" : "下载 PDF 报告"}
            </button>
            <button type="button" onClick={() => downloadReport("markdown")} disabled={reportStatus === "generating"}>
              {reportStatus === "generating" ? "正在生成报告" : "下载 Markdown 报告"}
            </button>
            <button type="button" className="secondary-button" onClick={backToUpload}>返回上传</button>
          </div>
          {reportMessage && <p className="error">{reportMessage}</p>}
          {result.errors.length > 0 && (
            <div className="result-toolbar">
              <label htmlFor="error-filter">
                按类型筛选
                <select
                  id="error-filter"
                  value={filter}
                  onChange={(event) => {
                    setFilter(event.target.value);
                    setPage(1);
                  }}
                >
                  <option value="all">全部（{result.errors.length}）</option>
                  {types.map((type) => (
                    <option key={type} value={type}>
                      {errorTypeLabel(type)}
                    </option>
                  ))}
                </select>
              </label>
              <span className="muted">
                第 {page} / {pages} 页
              </span>
            </div>
          )}
          {result.errors.length === 0 ? (
            <p className="muted">未发现格式问题。</p>
          ) : visible.length === 0 ? (
            <p className="muted">当前筛选条件下没有格式问题。</p>
          ) : (
            <ul className="error-list">
              {visible.map((error) => (
                <li key={error.error_id} className="error-card">
                  <h3>{errorTypeLabel(error.type)}</h3>
                  <dl>
                    <div>
                      <dt>位置</dt>
                      <dd>{error.location || "（无位置）"}</dd>
                    </div>
                    <div>
                      <dt>文本</dt>
                      <dd>{error.content || "（无文本）"}</dd>
                    </div>
                    <div>
                      <dt>当前格式</dt>
                      <dd>{displayValue(error.current)}</dd>
                    </div>
                    <div>
                      <dt>规范要求</dt>
                      <dd>{displayValue(error.expected)}</dd>
                    </div>
                  </dl>
                </li>
              ))}
            </ul>
          )}
          {pages > 1 && (
            <nav className="pagination">
              <button type="button" disabled={page === 1} onClick={() => setPage(page - 1)}>
                上一页
              </button>
              <button type="button" disabled={page === pages} onClick={() => setPage(page + 1)}>
                下一页
              </button>
            </nav>
          )}
          {analysis?.format_text && (
            <section className="analysis-card" aria-label="格式分析">
              <h2>格式分析</h2>
              <p>{analysis.format_text}</p>
            </section>
          )}
        </section>
      </main>
    );
  }

  return (
    <main className="shell">
      <header className="hero">
        <BrandMark size={88} />
        <h1>师鉴通</h1>
        <p className="slogan">论文格式智能检测</p>
        <p className="sub">上传 Word 论文后，系统会按学校规范检查字体、字号、段落与页面格式。</p>
      </header>
      <section className="panel">
        <h2>上传论文</h2>
        <p className="muted">当前版本接受有效的 DOCX 文件，单文件最大 50 MB。</p>
        <label className="dropzone">
          <input
            key={inputKey}
            type="file"
            accept=".docx"
            aria-label="选择 DOCX 文件"
            onChange={(event) => setFile(event.target.files?.[0] ?? null)}
          />
          <strong>{file ? file.name : "选择 DOCX 文件"}</strong>
          <span>{file ? `${(file.size / 1024 / 1024).toFixed(2)} MB` : "文件只保存在本地 uploads 目录"}</span>
        </label>
        <button type="button" disabled={!file || status === "检测中"} onClick={startDetection}>
          {status === "检测中" ? "正在鉴测" : "开始检测"}
        </button>
        <div className="status-row">
          {status === "检测中" && <ScanningMark size={64} />}
          <p className={`status ${status === "检测失败" ? "error" : ""}`}>{status}</p>
        </div>
        {message && <p className="error">{message}</p>}
      </section>
    </main>
  );
}

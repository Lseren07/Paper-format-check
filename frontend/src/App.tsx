import { useState } from "react";
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

function errorTypeLabel(type: string): string {
  return ERROR_TYPE_LABELS[type] ?? type;
}

export default function App() {
  const [file, setFile] = useState<File | null>(null);
  const [status, setStatus] = useState("待检测");
  const [message, setMessage] = useState("");
  const [result, setResult] = useState<DetectResult | null>(null);
  const [inputKey, setInputKey] = useState(0);
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
    setReportStatus("idle");
    setReportMessage("");
    setInputKey((value) => value + 1);
  }

  async function downloadReport() {
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

      const downloadUrl = createBody.data?.download_url as string | undefined;
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
      anchor.download = createBody.data.filename ?? "格式检测报告.pdf";
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
          {result.errors.length === 0 ? (
            <p className="muted">未发现格式问题。</p>
          ) : (
            <ul className="error-list">
              {result.errors.map((error) => (
                <li key={error.error_id} className="error-card">
                  <h3>{errorTypeLabel(error.type)}</h3>
                  <dl>
                    <div>
                      <dt>位置</dt>
                      <dd>{error.location}</dd>
                    </div>
                    <div>
                      <dt>文本</dt>
                      <dd>{error.content || "（无文本）"}</dd>
                    </div>
                    <div>
                      <dt>当前格式</dt>
                      <dd>{error.current}</dd>
                    </div>
                    <div>
                      <dt>规范要求</dt>
                      <dd>{error.expected}</dd>
                    </div>
                  </dl>
                </li>
              ))}
            </ul>
          )}
          <div className="result-actions">
            <button type="button" onClick={downloadReport} disabled={reportStatus === "generating"}>
              {reportStatus === "generating" ? "正在生成报告" : "下载 PDF 报告"}
            </button>
            <button type="button" className="secondary-button" onClick={backToUpload}>返回上传</button>
          </div>
          {reportMessage && <p className="error">{reportMessage}</p>}
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

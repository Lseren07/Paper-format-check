import { useState } from "react";

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

const ERROR_TYPE_LABELS: Record<string, string> = {
  font_error: "字体错误",
  size_error: "字号错误",
  bold_error: "加粗错误",
  alignment_error: "对齐错误",
  line_spacing_error: "行距错误",
  paragraph_indent_error: "缩进错误",
  heading_numbering_error: "标题编号错误",
  toc_consistency_error: "目录一致性错误",
  table_figure_format_error: "图表格式错误",
  reference_baseline_error: "参考文献格式错误",
  page_margin_error: "页边距错误",
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
    setInputKey((value) => value + 1);
  }

  if (result) {
    return (
      <main className="shell">
        <header>
          <span className="eyebrow">PAPER CHECKER</span>
          <h1>检测结果</h1>
          <p>{result.filename} 已完成格式检测。</p>
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
          <button type="button" onClick={backToUpload}>返回上传</button>
        </section>
      </main>
    );
  }

  return (
    <main className="shell">
      <header>
        <span className="eyebrow">PAPER CHECKER</span>
        <h1>论文格式检测系统</h1>
        <p>上传 Word 论文后，系统会按学校规范检查字体、字号、段落与页面格式。</p>
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
          开始检测
        </button>
        <p className={`status ${status === "检测失败" ? "error" : ""}`}>{status}</p>
        {message && <p className="error">{message}</p>}
      </section>
    </main>
  );
}

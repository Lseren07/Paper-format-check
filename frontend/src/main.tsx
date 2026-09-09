import { StrictMode, useState } from "react";
import { createRoot } from "react-dom/client";
import "./styles.css";

type UploadResult = { task_id: string; filename: string; size: number; status: string };

function App() {
  const [file, setFile] = useState<File | null>(null);
  const [status, setStatus] = useState("待上传");
  const [message, setMessage] = useState("");
  const [result, setResult] = useState<UploadResult | null>(null);

  async function uploadFile() {
    if (!file) return;
    setStatus("上传中"); setMessage(""); setResult(null);
    const formData = new FormData(); formData.append("file", file);
    try {
      const response = await fetch("/api/v1/paper/upload", { method: "POST", body: formData });
      const body = await response.json();
      if (!response.ok) throw new Error(body.detail ?? "上传失败");
      setResult(body.data); setStatus("上传成功");
    } catch (error) {
      setStatus("上传失败");
      setMessage(error instanceof Error ? error.message : "无法连接后端服务");
    }
  }

  return <main className="shell">
    <header><span className="eyebrow">PAPER CHECKER</span><h1>论文格式检测</h1><p>本地上传入口已连接后端，检测规则功能正在建设中。</p></header>
    <section className="panel">
      <h2>上传论文</h2><p className="muted">当前版本接受有效的 DOCX 文件，单文件最大 50 MB。</p>
      <label className="dropzone"><input type="file" accept=".docx" onChange={(event) => setFile(event.target.files?.[0] ?? null)} /><strong>{file ? file.name : "选择 DOCX 文件"}</strong><span>{file ? `${(file.size / 1024 / 1024).toFixed(2)} MB` : "文件只保存在本地 uploads 目录"}</span></label>
      <button type="button" disabled={!file || status === "上传中"} onClick={uploadFile}>开始上传</button>
      <p className={`status ${status === "上传失败" ? "error" : ""}`}>{status}</p>
      {message && <p className="error">{message}</p>}
      {result && <div className="result"><b>任务编号</b><code>{result.task_id}</code><span>文件已保存，格式检测任务尚未启动。</span></div>}
    </section>
  </main>;
}

createRoot(document.getElementById("root")!).render(<StrictMode><App /></StrictMode>);

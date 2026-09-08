export default function App() {
  return (
    <main className="app-shell">
      <section className="status-panel" aria-labelledby="app-title">
        <p className="eyebrow">论文格式检测</p>
        <h1 id="app-title">论文格式检测系统</h1>
        <p className="description">上传论文后检查标题、字体、段落与页面格式。</p>
        <dl className="system-status" aria-label="系统状态">
          <div>
            <dt>接口版本</dt>
            <dd>API v1</dd>
          </div>
          <div>
            <dt>后端状态</dt>
            <dd>后端服务待连接</dd>
          </div>
        </dl>
      </section>
    </main>
  );
}

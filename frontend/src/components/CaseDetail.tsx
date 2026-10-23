import { useEffect, useState } from "react";

type ProjectCase = {
  case_id: string;
  title: string;
  description: string;
  school: string;
  file_count: number;
  error_rate: number;
  created_at: string;
  thumbnail_url?: string;
  tags: string[];
};

type CaseDetailProps = {
  caseId: string;
  onBack: () => void;
};

export function CaseDetail({ caseId, onBack }: CaseDetailProps) {
  const [caseData, setCaseData] = useState<ProjectCase | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    async function fetchCaseDetail() {
      try {
        const response = await fetch(`/api/v1/cases/${caseId}`);
        const body = await response.json();
        if (!response.ok) {
          throw new Error(body.detail ?? "获取案例详情失败");
        }
        setCaseData(body.data);
      } catch (err) {
        setError(err instanceof Error ? err.message : "无法加载案例详情");
      } finally {
        setLoading(false);
      }
    }
    fetchCaseDetail();
  }, [caseId]);

  if (loading) {
    return (
      <main className="shell">
        <section className="panel">
          <p className="muted">正在加载案例详情...</p>
        </section>
      </main>
    );
  }

  if (error || !caseData) {
    return (
      <main className="shell">
        <section className="panel">
          <p className="error">{error || "案例不存在"}</p>
          <button type="button" onClick={onBack}>返回列表</button>
        </section>
      </main>
    );
  }

  const createdDate = new Date(caseData.created_at).toLocaleString("zh-CN");

  return (
    <main className="shell">
      <header className="hero compact">
        <h1>{caseData.title}</h1>
        <p className="sub">{caseData.school}</p>
      </header>
      <section className="panel">
        <div className="result-actions">
          <button type="button" className="secondary-button" onClick={onBack}>
            返回列表
          </button>
        </div>

        {caseData.thumbnail_url && (
          <div className="case-detail-thumbnail">
            <img src={caseData.thumbnail_url} alt={caseData.title} />
          </div>
        )}

        <div className="case-detail-section">
          <h2>案例描述</h2>
          <p>{caseData.description}</p>
        </div>

        <div className="case-detail-section">
          <h2>完成情况</h2>
          <dl className="case-detail-stats">
            <div>
              <dt>文件数量</dt>
              <dd>{caseData.file_count} 个</dd>
            </div>
            <div>
              <dt>错误率</dt>
              <dd className={caseData.error_rate > 0.1 ? "error" : "success"}>
                {(caseData.error_rate * 100).toFixed(1)}%
              </dd>
            </div>
            <div>
              <dt>创建时间</dt>
              <dd>{createdDate}</dd>
            </div>
          </dl>
        </div>

        {caseData.tags.length > 0 && (
          <div className="case-detail-section">
            <h2>标签</h2>
            <div className="case-tags">
              {caseData.tags.map((tag) => (
                <span key={tag} className="tag">{tag}</span>
              ))}
            </div>
          </div>
        )}

        <div className="case-detail-section">
          <h2>评估内容</h2>
          <div className="evaluation-content">
            <div className="evaluation-item">
              <h3>文件处理能力</h3>
              <p>
                该案例共处理 <strong>{caseData.file_count}</strong> 个文件，
                展示了系统的批量处理能力。
              </p>
            </div>
            <div className="evaluation-item">
              <h3>准确性评估</h3>
              <p>
                错误率为 <strong>{(caseData.error_rate * 100).toFixed(1)}%</strong>
                {caseData.error_rate < 0.05 && "，表现优秀"}
                {caseData.error_rate >= 0.05 && caseData.error_rate < 0.1 && "，表现良好"}
                {caseData.error_rate >= 0.1 && "，需要进一步优化"}
                。
              </p>
            </div>
            <div className="evaluation-item">
              <h3>应用场景</h3>
              <p>
                适用于 <strong>{caseData.school}</strong> 的论文格式检测需求，
                为类似场景提供参考标准。
              </p>
            </div>
          </div>
        </div>
      </section>
    </main>
  );
}

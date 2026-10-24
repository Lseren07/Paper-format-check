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

type CaseListProps = {
  onSelectCase: (caseId: string) => void;
  onBack: () => void;
};

export function CaseList({ onSelectCase, onBack }: CaseListProps) {
  const [cases, setCases] = useState<ProjectCase[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    async function fetchCases() {
      try {
        const response = await fetch("/api/v1/cases");
        const body = await response.json();
        if (!response.ok) {
          throw new Error(body.detail ?? "获取案例列表失败");
        }
        setCases(body.data ?? []);
      } catch (err) {
        setError(err instanceof Error ? err.message : "无法加载案例列表");
      } finally {
        setLoading(false);
      }
    }
    fetchCases();
  }, []);

  if (loading) {
    return (
      <main className="shell">
        <section className="panel">
          <p className="muted">正在加载案例记录...</p>
        </section>
      </main>
    );
  }

  if (error) {
    return (
      <main className="shell">
        <section className="panel">
          <p className="error">{error}</p>
          <button type="button" onClick={onBack}>返回</button>
        </section>
      </main>
    );
  }

  return (
    <main className="shell">
      <header className="hero compact">
        <h1>案例记录</h1>
        <p className="sub">查看项目案例的完成情况及评估内容</p>
      </header>
      <section className="panel">
        <div className="result-actions">
          <button type="button" className="secondary-button" onClick={onBack}>
            返回主页
          </button>
        </div>
        {cases.length === 0 ? (
          <p className="muted">暂无案例记录</p>
        ) : (
          <ul className="case-grid">
            {cases.map((item) => (
              <li key={item.case_id} className="case-card">
                {item.thumbnail_url && (
                  <img
                    src={item.thumbnail_url}
                    alt={item.title}
                    className="case-thumbnail"
                  />
                )}
                <div className="case-content">
                  <h3>{item.title}</h3>
                  <p className="case-school">{item.school}</p>
                  <p className="case-description">{item.description}</p>
                  <dl className="case-stats">
                    <div>
                      <dt>文件数量</dt>
                      <dd>{item.file_count}</dd>
                    </div>
                    <div>
                      <dt>错误率</dt>
                      <dd>{(item.error_rate * 100).toFixed(1)}%</dd>
                    </div>
                  </dl>
                  {item.tags.length > 0 && (
                    <div className="case-tags">
                      {item.tags.map((tag) => (
                        <span key={tag} className="tag">{tag}</span>
                      ))}
                    </div>
                  )}
                  <button
                    type="button"
                    onClick={() => onSelectCase(item.case_id)}
                    className="case-detail-btn"
                  >
                    查看详情
                  </button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>
    </main>
  );
}

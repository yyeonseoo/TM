import type { Article } from '../types/news'

export function ArticleTable(props: { articles: Article[] }) {
  if (!props.articles?.length) {
    return <div className="nc-muted">아직 표시할 기사가 없습니다. Collect를 먼저 실행해 주세요.</div>
  }

  return (
    <div style={{ overflow: 'auto' }}>
      <table className="nc-table">
        <thead>
          <tr>
            <th style={{ width: 120 }}>언론사</th>
            <th>제목</th>
            <th style={{ width: 120 }}>링크</th>
          </tr>
        </thead>
        <tbody>
          {props.articles.map((a) => (
            <tr key={a.articleId}>
              <td>{a.press || <span className="nc-muted">-</span>}</td>
              <td>
                <div style={{ fontWeight: 650 }}>{a.title}</div>
                <div className="nc-muted" style={{ fontSize: 12, marginTop: 4 }}>
                  {a.contentPreview}
                </div>
              </td>
              <td>
                {a.url ? (
                  <a href={a.url} target="_blank" rel="noreferrer">
                    열기
                  </a>
                ) : (
                  <span className="nc-muted">-</span>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}


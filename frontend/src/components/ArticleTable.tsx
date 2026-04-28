import type { Article } from '../types/news'

export function ArticleTable(props: { articles: Article[]; loading?: boolean; variant?: 'table' | 'compact' }) {
  if (props.loading) {
    return (
      <div className="nc-tableSkeleton" aria-label="loading articles">
        {[0, 1, 2, 3, 4].map((i) => (
          <div key={i} className="nc-skeletonRow">
            <div className="nc-skeletonLine w20" />
            <div className="nc-skeletonLine w95" />
            <div className="nc-skeletonLine w35" />
          </div>
        ))}
      </div>
    )
  }

  if (!props.articles?.length) {
    return (
      <div className="nc-empty">
        <div className="nc-emptyIcon" aria-hidden="true">
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none">
            <path d="M4 7a3 3 0 0 1 3-3h12a1 1 0 0 1 1 1v14a2 2 0 0 1-2 2H7a3 3 0 0 1-3-3V7Z" stroke="currentColor" strokeWidth="1.5" opacity="0.9" />
            <path d="M7.5 9H17M7.5 12H17M7.5 15H13" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" opacity="0.8" />
          </svg>
        </div>
        <div className="nc-emptyTitle">아직 표시할 기사가 없습니다</div>
        <div className="nc-emptyBody">왼쪽에서 Collect를 실행하면, 수집된 기사가 여기에 표시됩니다.</div>
      </div>
    )
  }

  if (props.variant === 'compact') {
    return (
      <div className="nc-articleList" aria-label="collected articles list">
        {props.articles.map((a) => {
          const disabled = !a.url
          return (
            <a
              key={a.articleId}
              className={`nc-articleItem ${disabled ? 'disabled' : ''}`}
              href={a.url || undefined}
              target={disabled ? undefined : '_blank'}
              rel={disabled ? undefined : 'noreferrer'}
              aria-disabled={disabled}
              onClick={(e) => {
                if (disabled) e.preventDefault()
              }}
            >
              <div className="nc-articleTop">
                <span className="nc-articlePress">{a.press || '-'}</span>
                <span className="nc-articleLink">{disabled ? '' : '열기'}</span>
              </div>
              <div className="nc-articleTitle">{a.title}</div>
            </a>
          )
        })}
      </div>
    )
  }

  return (
    <div className="nc-tableWrap" aria-label="articles table">
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


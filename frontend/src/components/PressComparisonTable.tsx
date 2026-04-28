import type { Issue } from '../types/news'

export function PressComparisonTable(props: { issue: Issue }) {
  const rows = props.issue.pressData ?? []
  if (!rows.length) return <div className="nc-muted">언론사 비교 데이터가 없습니다.</div>

  return (
    <div className="nc-compareWrap" aria-label="press comparison summary">
      <table className="nc-table nc-compareTable">
        <thead>
          <tr>
            <th className="col-press">언론사</th>
            <th className="col-keywords">키워드</th>
            <th className="col-emphasis">강조 문장</th>
            <th className="col-titles">관련 기사</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.press}>
              <td className="col-press">
                <div className="nc-cellStrong">{r.press}</div>
              </td>
              <td className="col-keywords">
                <div className="nc-cellClamp nc-cellClamp2 nc-muted">{(r.keywords ?? []).slice(0, 8).join(', ') || '-'}</div>
              </td>
              <td className="col-emphasis">
                <div className="nc-cellClamp nc-cellClamp3">{(r.emphasizedSentences ?? [])[0] || <span className="nc-muted">-</span>}</div>
              </td>
              <td className="col-titles">
                <div className="nc-cellClamp nc-cellClamp2 nc-muted">{(r.titles ?? []).slice(0, 3).join(' / ') || '-'}</div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}


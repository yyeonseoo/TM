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
              <td className="nc-cellStrong">{r.press}</td>
              <td className="nc-muted nc-cellClamp2">
                {(r.keywords ?? []).slice(0, 8).join(', ') || '-'}
              </td>
              <td className="nc-cellClamp3">{(r.emphasizedSentences ?? [])[0] || <span className="nc-muted">-</span>}</td>
              <td className="nc-muted nc-cellClamp2">
                {(r.titles ?? []).slice(0, 3).join(' / ') || '-'}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}


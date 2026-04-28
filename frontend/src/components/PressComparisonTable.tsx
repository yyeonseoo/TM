import type { Issue } from '../types/news'

export function PressComparisonTable(props: { issue: Issue }) {
  const rows = props.issue.pressData ?? []
  if (!rows.length) return <div className="nc-muted">언론사 비교 데이터가 없습니다.</div>

  return (
    <div style={{ overflow: 'auto' }}>
      <table className="nc-table">
        <thead>
          <tr>
            <th style={{ width: 120 }}>언론사</th>
            <th style={{ width: 180 }}>키워드</th>
            <th>강조 문장</th>
            <th style={{ width: 220 }}>관련 기사</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.press}>
              <td>{r.press}</td>
              <td className="nc-muted" style={{ fontSize: 12 }}>
                {(r.keywords ?? []).slice(0, 6).join(', ') || '-'}
              </td>
              <td>{(r.emphasizedSentences ?? [])[0] || <span className="nc-muted">-</span>}</td>
              <td className="nc-muted" style={{ fontSize: 12 }}>
                {(r.titles ?? []).slice(0, 3).join(' / ') || '-'}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}


import type { Issue } from '../types/news'
import { PressComparisonTable } from './PressComparisonTable'
import { PressTabs } from './PressTabs'

export function IssueDetailPanel(props: { issue: Issue | null }) {
  const issue = props.issue
  if (!issue) return <div className="nc-muted">선택된 이슈가 없습니다.</div>

  return (
    <div className="nc-split">
      <div className="nc-card">
        <div className="nc-cardHeader">
          <div className="nc-cardTitle">공통 사실 요약</div>
          <div className="nc-badge">facts</div>
        </div>
        <div className="nc-cardBody">
          {issue.summary ? <div style={{ marginBottom: 10 }}>{issue.summary}</div> : null}
          <ul style={{ margin: 0, paddingLeft: 18 }}>
            {(issue.commonFacts ?? []).map((f, idx) => (
              <li key={idx} style={{ marginBottom: 8 }}>
                {f}
              </li>
            ))}
          </ul>

          <div className="nc-muted" style={{ fontSize: 12, marginTop: 12, marginBottom: 6 }}>근거 문장</div>
          <ul style={{ margin: 0, paddingLeft: 18 }}>
            {(issue.evidenceSentences ?? []).slice(0, 10).map((s, idx) => (
              <li key={idx} className="nc-muted" style={{ marginBottom: 6 }}>
                {s}
              </li>
            ))}
          </ul>
        </div>
      </div>

      <div style={{ display: 'grid', gap: 12 }}>
        <div className="nc-card">
          <div className="nc-cardHeader">
            <div className="nc-cardTitle">언론사 비교</div>
            <div className="nc-badge">compare</div>
          </div>
          <div className="nc-cardBody">
            <PressComparisonTable issue={issue} />
          </div>
        </div>

        <PressTabs issue={issue} />
      </div>
    </div>
  )
}


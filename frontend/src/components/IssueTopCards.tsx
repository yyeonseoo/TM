import type { Issue } from '../types/news'

export function IssueTopCards(props: {
  issues: Issue[]
  loading: boolean
  selectedIssueId: string | null
  onSelect: (issueId: string) => void
}) {
  if (props.loading) return <div className="nc-muted">불러오는 중…</div>
  if (!props.issues?.length) return <div className="nc-muted">분석 결과가 아직 없습니다. Analyze를 실행해 주세요.</div>

  return (
    <div className="nc-issueCards">
      {props.issues.slice(0, 3).map((issue) => {
        const selected = issue.issueId === props.selectedIssueId
        return (
          <div
            key={issue.issueId}
            className={`nc-issueCard ${selected ? 'selected' : ''}`}
            role="button"
            tabIndex={0}
            onClick={() => props.onSelect(issue.issueId)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' || e.key === ' ') props.onSelect(issue.issueId)
            }}
          >
            <div className="nc-issueRank">Rank #{issue.rank}</div>
            <div className="nc-issueTitle">{issue.title}</div>
            <div className="nc-pillRow">
              {(issue.keywords ?? []).slice(0, 6).map((k) => (
                <span className="nc-pill" key={k}>
                  {k}
                </span>
              ))}
            </div>
          </div>
        )
      })}
    </div>
  )
}


import type { Issue } from '../types/news'

export function IssueTopCards(props: {
  issues: Issue[]
  loading: boolean
  selectedIssueId: string | null
  onSelect: (issueId: string) => void
}) {
  if (props.loading) {
    return (
      <div className="nc-issueCards">
        {[0, 1, 2].map((i) => (
          <div key={i} className="nc-issueCard nc-skeletonCard" aria-hidden="true">
            <div className="nc-skeletonLine w40" />
            <div className="nc-skeletonLine w90" />
            <div className="nc-skeletonLine w75" />
            <div className="nc-skeletonPills">
              <span className="nc-skeletonPill" />
              <span className="nc-skeletonPill" />
              <span className="nc-skeletonPill" />
            </div>
          </div>
        ))}
      </div>
    )
  }

  if (!props.issues?.length) {
    return (
      <div className="nc-empty">
        <div className="nc-emptyIcon" aria-hidden="true">
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none">
            <path d="M6.5 4H20v14.5A2.5 2.5 0 0 1 17.5 21h-11A2.5 2.5 0 0 1 4 18.5v-12A2.5 2.5 0 0 1 6.5 4Z" stroke="currentColor" strokeWidth="1.5" opacity="0.9" />
            <path d="M8 8h8M8 12h8M8 16h5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" opacity="0.8" />
          </svg>
        </div>
        <div className="nc-emptyTitle">분석 결과가 아직 없습니다</div>
        <div className="nc-emptyBody">오른쪽 상단 상태가 수집 done이면, Analyze를 실행해 주세요.</div>
      </div>
    )
  }

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
            <div className="nc-issueRank">#{issue.rank}</div>
            <div className="nc-issueTitle">{issue.title}</div>
            <div className="nc-issueSummary">{issue.summary || '요약 정보가 없습니다.'}</div>
            <div className="nc-issueMetaRow">
              <span className="nc-badge nc-badgeTiny">{(issue.pressData?.length ?? 0).toString()} sources</span>
            </div>
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


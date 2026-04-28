import { useMemo, useState } from 'react'
import type { Issue } from '../../types/news'

type TimelinePoint = {
  date: string
  count: number
}

function buildStubTimeline(issue: Issue): TimelinePoint[] {
  // Placeholder for future "re-search API → time series aggregation" logic.
  // For now, provide a deterministic stub so UI layout is implementable.
  const base = (issue.pressData?.length ?? 1) + (issue.keywords?.length ?? 1)
  return [
    { date: 'D-6', count: Math.max(0, base - 2) },
    { date: 'D-5', count: Math.max(0, base - 1) },
    { date: 'D-4', count: base },
    { date: 'D-3', count: base + 1 },
    { date: 'D-2', count: base + 2 },
    { date: 'D-1', count: base + 1 },
    { date: 'D', count: base + 3 },
  ]
}

export function IssueTimelinePanel(props: { issue: Issue }) {
  const [query, setQuery] = useState<string>(() => props.issue.title)
  const points = useMemo(() => buildStubTimeline(props.issue), [props.issue])
  const max = Math.max(1, ...points.map((p) => p.count))

  return (
    <div className="nc-timelineWrap">
      <div className="nc-muted" style={{ fontSize: 12 }}>
        시계열(스캐폴딩) · “이슈 재검색 API → 날짜별 기사 수”로 확장 예정
      </div>

      <div className="nc-timelineControls">
        <div className="nc-field" style={{ marginBottom: 0 }}>
          <div className="nc-label">검색 쿼리(초안)</div>
          <input className="nc-input" value={query} onChange={(e) => setQuery(e.target.value)} placeholder="예: 키워드 조합" />
        </div>
        <button className="nc-btn secondary" type="button" disabled>
          검색(예정)
        </button>
      </div>

      <div className="nc-timelineChart" role="img" aria-label="timeline chart">
        {points.map((p) => (
          <div key={p.date} className="nc-bar">
            <div className="nc-barFill" style={{ width: `${(p.count / max) * 100}%` }} />
            <div className="nc-barLabel">
              <span>{p.date}</span>
              <span className="nc-muted">{p.count}건</span>
            </div>
          </div>
        ))}
      </div>

      <div className="nc-empty" style={{ marginTop: 12 }}>
        <div className="nc-emptyTitle">다음 작업 포인트</div>
        <div className="nc-emptyBody">
          `related news search` 엔드포인트 연결 → 기사 리스트/언론사 분포/시계열 집계까지 여기서 확장하면 됩니다.
        </div>
      </div>
    </div>
  )
}


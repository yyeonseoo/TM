import { useMemo, useState } from 'react'
import type { Issue } from '../types/news'
import { PressComparisonTable } from './PressComparisonTable'
import { PressTabs } from './PressTabs'

type TabKey = 'facts' | 'compare' | 'evidence'

export function IssueDetailPanel(props: { issue: Issue | null }) {
  const issue = props.issue
  const [tab, setTab] = useState<TabKey>('facts')

  const evidence = useMemo(() => (issue?.evidenceSentences ?? []).filter(Boolean), [issue?.evidenceSentences])

  if (!issue) {
    return (
      <div className="nc-empty">
        <div className="nc-emptyIcon" aria-hidden="true">
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none">
            <path d="M12 3 2.5 7.5 12 12l9.5-4.5L12 3Z" stroke="currentColor" strokeWidth="1.5" opacity="0.9" />
            <path d="M2.5 7.5V16.5L12 21l9.5-4.5V7.5" stroke="currentColor" strokeWidth="1.5" opacity="0.75" />
          </svg>
        </div>
        <div className="nc-emptyTitle">이슈를 선택해 주세요</div>
        <div className="nc-emptyBody">TOP 3에서 이슈를 클릭하면, 상세 분석이 여기 표시됩니다.</div>
      </div>
    )
  }

  return (
    <div className="nc-card nc-cardGlass">
      <div className="nc-cardHeader">
        <div style={{ minWidth: 0 }}>
          <div className="nc-cardTitle" style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {issue.title}
          </div>
          <div className="nc-muted" style={{ fontSize: 12, marginTop: 4 }}>
            Rank #{issue.rank} · {issue.pressData?.length ?? 0} sources · {issue.keywords?.length ?? 0} keywords
          </div>
        </div>
        <div className="nc-badge">detail</div>
      </div>

      <div className="nc-cardBody">
        <div className="nc-tabsUnderline" role="tablist" aria-label="issue detail tabs">
          <button type="button" className={`nc-tabU ${tab === 'facts' ? 'active' : ''}`} onClick={() => setTab('facts')}>
            공통 사실
          </button>
          <button type="button" className={`nc-tabU ${tab === 'compare' ? 'active' : ''}`} onClick={() => setTab('compare')}>
            언론사별 비교
          </button>
          <button type="button" className={`nc-tabU ${tab === 'evidence' ? 'active' : ''}`} onClick={() => setTab('evidence')}>
            근거 문장
          </button>
        </div>

        {tab === 'facts' ? (
          <div className="nc-stack">
            {issue.summary ? <div className="nc-lead">{issue.summary}</div> : null}
            <div className="nc-subtitle">공통 사실</div>
            {(issue.commonFacts ?? []).length ? (
              <ul className="nc-list">
                {(issue.commonFacts ?? []).map((f, idx) => (
                  <li key={idx}>{f}</li>
                ))}
              </ul>
            ) : (
              <div className="nc-muted">공통 사실 데이터가 없습니다.</div>
            )}
          </div>
        ) : null}

        {tab === 'compare' ? (
          <div className="nc-stack">
            <div className="nc-subtitle">언론사 비교 요약</div>
            <PressComparisonTable issue={issue} />
            <div className="nc-subtitle">언론사별 상세</div>
            <PressTabs issue={issue} />
          </div>
        ) : null}

        {tab === 'evidence' ? (
          <div className="nc-stack">
            <div className="nc-subtitle">근거 문장</div>
            {evidence.length ? (
              <ul className="nc-list nc-listMuted">
                {evidence.slice(0, 30).map((s, idx) => (
                  <li key={idx}>{s}</li>
                ))}
              </ul>
            ) : (
              <div className="nc-muted">근거 문장이 없습니다.</div>
            )}
          </div>
        ) : null}
      </div>
    </div>
  )
}


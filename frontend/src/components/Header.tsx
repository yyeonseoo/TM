import type { JobStatus } from '../types/news'

function badgeClass(status: JobStatus | null | undefined) {
  if (!status) return 'nc-badge'
  if (status === 'done') return 'nc-badge good'
  if (status === 'running' || status === 'queued') return 'nc-badge warn'
  return 'nc-badge bad'
}

function label(status: JobStatus | null | undefined) {
  if (!status) return 'idle'
  if (status === 'queued') return 'queued'
  if (status === 'running') return 'running'
  if (status === 'done') return 'done'
  return 'error'
}

export function Header(props: {
  projectName: string
  subtitle?: string
  collectStatus?: JobStatus | null
  analyzeStatus?: JobStatus | null
}) {
  return (
    <header className="nc-headerBar">
      <div className="nc-headerLeft">
        <div className="nc-headerIcon" aria-hidden="true">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
            <path
              d="M4 6.5C4 5.12 5.12 4 6.5 4H20v14.5c0 1.38-1.12 2.5-2.5 2.5H6.5C5.12 21 4 19.88 4 18.5v-12.0Z"
              stroke="currentColor"
              strokeWidth="1.5"
              opacity="0.9"
            />
            <path d="M8 8h8M8 12h8M8 16h5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" opacity="0.85" />
          </svg>
        </div>
        <div className="nc-headerText">
          <div className="nc-headerTitle">{props.projectName}</div>
          <div className="nc-headerSubtitle">{props.subtitle ?? '수집 → 분석 → 이슈 비교까지 한 화면에서'}</div>
        </div>
      </div>
      <div className="nc-headerRight" aria-label="status badges">
        <span className={badgeClass(props.collectStatus)}>수집 {label(props.collectStatus)}</span>
        <span className={badgeClass(props.analyzeStatus)}>분석 {label(props.analyzeStatus)}</span>
      </div>
    </header>
  )
}


import type { JobStatus } from '../types/news'

function badgeClass(status: JobStatus | null) {
  if (!status) return 'nc-badge'
  if (status === 'done') return 'nc-badge good'
  if (status === 'running' || status === 'queued') return 'nc-badge warn'
  return 'nc-badge bad'
}

function label(status: JobStatus | null) {
  if (!status) return 'idle'
  if (status === 'queued') return 'queued'
  if (status === 'running') return 'running'
  if (status === 'done') return 'done'
  return 'error'
}

export function RunStatusBar(props: { runId: string | null; collectStatus: JobStatus | null; analyzeStatus: JobStatus | null }) {
  return (
    <div className="nc-card" style={{ marginTop: 12 }}>
      <div className="nc-cardBody" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 10 }}>
        <div style={{ minWidth: 0 }}>
          <div className="nc-muted" style={{ fontSize: 12 }}>최근 실행 runId</div>
          <div style={{ fontWeight: 750, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {props.runId ? <code>{props.runId}</code> : <span className="nc-muted">아직 없음</span>}
          </div>
        </div>
        <div className="nc-badgeRow" aria-label="run status badges">
          <span className={badgeClass(props.collectStatus)}>수집 {label(props.collectStatus)}</span>
          <span className={badgeClass(props.analyzeStatus)}>분석 {label(props.analyzeStatus)}</span>
        </div>
      </div>
    </div>
  )
}


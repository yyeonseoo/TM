import type { JobStatusResponse } from '../types/news'

export function JobProgressCard(props: { title: string; job: JobStatusResponse | null | undefined; error: string | null }) {
  const progress = props.job?.progress ?? 0
  const status = props.job?.status ?? 'idle'
  const message = props.job?.message ?? ''
  const err = props.job?.error ?? props.error

  return (
    <div className="nc-card">
      <div className="nc-cardHeader">
        <div className="nc-cardTitle">{props.title}</div>
        <div className="nc-badge">{status}</div>
      </div>
      <div className="nc-cardBody">
        <div className="nc-progressOuter" aria-label={`${props.title} progress`}>
          <div className="nc-progressInner" style={{ width: `${progress}%` }} />
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 10 }}>
          <div className="nc-muted" style={{ fontSize: 12 }}>
            {message || '대기 중'}
          </div>
          <div style={{ fontWeight: 750, fontSize: 12 }}>{progress}%</div>
        </div>
        {err ? (
          <div style={{ marginTop: 10, fontSize: 12, color: 'rgba(239,68,68,0.95)' }}>
            {String(err)}
          </div>
        ) : null}
      </div>
    </div>
  )
}


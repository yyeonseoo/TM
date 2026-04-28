export function Header(props: { projectName: string }) {
  return (
    <div className="nc-card">
      <div className="nc-cardHeader">
        <div>
          <div className="nc-cardTitle">{props.projectName}</div>
          <div className="nc-muted" style={{ fontSize: 12, marginTop: 4 }}>
            React UI · FastAPI 파이프라인 (runId/jobId)
          </div>
        </div>
        <div className="nc-badge">MVP</div>
      </div>
    </div>
  )
}


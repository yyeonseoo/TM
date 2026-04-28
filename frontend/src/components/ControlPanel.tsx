export function ControlPanel(props: {
  categoryFilter: string
  setCategoryFilter: (v: string) => void
  targetCount: number
  setTargetCount: (v: number) => void
  linkPoolSize: number
  setLinkPoolSize: (v: number) => void
  onCollect: () => Promise<void> | void
  onAnalyze: () => Promise<void> | void
  canAnalyze: boolean
  busy: boolean
}) {
  return (
    <div className="nc-card">
      <div className="nc-cardHeader">
        <div className="nc-cardTitle">수집 설정</div>
        <div className="nc-badge">controls</div>
      </div>
      <div className="nc-cardBody">
        <div className="nc-field">
          <div className="nc-label">카테고리</div>
          <select className="nc-select" value={props.categoryFilter} onChange={(e) => props.setCategoryFilter(e.target.value)}>
            <option value="politics">politics (정치)</option>
            <option value="정치">정치</option>
          </select>
        </div>

        <div className="nc-field">
          <div className="nc-label">수집 기사 수</div>
          <input
            className="nc-input"
            type="number"
            min={1}
            max={300}
            value={props.targetCount}
            onChange={(e) => props.setTargetCount(Number(e.target.value))}
          />
        </div>

        <div className="nc-field">
          <div className="nc-label">링크 후보 수</div>
          <input
            className="nc-input"
            type="number"
            min={10}
            max={2000}
            value={props.linkPoolSize}
            onChange={(e) => props.setLinkPoolSize(Number(e.target.value))}
          />
        </div>

        <div className="nc-btnRow">
          <button className="nc-btn primary" onClick={props.onCollect} disabled={props.busy}>
            Collect
          </button>
          <button className="nc-btn" onClick={props.onAnalyze} disabled={!props.canAnalyze || props.busy}>
            Analyze
          </button>
        </div>

        <div className="nc-muted" style={{ fontSize: 12, marginTop: 10, lineHeight: 1.4 }}>
          시크릿은 백엔드 환경변수 <code>NAVER_CLIENT_ID</code>, <code>NAVER_CLIENT_SECRET</code>로 설정되어 있어야 합니다.
        </div>
      </div>
    </div>
  )
}


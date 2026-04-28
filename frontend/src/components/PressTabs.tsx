import { useMemo, useState } from 'react'
import type { Issue, PressData } from '../types/news'

function PressDetailCard(props: { press: PressData }) {
  const p = props.press
  return (
    <div className="nc-card">
      <div className="nc-cardHeader">
        <div className="nc-cardTitle">{p.press}</div>
        <div className="nc-badge">press</div>
      </div>
      <div className="nc-cardBody">
        <div className="nc-muted" style={{ fontSize: 12, marginBottom: 6 }}>키워드</div>
        <div className="nc-pillRow" style={{ marginBottom: 12 }}>
          {(p.keywords ?? []).slice(0, 10).map((k) => (
            <span className="nc-pill" key={k}>{k}</span>
          ))}
        </div>

        <div className="nc-muted" style={{ fontSize: 12, marginBottom: 6 }}>강조 문장</div>
        <div style={{ marginBottom: 12 }}>{(p.emphasizedSentences ?? [])[0] || <span className="nc-muted">-</span>}</div>

        <div className="nc-muted" style={{ fontSize: 12, marginBottom: 6 }}>근거 문장</div>
        <ul style={{ margin: 0, paddingLeft: 18 }}>
          {(p.evidenceSentences ?? []).slice(0, 6).map((s, idx) => (
            <li key={idx} className="nc-muted" style={{ marginBottom: 6 }}>{s}</li>
          ))}
        </ul>
      </div>
    </div>
  )
}

export function PressTabs(props: { issue: Issue }) {
  const presses = useMemo(() => props.issue.pressData ?? [], [props.issue.pressData])
  const [active, setActive] = useState<string>(() => presses[0]?.press ?? '')

  const activePress = presses.find((p) => p.press === active) ?? presses[0]

  if (!presses.length) return <div className="nc-muted">언론사 데이터가 없습니다.</div>

  return (
    <div>
      <div className="nc-tabs" role="tablist" aria-label="press tabs">
        {presses.map((p) => (
          <button
            key={p.press}
            className={`nc-tab ${p.press === active ? 'active' : ''}`}
            onClick={() => setActive(p.press)}
            type="button"
          >
            {p.press}
          </button>
        ))}
      </div>

      {activePress ? <PressDetailCard press={activePress} /> : null}
    </div>
  )
}


import { useMemo } from 'react'
import type { Issue } from '../../types/news'

type Node = { id: string; label: string }
type Edge = { from: string; to: string }

function buildGraph(issue: Issue): { nodes: Node[]; edges: Edge[] } {
  const centerId = `issue:${issue.issueId}`
  const nodes: Node[] = [{ id: centerId, label: issue.title }]
  const edges: Edge[] = []

  const keywords = (issue.keywords ?? []).slice(0, 10)
  for (const k of keywords) {
    const id = `kw:${k}`
    nodes.push({ id, label: k })
    edges.push({ from: centerId, to: id })
  }

  const presses = (issue.pressData ?? []).map((p) => p.press).filter(Boolean).slice(0, 8)
  for (const p of presses) {
    const id = `press:${p}`
    nodes.push({ id, label: p })
    edges.push({ from: centerId, to: id })
  }

  return { nodes, edges }
}

export function IssueGraphPanel(props: { issue: Issue }) {
  const graph = useMemo(() => buildGraph(props.issue), [props.issue])

  // Minimal SVG scaffold: center node + circle layout for related nodes.
  const w = 720
  const h = 360
  const cx = w / 2
  const cy = h / 2
  const others = graph.nodes.slice(1)
  const r = Math.min(w, h) * 0.33

  const pos = new Map<string, { x: number; y: number }>()
  pos.set(graph.nodes[0]!.id, { x: cx, y: cy })
  others.forEach((n, i) => {
    const t = (i / Math.max(1, others.length)) * Math.PI * 2
    pos.set(n.id, { x: cx + Math.cos(t) * r, y: cy + Math.sin(t) * r })
  })

  return (
    <div className="nc-graphWrap">
      <div className="nc-muted" style={{ fontSize: 12 }}>
        관계 그래프(스캐폴딩) · 키워드/언론사 노드 연결 — 이후 레이아웃/가중치/클러스터링을 확장하세요.
      </div>

      <div className="nc-graphStage" role="img" aria-label="issue relationship graph">
        <svg viewBox={`0 0 ${w} ${h}`} width="100%" height="100%" preserveAspectRatio="xMidYMid meet">
          <defs>
            <linearGradient id="edgeGrad" x1="0" x2="1">
              <stop offset="0%" stopColor="rgba(47,116,192,0.55)" />
              <stop offset="100%" stopColor="rgba(57,166,198,0.45)" />
            </linearGradient>
          </defs>

          {graph.edges.map((e) => {
            const a = pos.get(e.from)!
            const b = pos.get(e.to)!
            return (
              <line
                key={`${e.from}->${e.to}`}
                x1={a.x}
                y1={a.y}
                x2={b.x}
                y2={b.y}
                stroke="url(#edgeGrad)"
                strokeWidth="1.5"
                opacity="0.7"
              />
            )
          })}

          {/* Center */}
          <circle cx={cx} cy={cy} r="34" fill="rgba(11,42,85,0.95)" stroke="rgba(47,116,192,0.45)" strokeWidth="2" />
          <text x={cx} y={cy} textAnchor="middle" dominantBaseline="middle" fontSize="11" fill="rgba(255,255,255,0.95)">
            ISSUE
          </text>

          {/* Others */}
          {others.map((n) => {
            const p = pos.get(n.id)!
            const isPress = n.id.startsWith('press:')
            const fill = isPress ? 'rgba(57,166,198,0.16)' : 'rgba(47,116,192,0.12)'
            const stroke = isPress ? 'rgba(57,166,198,0.35)' : 'rgba(47,116,192,0.32)'
            return (
              <g key={n.id}>
                <circle cx={p.x} cy={p.y} r="18" fill={fill} stroke={stroke} strokeWidth="1.5" />
                <text
                  x={p.x}
                  y={p.y + 30}
                  textAnchor="middle"
                  fontSize="10"
                  fill="rgba(12,20,34,0.72)"
                >
                  {n.label.length > 10 ? `${n.label.slice(0, 10)}…` : n.label}
                </text>
              </g>
            )
          })}
        </svg>
      </div>
    </div>
  )
}


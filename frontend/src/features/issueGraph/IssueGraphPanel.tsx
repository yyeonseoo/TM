import { useEffect, useMemo, useState } from 'react'
import type { GraphEdge, GraphNode, Issue, IssueGraphResponse } from '../../types/news'
import { newsConsensusApi } from '../../api/newsConsensusApi'

type UiNode = { id: string; label: string; kind?: string; size?: number }
type UiEdge = { from: string; to: string; weight?: number; kind?: string }

function toUiGraph(res: IssueGraphResponse): { nodes: UiNode[]; edges: UiEdge[] } {
  const nodes: UiNode[] = (res.graph.nodes ?? []).map((n: GraphNode) => ({
    id: n.id,
    label: (typeof n.label === 'string' && n.label) || n.id,
    kind: typeof n.kind === 'string' ? n.kind : undefined,
    size: typeof n.size === 'number' ? n.size : undefined,
  }))
  const rawEdges: GraphEdge[] = (res.graph.links ?? res.graph.edges ?? []) as GraphEdge[]
  const edges: UiEdge[] = rawEdges.map((e: GraphEdge) => ({
    from: e.source,
    to: e.target,
    weight: typeof e.weight === 'number' ? e.weight : undefined,
    kind: typeof e.kind === 'string' ? e.kind : undefined,
  }))
  return { nodes, edges }
}

export function IssueGraphPanel(props: { issue: Issue; runId: string | null }) {
  const [data, setData] = useState<{ nodes: UiNode[]; edges: UiEdge[] } | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const runId = props.runId
    const issueId = props.issue.issueId
    if (!runId) {
      setError('runId가 없어 그래프 API를 호출할 수 없습니다.')
      setData(null)
      return
    }
    let cancelled = false
    setError(null)
    setData(null)
    ;(async () => {
      try {
        const res = await newsConsensusApi.getIssueGraph(runId, issueId)
        if (!cancelled) setData(toUiGraph(res))
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : String(e))
      }
    })()
    return () => {
      cancelled = true
    }
  }, [props.runId, props.issue.issueId])

  const graph = useMemo(() => data ?? { nodes: [], edges: [] }, [data])

  // Minimal SVG scaffold: center node + circle layout for related nodes.
  const w = 720
  const h = 360
  const cx = w / 2
  const cy = h / 2
  const center = graph.nodes.find((n) => n.kind === 'issue') ?? graph.nodes[0] ?? null
  const others = center ? graph.nodes.filter((n) => n.id !== center.id) : graph.nodes
  const r = Math.min(w, h) * 0.33

  const pos = new Map<string, { x: number; y: number }>()
  if (center) pos.set(center.id, { x: cx, y: cy })
  others.forEach((n, i) => {
    const t = (i / Math.max(1, others.length)) * Math.PI * 2
    pos.set(n.id, { x: cx + Math.cos(t) * r, y: cy + Math.sin(t) * r })
  })

  return (
    <div className="nc-graphWrap">
      <div className="nc-muted" style={{ fontSize: 12 }}>
        관계 그래프 · API 기반(weighted graph)
      </div>
      {error ? (
        <div className="nc-alert" style={{ marginTop: 10 }}>
          <div className="nc-alertTitle">그래프 로드 실패</div>
          <div className="nc-alertBody">{error}</div>
        </div>
      ) : null}

      <div className="nc-graphStage" role="img" aria-label="issue relationship graph">
        <svg viewBox={`0 0 ${w} ${h}`} width="100%" height="100%" preserveAspectRatio="xMidYMid meet">
          <defs>
            <linearGradient id="edgeGrad" x1="0" x2="1">
              <stop offset="0%" stopColor="rgba(47,116,192,0.55)" />
              <stop offset="100%" stopColor="rgba(57,166,198,0.45)" />
            </linearGradient>
          </defs>

          {graph.edges.map((e) => {
            const a = pos.get(e.from)
            const b = pos.get(e.to)
            if (!a || !b) return null
            return (
              <line
                key={`${e.from}->${e.to}`}
                x1={a.x}
                y1={a.y}
                x2={b.x}
                y2={b.y}
                stroke="url(#edgeGrad)"
                strokeWidth={1.2 + Math.min(2.2, (e.weight ?? 0) * 2)}
                opacity="0.7"
              />
            )
          })}

          {/* Center */}
          {center ? (
            <>
              <circle
                cx={cx}
                cy={cy}
                r={34}
                fill="rgba(11,42,85,0.95)"
                stroke="rgba(47,116,192,0.45)"
                strokeWidth="2"
              />
              <text x={cx} y={cy} textAnchor="middle" dominantBaseline="middle" fontSize="11" fill="rgba(255,255,255,0.95)">
                ISSUE
              </text>
            </>
          ) : null}

          {/* Others */}
          {others.map((n) => {
            const p = pos.get(n.id)
            if (!p) return null
            const isPress = (n.kind ?? '').toString() === 'press' || n.id.startsWith('press:')
            const fill = isPress ? 'rgba(57,166,198,0.16)' : 'rgba(47,116,192,0.12)'
            const stroke = isPress ? 'rgba(57,166,198,0.35)' : 'rgba(47,116,192,0.32)'
            const rr = 14 + Math.min(10, Math.max(0, (n.size ?? 0) * 2))
            return (
              <g key={n.id}>
                <circle cx={p.x} cy={p.y} r={rr} fill={fill} stroke={stroke} strokeWidth="1.5" />
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


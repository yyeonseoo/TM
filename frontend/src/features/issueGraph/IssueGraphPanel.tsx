import { useEffect, useMemo, useState } from 'react'
import type { Issue, IssueImageGraphResponse } from '../../types/news'
import { newsConsensusApi } from '../../api/newsConsensusApi'

type UiNode = {
  id: string
  label: string
  size?: number
  iconUrl?: string | null
  iconMeta?: {
    selected?: boolean
    score?: number
    source?: string
    reason?: string
    fallback?: boolean
    candidatesCount?: number
  } | null
}
type UiEdge = { from: string; to: string; weight?: number; weightNorm?: number; relation?: string }

const DEFAULT_API_BASE = 'http://127.0.0.1:8000'
function apiBase(): string {
  return (import.meta as any).env?.VITE_API_BASE ?? DEFAULT_API_BASE
}

function toAbsoluteApiUrl(maybePath: string | null | undefined): string | null {
  if (!maybePath) return null
  if (maybePath.startsWith('http://') || maybePath.startsWith('https://') || maybePath.startsWith('data:')) return maybePath
  if (maybePath.startsWith('/')) return `${apiBase()}${maybePath}`
  return maybePath
}

function toUiGraph(res: IssueImageGraphResponse): { nodes: UiNode[]; edges: UiEdge[] } {
  const nodes: UiNode[] = (res.graph.nodes ?? [])
    .filter((n) => (n.type ?? '') === 'keyword')
    .map((n) => ({
      id: n.id,
      label: n.label ?? n.id,
      size: typeof n.size === 'number' ? n.size : undefined,
      iconUrl: toAbsoluteApiUrl(typeof n.iconUrl === 'string' ? n.iconUrl : null),
      iconMeta: (n as any).iconMeta ?? null,
    }))

  const edges: UiEdge[] = (res.graph.edges ?? []).map((e) => ({
    from: e.source,
    to: e.target,
    weight: typeof e.weight === 'number' ? e.weight : undefined,
    weightNorm: typeof e.weightNorm === 'number' ? e.weightNorm : undefined,
    relation: typeof e.relation === 'string' ? e.relation : undefined,
  }))
  return { nodes, edges }
}

function svgFallbackAvatar(label: string, size = 96): string {
  const txt = (label || '').trim()
  const short = encodeURIComponent(txt.length >= 2 ? txt.slice(0, 2) : txt.length === 1 ? txt : '?')
  // simple stable-ish color
  let h = 0
  for (let i = 0; i < txt.length; i++) h = (h * 31 + txt.charCodeAt(i)) % 360
  const bg = `hsl(${h},65%,55%)`
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${size}" height="${size}" viewBox="0 0 ${size} ${size}"><defs><clipPath id="c"><circle cx="${size / 2}" cy="${size / 2}" r="${size / 2}"/></clipPath></defs><g clip-path="url(#c)"><rect width="${size}" height="${size}" fill="${bg}"/><text x="50%" y="54%" text-anchor="middle" dominant-baseline="middle" font-family="system-ui,-apple-system,Segoe UI,Roboto,Arial" font-size="${Math.floor(
    size * 0.38,
  )}" font-weight="700" fill="rgba(255,255,255,0.96)">${decodeURIComponent(short)}</text></g></svg>`
  return `data:image/svg+xml;utf8,${encodeURIComponent(svg)}`
}

function edgeLabel(e: UiEdge): { label: string; tooltip: string } {
  const wn = typeof e.weightNorm === 'number' ? e.weightNorm : null
  const w = typeof e.weight === 'number' ? e.weight : null
  const rel = e.relation ?? 'co_occurs'

  const relationName = rel === 'co_occurs' ? '같이 언급됨' : rel
  const label = w !== null ? `같은 기사 ${w}건` : wn !== null ? `연관도 ${wn.toFixed(2)}` : relationName

  const strength =
    w === null
      ? wn !== null
        ? wn >= 0.7
          ? '강한 연관'
          : wn >= 0.35
            ? '연관'
            : '약한 연관'
        : '관계'
      : w >= 4
        ? '강한 연관'
        : w >= 2
          ? '연관'
          : '약한 연관'

  const tooltip =
    `관계: ${relationName}\n` +
    `강도: ${strength}\n` +
    (w !== null ? `같은 기사: ${w}건\n` : '') +
    (wn !== null ? `정규화 연관도: ${wn.toFixed(2)}` : '')

  return { label, tooltip }
}

export function IssueGraphPanel(props: { issue: Issue; runId: string | null }) {
  const [data, setData] = useState<{ nodes: UiNode[]; edges: UiEdge[] } | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [broken, setBroken] = useState<Record<string, boolean>>({})

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
        const res = await newsConsensusApi.getIssueImageGraph(runId, issueId)
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
  const others = graph.nodes
  const r = Math.min(w, h) * 0.33

  const pos = new Map<string, { x: number; y: number }>()
  others.forEach((n, i) => {
    const t = (i / Math.max(1, others.length)) * Math.PI * 2
    pos.set(n.id, { x: cx + Math.cos(t) * r, y: cy + Math.sin(t) * r })
  })

  return (
    <div className="nc-graphWrap">
      <div className="nc-muted" style={{ fontSize: 12 }}>
        관계 그래프 · 아이콘 + 관계 라벨 (image graph)
      </div>
      {error ? (
        <div className="nc-alert" style={{ marginTop: 10 }}>
          <div className="nc-alertTitle">그래프 로드 실패</div>
          <div className="nc-alertBody">{error}</div>
        </div>
      ) : null}

      <div className="nc-graphStage" role="img" aria-label="issue relationship graph" style={{ position: 'relative' }}>
        {/* Edges in SVG */}
        <svg
          viewBox={`0 0 ${w} ${h}`}
          width="100%"
          height="100%"
          preserveAspectRatio="xMidYMid meet"
          style={{ display: 'block' }}
        >
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
            const { label, tooltip } = edgeLabel(e)
            return (
              <g key={`${e.from}->${e.to}`}>
                <line
                  x1={a.x}
                  y1={a.y}
                  x2={b.x}
                  y2={b.y}
                  stroke="url(#edgeGrad)"
                  strokeWidth={0.8 + Math.min(3.2, (e.weightNorm ?? 0.5) * 3)}
                  opacity="0.55"
                />
                <title>{tooltip}</title>
                {(e.weightNorm ?? 0) > 0.2 ? (
                  <text
                    x={(a.x + b.x) / 2}
                    y={(a.y + b.y) / 2}
                    textAnchor="middle"
                    fontSize="9"
                    fill="rgba(12,20,34,0.58)"
                  >
                    {label}
                    <title>{tooltip}</title>
                  </text>
                ) : null}
              </g>
            )
          })}
        </svg>

        {/* Nodes in HTML for stable <img> loading */}
        {others.map((n) => {
          const p = pos.get(n.id)
          if (!p) return null
          const base = typeof n.size === 'number' ? n.size : 40
          const rr = Math.max(8, Math.min(34, base / 5))
          const leftPct = (p.x / w) * 100
          const topPct = (p.y / h) * 100
          const src = broken[n.id] ? svgFallbackAvatar(n.label) : n.iconUrl || svgFallbackAvatar(n.label)
          const meta = n.iconMeta
          const metaLine = meta
            ? `\nicon: ${meta.source ?? 'n/a'} score=${typeof meta.score === 'number' ? meta.score.toFixed(2) : 'n/a'} cand=${meta.candidatesCount ?? 'n/a'}`
            : ''
          const reasonLine = meta?.reason ? `\n${meta.reason}` : ''
          return (
            <div
              key={n.id}
              style={{
                position: 'absolute',
                left: `${leftPct}%`,
                top: `${topPct}%`,
                transform: 'translate(-50%, -50%)',
                width: rr * 2,
                height: rr * 2,
                borderRadius: '999px',
                overflow: 'hidden',
                border: '1.5px solid rgba(47,116,192,0.34)',
                background: 'rgba(47,116,192,0.14)',
                boxShadow: '0 6px 18px rgba(10,25,40,0.10)',
              }}
              title={`${n.label}${metaLine}${reasonLine}`}
            >
              <img
                src={src ?? undefined}
                alt={n.label}
                style={{ width: '100%', height: '100%', objectFit: 'cover', display: 'block' }}
                onError={() => setBroken((prev) => ({ ...prev, [n.id]: true }))}
              />
              <div
                style={{
                  position: 'absolute',
                  left: '50%',
                  top: '100%',
                  transform: 'translate(-50%, 8px)',
                  fontSize: 10,
                  color: 'rgba(12,20,34,0.72)',
                  whiteSpace: 'nowrap',
                  pointerEvents: 'none',
                }}
              >
                {n.label.length > 10 ? `${n.label.slice(0, 10)}…` : n.label}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}


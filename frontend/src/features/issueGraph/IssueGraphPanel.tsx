import { useEffect, useMemo, useState } from 'react'
import type { Issue } from '../../types/news'

type GraphNodeType = 'issue' | 'keyword' | 'press'
type GraphEdgeType = 'issue-keyword' | 'issue-press'

type GraphNode = {
  id: string
  label: string
  type: GraphNodeType
  imageUrl?: string | null
  thumbnailUrl?: string | null
  sourceUrl?: string | null
  weight?: number
}

type GraphEdge = {
  from: string
  to: string
  type?: GraphEdgeType
  weight?: number
}

type IssueGraph = {
  issueId: string
  nodes: GraphNode[]
  edges: GraphEdge[]
}

function apiBase(): string {
  return (import.meta as any).env?.VITE_API_BASE ?? 'http://127.0.0.1:8000'
}

function fallbackGraph(issue: Issue): IssueGraph {
  const centerId = `issue:${issue.issueId}`
  const nodes: GraphNode[] = [{ id: centerId, label: issue.title, type: 'issue', weight: 2 }]
  const edges: GraphEdge[] = []

  for (const keyword of (issue.keywords ?? []).slice(0, 10)) {
    const id = `kw:${keyword}`
    nodes.push({ id, label: keyword, type: 'keyword', weight: 1.4 })
    edges.push({ from: centerId, to: id, type: 'issue-keyword' })
  }

  for (const press of (issue.pressData ?? []).map((pressData) => pressData.press).filter(Boolean).slice(0, 8)) {
    const id = `press:${press}`
    nodes.push({ id, label: press, type: 'press' })
    edges.push({ from: centerId, to: id, type: 'issue-press' })
  }

  return { issueId: issue.issueId, nodes, edges }
}

async function fetchImageGraph(issue: Issue): Promise<IssueGraph> {
  const presses = (issue.pressData ?? []).map((pressData) => pressData.press).filter(Boolean)
  const response = await fetch(`${apiBase()}/api/issue-graph/extract`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      issueId: issue.issueId,
      title: issue.title,
      keywords: issue.keywords ?? [],
      presses,
    }),
  })

  if (!response.ok) {
    throw new Error(`issue graph API failed: HTTP ${response.status}`)
  }

  return (await response.json()) as IssueGraph
}

function nodeRadius(node: GraphNode) {
  if (node.type === 'issue') return 34
  if (node.type === 'keyword' && node.thumbnailUrl) return 26
  if (node.type === 'keyword') return 19
  return 17
}

function nodeStyle(node: GraphNode): { fill: string; stroke: string } {
  if (node.type === 'issue') return { fill: 'rgba(11,42,85,0.95)', stroke: 'rgba(47,116,192,0.45)' }
  if (node.type === 'press') return { fill: 'rgba(57,166,198,0.16)', stroke: 'rgba(57,166,198,0.35)' }
  return { fill: 'rgba(47,116,192,0.12)', stroke: 'rgba(47,116,192,0.32)' }
}

function edgeStroke() {
  return 'url(#edgeGrad)'
}

function labelFor(node: GraphNode) {
  return node.label.length > 12 ? `${node.label.slice(0, 12)}...` : node.label
}

function clipId(index: number) {
  return `keyword-image-clip-${index}`
}

function buildPositions(graph: IssueGraph, width: number, height: number) {
  const cx = width / 2
  const cy = height / 2
  const positions = new Map<string, { x: number; y: number }>()
  const center = graph.nodes.find((node) => node.type === 'issue') ?? graph.nodes[0]
  positions.set(center.id, { x: cx, y: cy })

  const relatedNodes = graph.nodes.filter((node) => node.id !== center.id)
  const radius = Math.min(width, height) * 0.33
  relatedNodes.forEach((node, index) => {
    const angle = (index / Math.max(1, relatedNodes.length)) * Math.PI * 2 - Math.PI / 2
    positions.set(node.id, {
      x: cx + Math.cos(angle) * radius,
      y: cy + Math.sin(angle) * radius,
    })
  })

  return positions
}

export function IssueGraphPanel(props: { issue: Issue }) {
  const fallback = useMemo(() => fallbackGraph(props.issue), [props.issue])
  const [remoteGraph, setRemoteGraph] = useState<IssueGraph | null>(null)
  const [status, setStatus] = useState<'loading' | 'ready' | 'fallback'>('loading')

  useEffect(() => {
    let cancelled = false
    setStatus('loading')
    setRemoteGraph(null)

    fetchImageGraph(props.issue)
      .then((graph) => {
        if (cancelled) return
        setRemoteGraph(graph)
        setStatus('ready')
      })
      .catch(() => {
        if (cancelled) return
        setStatus('fallback')
      })

    return () => {
      cancelled = true
    }
  }, [props.issue])

  const graph = remoteGraph ?? fallback
  const width = 720
  const height = 360
  const positions = useMemo(() => buildPositions(graph, width, height), [graph])

  return (
    <div className="nc-graphWrap">
      <div className="nc-muted" style={{ fontSize: 12 }}>
        {status === 'ready'
          ? 'Representative keyword images are displayed inside keyword nodes.'
          : status === 'loading'
            ? 'Loading keyword image graph...'
            : 'Image graph API is unavailable, showing the local issue graph.'}
      </div>

      <div className="nc-graphStage" role="img" aria-label="issue relationship graph">
        <svg viewBox={`0 0 ${width} ${height}`} width="100%" height="100%" preserveAspectRatio="xMidYMid meet">
          <defs>
            <linearGradient id="edgeGrad" x1="0" x2="1">
              <stop offset="0%" stopColor="rgba(47,116,192,0.55)" />
              <stop offset="100%" stopColor="rgba(57,166,198,0.45)" />
            </linearGradient>
            {graph.nodes.map((node, index) => {
              const position = positions.get(node.id)
              if (node.type !== 'keyword' || !node.thumbnailUrl || !position) return null
              const radius = nodeRadius(node)
              return <clipPath key={node.id} id={clipId(index)}><circle cx={position.x} cy={position.y} r={radius} /></clipPath>
            })}
          </defs>

          {graph.edges.map((edge) => {
            const from = positions.get(edge.from)
            const to = positions.get(edge.to)
            if (!from || !to) return null
            return (
              <line
                key={`${edge.from}->${edge.to}-${edge.type ?? 'edge'}`}
                x1={from.x}
                y1={from.y}
                x2={to.x}
                y2={to.y}
                stroke={edgeStroke()}
                strokeWidth="1.5"
                opacity="0.72"
              />
            )
          })}

          {graph.nodes.map((node, index) => {
            const position = positions.get(node.id)
            if (!position) return null
            const style = nodeStyle(node)
            const radius = nodeRadius(node)
            const hasKeywordImage = node.type === 'keyword' && Boolean(node.thumbnailUrl)

            return (
              <g key={node.id}>
                {hasKeywordImage ? (
                  <image
                    href={node.thumbnailUrl ?? ''}
                    x={position.x - radius}
                    y={position.y - radius}
                    width={radius * 2}
                    height={radius * 2}
                    preserveAspectRatio="xMidYMid slice"
                    clipPath={`url(#${clipId(index)})`}
                  />
                ) : (
                  <circle cx={position.x} cy={position.y} r={radius} fill={style.fill} stroke={style.stroke} strokeWidth="1.5" />
                )}
                {node.type === 'issue' ? (
                  <text x={position.x} y={position.y} textAnchor="middle" dominantBaseline="middle" fontSize="11" fill="rgba(255,255,255,0.95)">
                    ISSUE
                  </text>
                ) : null}
                {hasKeywordImage ? (
                  <circle cx={position.x} cy={position.y} r={radius} fill="none" stroke={style.stroke} strokeWidth="2" />
                ) : null}
                <text
                  x={position.x}
                  y={position.y + radius + 13}
                  textAnchor="middle"
                  fontSize="10"
                  fill="rgba(12,20,34,0.72)"
                >
                  {labelFor(node)}
                </text>
              </g>
            )
          })}
        </svg>
      </div>
    </div>
  )
}

import { useEffect, useMemo, useState } from 'react'
import type { Issue } from '../../types/news'

type GraphNodeType = 'issue' | 'keyword' | 'press'
type GraphEdgeType = 'issue-keyword' | 'issue-press' | 'keyword-relation'

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
  label?: string | null
  evidence?: string[]
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
  const keywords = (issue.keywords ?? []).slice(0, 10)
  const nodes: GraphNode[] = keywords.map((keyword) => ({
    id: `kw:${keyword}`,
    label: keyword,
    type: 'keyword',
    weight: 1.4,
  }))

  const edges: GraphEdge[] = nodes.slice(0, -1).map((node, index) => ({
    from: node.id,
    to: nodes[index + 1].id,
    type: 'keyword-relation',
    label: '관련',
    weight: 0.5,
  }))

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
      evidenceSentences: issue.evidenceSentences ?? [],
      commonFacts: issue.commonFacts ?? [],
    }),
  })

  if (!response.ok) {
    throw new Error(`issue graph API failed: HTTP ${response.status}`)
  }

  return (await response.json()) as IssueGraph
}

function nodeRadius(node: GraphNode) {
  if (node.type === 'keyword' && node.thumbnailUrl) return 26
  if (node.type === 'keyword') return 19
  return 17
}

function nodeStyle(node: GraphNode): { fill: string; stroke: string } {
  if (node.type === 'press') return { fill: 'rgba(57,166,198,0.16)', stroke: 'rgba(57,166,198,0.35)' }
  return { fill: 'rgba(47,116,192,0.12)', stroke: 'rgba(47,116,192,0.32)' }
}

function edgeStroke() {
  return 'url(#edgeGrad)'
}

function edgeLabel(edge: GraphEdge) {
  if (edge.type === 'keyword-relation') return edge.label ?? '관련'
  return edge.label ?? null
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

  const radius = Math.min(width, height) * 0.36
  graph.nodes.forEach((node, index) => {
    const angle = (index / Math.max(1, graph.nodes.length)) * Math.PI * 2 - Math.PI / 2
    positions.set(node.id, {
      x: cx + Math.cos(angle) * radius,
      y: cy + Math.sin(angle) * radius,
    })
  })

  return positions
}

function edgeEndpoints(from: { x: number; y: number }, to: { x: number; y: number }, fromRadius: number, toRadius: number) {
  const dx = to.x - from.x
  const dy = to.y - from.y
  const length = Math.hypot(dx, dy) || 1
  const ux = dx / length
  const uy = dy / length

  return {
    x1: from.x + ux * fromRadius,
    y1: from.y + uy * fromRadius,
    x2: to.x - ux * toRadius,
    y2: to.y - uy * toRadius,
  }
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
          ? 'Keyword nodes are connected by relation edges extracted from evidence sentences.'
          : status === 'loading'
            ? 'Loading keyword relation graph...'
            : 'Relation graph API is unavailable, showing local keyword relations.'}
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
            const fromNode = graph.nodes.find((node) => node.id === edge.from)
            const toNode = graph.nodes.find((node) => node.id === edge.to)
            if (!from || !to || !fromNode || !toNode) return null
            const endpoint = edgeEndpoints(from, to, nodeRadius(fromNode), nodeRadius(toNode))
            return (
              <g key={`${edge.from}->${edge.to}-${edge.type ?? 'edge'}-${edge.label ?? ''}`}>
                <line
                  x1={endpoint.x1}
                  y1={endpoint.y1}
                  x2={endpoint.x2}
                  y2={endpoint.y2}
                  stroke={edgeStroke()}
                  strokeWidth={edge.type === 'keyword-relation' ? 2.4 : 2}
                  opacity={edge.type === 'keyword-relation' ? 0.86 : 0.78}
                />
                {edgeLabel(edge) ? (
                  <text
                    x={(endpoint.x1 + endpoint.x2) / 2}
                    y={(endpoint.y1 + endpoint.y2) / 2 - 4}
                    textAnchor="middle"
                    fontSize="9"
                    fill="rgba(12,20,34,0.64)"
                    paintOrder="stroke"
                    stroke="rgba(255,255,255,0.9)"
                    strokeWidth="3"
                  >
                    {edgeLabel(edge)}
                  </text>
                ) : null}
              </g>
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

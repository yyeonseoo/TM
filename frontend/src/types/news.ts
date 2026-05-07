export type JobStatus = 'queued' | 'running' | 'done' | 'error'

export type CreateRunRequest = {
  categoryFilter: string
  targetCount: number
  linkPoolSize: number
}

export type CreateRunResponse = {
  runId: string
  collectJobId: string
}

export type AnalyzeResponse = {
  runId: string
  analyzeJobId: string
}

export type JobStatusResponse = {
  jobId: string
  status: JobStatus
  progress: number
  message: string
  runId?: string | null
  kind?: string | null
  createdAt?: string | null
  updatedAt?: string | null
  error?: string | null
}

export type Article = {
  articleId: string
  title: string
  press: string
  url: string
  publishedAt?: string | null
  contentPreview: string
}

export type ArticlesResponse = {
  runId: string
  articles: Article[]
}

export type PressData = {
  press: string
  summary: string
  emphasizedSentences: string[]
  missingFacts: string[]
  evidenceSentences: string[]
  keywords: string[]
  titles: string[]
  links: string[]
}

export type Issue = {
  issueId: string
  rank: number
  title: string
  keywords: string[]
  commonFacts: string[]
  pressData: PressData[]
  evidenceSentences: string[]
  summary: string
  controversies: Record<string, unknown>[]
}

export type IssuesResponse = {
  runId: string
  issues: Issue[]
}

export type TimeseriesPoint = {
  date: string
  count: number
}

export type TimeseriesArticle = {
  title: string
  description: string
  link: string
  originallink: string
  pubDate: string
  date: string
}

export type IssueTimeseriesResponse = {
  runId: string
  keyword: string
  totalCount: number
  series: TimeseriesPoint[]
  articles: TimeseriesArticle[]
}

export type GraphNode = {
  id: string
  kind?: string
  label?: string
  size?: number
  [k: string]: unknown
}

export type GraphEdge = {
  source: string
  target: string
  weight?: number
  kind?: string
  [k: string]: unknown
}

export type IssueGraphResponse = {
  runId: string
  issueId: string
  graph: {
    nodes: GraphNode[]
    links?: GraphEdge[]
    edges?: GraphEdge[]
    directed?: boolean
    multigraph?: boolean
    graph?: Record<string, unknown>
  }
}


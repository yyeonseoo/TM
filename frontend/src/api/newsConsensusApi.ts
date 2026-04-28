import type {
  AnalyzeResponse,
  ArticlesResponse,
  CreateRunRequest,
  CreateRunResponse,
  IssuesResponse,
  JobStatusResponse,
} from '../types/news'

const DEFAULT_BASE = 'http://127.0.0.1:8000'

function apiBase(): string {
  return (import.meta as any).env?.VITE_API_BASE ?? DEFAULT_BASE
}

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${apiBase()}${path}`, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...(init?.headers ?? {}),
    },
  })
  if (!res.ok) {
    const text = await res.text().catch(() => '')
    throw new Error(text || `HTTP ${res.status}`)
  }
  return (await res.json()) as T
}

export const newsConsensusApi = {
  createRun(payload: CreateRunRequest) {
    return requestJson<CreateRunResponse>('/api/runs', {
      method: 'POST',
      body: JSON.stringify(payload),
    })
  },
  getJob(jobId: string) {
    return requestJson<JobStatusResponse>(`/api/jobs/${encodeURIComponent(jobId)}`)
  },
  getArticles(runId: string) {
    return requestJson<ArticlesResponse>(`/api/runs/${encodeURIComponent(runId)}/articles`)
  },
  analyze(runId: string) {
    return requestJson<AnalyzeResponse>(`/api/runs/${encodeURIComponent(runId)}/analyze`, {
      method: 'POST',
    })
  },
  getIssues(runId: string) {
    return requestJson<IssuesResponse>(`/api/runs/${encodeURIComponent(runId)}/issues`)
  },
}


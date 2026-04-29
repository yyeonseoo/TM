import { useCallback, useState } from 'react'
import type { Issue } from '../types/news'
import { newsConsensusApi } from '../api/newsConsensusApi'

export function useIssues() {
  const [issues, setIssues] = useState<Issue[]>([])
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  const loadIssues = useCallback(async (runId: string) => {
    setLoading(true)
    setError(null)
    try {
      const res = await newsConsensusApi.getIssues(runId)
      setIssues(res.issues ?? [])
      return res.issues ?? []
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
      setIssues([])
      return []
    } finally {
      setLoading(false)
    }
  }, [])

  const clearIssues = useCallback(() => {
    setIssues([])
    setError(null)
    setLoading(false)
  }, [])

  return { issues, loading, error, loadIssues, clearIssues }
}


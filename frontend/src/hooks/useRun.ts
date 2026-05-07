import { useCallback, useState } from 'react'
import type { CreateRunRequest, CreateRunResponse } from '../types/news'
import { newsConsensusApi } from '../api/newsConsensusApi'

export function useRun() {
  const [runId, setRunId] = useState<string | null>(null)
  const [collectJobId, setCollectJobId] = useState<string | null>(null)
  const [analyzeJobId, setAnalyzeJobId] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const createRun = useCallback(async (payload: CreateRunRequest) => {
    setError(null)
    try {
      const res: CreateRunResponse = await newsConsensusApi.createRun(payload)
      setRunId(res.runId)
      setCollectJobId(res.collectJobId)
      setAnalyzeJobId(null)
      return res
    } catch (e) {
      const message = e instanceof Error ? e.message : String(e)
      setError(message)
      throw e
    }
  }, [])

  const startAnalyze = useCallback(async () => {
    if (!runId) throw new Error('runId is null')
    setError(null)
    try {
      const res = await newsConsensusApi.analyze(runId)
      setAnalyzeJobId(res.analyzeJobId)
      return res
    } catch (e) {
      const message = e instanceof Error ? e.message : String(e)
      setError(message)
      throw e
    }
  }, [runId])

  return {
    runId,
    collectJobId,
    analyzeJobId,
    error,
    setError,
    createRun,
    startAnalyze,
  }
}


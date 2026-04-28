import { useEffect, useMemo, useState } from 'react'
import type { JobStatusResponse } from '../types/news'
import { newsConsensusApi } from '../api/newsConsensusApi'

type PollingOptions = {
  enabled: boolean
  intervalMs?: number
}

export function useJobPolling(jobId: string | null, options: PollingOptions) {
  const intervalMs = options.intervalMs ?? 1200
  const [job, setJob] = useState<JobStatusResponse | null>(null)
  const [error, setError] = useState<string | null>(null)

  const isTerminal = useMemo(() => job?.status === 'done' || job?.status === 'error', [job?.status])

  useEffect(() => {
    if (!options.enabled || !jobId) return
    let cancelled = false

    async function tick() {
      try {
        const next = await newsConsensusApi.getJob(jobId)
        if (!cancelled) {
          setJob(next)
          setError(null)
        }
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : String(e))
      }
    }

    tick()
    const id = window.setInterval(() => {
      if (isTerminal) return
      void tick()
    }, intervalMs)

    return () => {
      cancelled = true
      window.clearInterval(id)
    }
  }, [jobId, options.enabled, intervalMs, isTerminal])

  return { job, error, isTerminal }
}


import { useEffect, useMemo, useState } from 'react'
import type { Article, Issue } from '../types/news'
import { newsConsensusApi } from '../api/newsConsensusApi'
import { useJobPolling } from '../hooks/useJobPolling'
import { useIssues } from '../hooks/useIssues'
import { useRun } from '../hooks/useRun'
import { ArticleTable } from '../components/ArticleTable'
import { ControlPanel } from '../components/ControlPanel'
import { Header } from '../components/Header'
import { IssueDetailPanel } from '../components/IssueDetailPanel'
import { IssueTopCards } from '../components/IssueTopCards'
import { JobProgressCard } from '../components/JobProgressCard'
import '../styles/newsConsensus.css'

export function NewsConsensusPage() {
  const { runId, collectJobId, analyzeJobId, error: runError, setError: setRunError, createRun, startAnalyze } = useRun()
  const collect = useJobPolling(collectJobId, { enabled: Boolean(collectJobId) })
  const analyze = useJobPolling(analyzeJobId, { enabled: Boolean(analyzeJobId) })
  const { issues, loadIssues, clearIssues, loading: issuesLoading, error: issuesError } = useIssues()

  const [categoryFilter, setCategoryFilter] = useState('politics')
  const [targetCount, setTargetCount] = useState(30)
  const [linkPoolSize, setLinkPoolSize] = useState(100)

  const [articles, setArticles] = useState<Article[]>([])
  const [articlesError, setArticlesError] = useState<string | null>(null)
  const [selectedIssueId, setSelectedIssueId] = useState<string | null>(null)

  const selectedIssue: Issue | null = useMemo(
    () => issues.find((i) => i.issueId === selectedIssueId) ?? (issues[0] ?? null),
    [issues, selectedIssueId],
  )

  useEffect(() => {
    if (!runId) return
    if (collect.job?.status !== 'done') return
    let cancelled = false
    ;(async () => {
      try {
        const res = await newsConsensusApi.getArticles(runId)
        if (!cancelled) {
          setArticles(res.articles ?? [])
          setArticlesError(null)
        }
      } catch (e) {
        if (!cancelled) setArticlesError(e instanceof Error ? e.message : String(e))
      }
    })()
    return () => {
      cancelled = true
    }
  }, [runId, collect.job?.status])

  useEffect(() => {
    if (!runId) return
    if (analyze.job?.status !== 'done') return
    void loadIssues(runId)
  }, [runId, analyze.job?.status, loadIssues])

  const badges = {
    collect: collect.job?.status ?? (collectJobId ? 'queued' : null),
    analyze: analyze.job?.status ?? (analyzeJobId ? 'queued' : null),
  }

  async function onCollect() {
    setRunError(null)
    setArticles([])
    clearIssues()
    setSelectedIssueId(null)
    await createRun({ categoryFilter, targetCount, linkPoolSize })
  }

  async function onAnalyze() {
    setRunError(null)
    await startAnalyze()
  }

  const canAnalyze = Boolean(runId && (collect.job?.status === 'done' || (articles?.length ?? 0) > 0))

  return (
    <div className="nc-page">
      <Header projectName="뉴스 이슈 분석 시스템" collectStatus={badges.collect} analyzeStatus={badges.analyze} />

      <div className="nc-layout">
        <aside className="nc-left">
          <ControlPanel
            categoryFilter={categoryFilter}
            setCategoryFilter={setCategoryFilter}
            targetCount={targetCount}
            setTargetCount={setTargetCount}
            linkPoolSize={linkPoolSize}
            setLinkPoolSize={setLinkPoolSize}
            onCollect={onCollect}
            onAnalyze={onAnalyze}
            canAnalyze={canAnalyze}
            busy={collect.job?.status === 'running' || analyze.job?.status === 'running'}
          />
          <section className="nc-section nc-sectionTight">
            <div className="nc-sectionTitle">수집된 기사 : {(articles?.length ?? 0).toString().padStart(2, '0')}개</div>
            <ArticleTable
              variant="compact"
              articles={articles}
              loading={collect.job?.status === 'running' || collect.job?.status === 'queued'}
            />
          </section>
        </aside>

        <main className="nc-center">
          <div className="nc-grid">
            <JobProgressCard title="수집 진행률" job={collect.job} error={collect.error} kind="collect" />
            <JobProgressCard title="분석 진행률" job={analyze.job} error={analyze.error} kind="analyze" />
          </div>

          {(runError || articlesError || issuesError) && (
            <div className="nc-alert">
              <div className="nc-alertTitle">에러</div>
              <div className="nc-alertBody">{runError || articlesError || issuesError}</div>
            </div>
          )}

          <section className="nc-section">
            <div className="nc-sectionTitle">이슈 TOP 3</div>
            <IssueTopCards
              issues={issues}
              loading={issuesLoading || analyze.job?.status === 'running' || analyze.job?.status === 'queued'}
              selectedIssueId={selectedIssue?.issueId ?? null}
              onSelect={setSelectedIssueId}
            />
          </section>

          <section className="nc-section">
            <div className="nc-sectionTitle">이슈 상세</div>
            <IssueDetailPanel issue={selectedIssue} runId={runId} />
          </section>
        </main>
      </div>
    </div>
  )
}


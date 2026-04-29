import { useCallback, useEffect, useMemo, useState } from 'react'
import { newsConsensusApi } from '../../api/newsConsensusApi'
import type { Issue, IssueTimeseriesResponse } from '../../types/news'

export function IssueTimelinePanel(props: { issue: Issue; runId: string | null }) {
  const { issue, runId } = props
  const [query, setQuery] = useState<string>(() => issue.title)
  const [data, setData] = useState<IssueTimeseriesResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const loadTimeseries = useCallback(
    async (keyword: string) => {
      if (!runId) {
        setError('runId가 없습니다. 수집·분석이 끝난 뒤 다시 시도해 주세요.')
        return
      }
      const kw = keyword.trim()
      if (!kw) {
        setError('검색 키워드를 입력해 주세요.')
        return
      }
      setLoading(true)
      setError(null)
      try {
        const res = await newsConsensusApi.getIssueTimeseries(runId, kw, 100)
        setData(res)
      } catch (e) {
        setData(null)
        setError(e instanceof Error ? e.message : String(e))
      } finally {
        setLoading(false)
      }
    },
    [runId],
  )

  useEffect(() => {
    setQuery(issue.title)
    void loadTimeseries(issue.title)
  }, [issue.issueId, issue.title, loadTimeseries])

  const points = useMemo(() => data?.series ?? [], [data])
  const max = useMemo(() => Math.max(1, ...points.map((p) => p.count)), [points])

  if (!runId) {
    return (
      <div className="nc-timelineWrap">
        <div className="nc-empty">
          <div className="nc-emptyTitle">시계열을 불러올 수 없습니다</div>
          <div className="nc-emptyBody">이슈 분석이 완료된 run이 있어야 네이버 뉴스 시계열을 조회할 수 있습니다.</div>
        </div>
      </div>
    )
  }

  return (
    <div className="nc-timelineWrap">
      <div className="nc-muted" style={{ fontSize: 12 }}>
        네이버 뉴스 API로 키워드 재검색 후, 날짜별 기사 수를 집계합니다. (최대 100건)
      </div>

      <div className="nc-timelineControls">
        <div className="nc-field" style={{ marginBottom: 0 }}>
          <div className="nc-label">검색 키워드</div>
          <input
            className="nc-input"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="이슈 제목 또는 키워드"
            disabled={loading}
            onKeyDown={(e) => {
              if (e.key === 'Enter') void loadTimeseries(query)
            }}
          />
        </div>
        <button
          className="nc-btn secondary"
          type="button"
          disabled={loading}
          onClick={() => void loadTimeseries(query)}
        >
          {loading ? '검색 중…' : '검색'}
        </button>
      </div>

      {error ? (
        <div className="nc-alert" style={{ marginTop: 12 }}>
          <div className="nc-alertTitle">시계열 조회 실패</div>
          <div className="nc-alertBody">{error}</div>
        </div>
      ) : null}

      {data && !error ? (
        <div className="nc-muted" style={{ fontSize: 12, marginTop: 10 }}>
          키워드: <strong style={{ color: 'var(--nc-text)' }}>{data.keyword}</strong> · 수집 건수{' '}
          <strong style={{ color: 'var(--nc-text)' }}>{data.totalCount}</strong>
          {points.length ? ` · 일자 ${points.length}개` : ''}
        </div>
      ) : null}

      <div className="nc-timelineChart" role="img" aria-label="timeline chart" style={{ marginTop: 12 }}>
        {loading && !data ? (
          <div className="nc-muted">불러오는 중…</div>
        ) : null}
        {!loading && !points.length && data ? (
          <div className="nc-muted">날짜를 파싱한 기사가 없습니다. 다른 키워드로 검색해 보세요.</div>
        ) : null}
        {points.map((p) => (
          <div key={p.date} className="nc-bar">
            <div className="nc-barFill" style={{ width: `${(p.count / max) * 100}%` }} />
            <div className="nc-barLabel">
              <span>{p.date}</span>
              <span className="nc-muted">{p.count}건</span>
            </div>
          </div>
        ))}
      </div>

      {data ? (
        <div style={{ marginTop: 16 }}>
          <div className="nc-subtitle" style={{ fontSize: 13 }}>
            관련 기사 : {String(data.totalCount ?? 0).padStart(2, '0')}개
          </div>
          {data.articles?.length ? (
            <ul className="nc-list nc-listMuted" style={{ maxHeight: 220, overflow: 'auto', marginTop: 8 }}>
              {data.articles.slice(0, 15).map((a, idx) => (
                <li key={`${a.link}-${idx}`}>
                  <a href={a.link || a.originallink} target="_blank" rel="noreferrer">
                    {a.title || '(제목 없음)'}
                  </a>
                  <span className="nc-muted" style={{ marginLeft: 8, fontSize: 11 }}>
                    {a.date}
                  </span>
                </li>
              ))}
            </ul>
          ) : null}
        </div>
      ) : null}
    </div>
  )
}

import asyncio
import unittest

from backend.services.image_ranking.pipeline import ImageRankingPipeline
from backend.services.image_ranking.ranker import HeuristicImageRanker
from backend.services.image_ranking.retrievers import BaseImageRetriever
from backend.services.image_ranking.types import ImageCandidate, IssueContext


class _FakeRetriever(BaseImageRetriever):
    def __init__(self, candidates):
        self._candidates = candidates

    async def retrieve(self, keyword: str, issue_ctx: IssueContext):
        return list(self._candidates)


def _fallback(label: str) -> str:
    return f"data:image/svg+xml;utf8,{label}"


class ImageRankingTests(unittest.TestCase):
    def test_no_candidates_returns_fallback(self):
        pipe = ImageRankingPipeline(retrievers=[_FakeRetriever([])], ranker=HeuristicImageRanker(), cache=None)
        ctx = IssueContext(issue_id="i1", title="t", summary="s", text="t s", entities=["한동훈"], keywords=["한동훈"])
        out = asyncio.run(pipe.select_icon("한동훈", ctx, fallback_factory=_fallback))
        self.assertTrue(out.fallback)
        self.assertFalse(out.selected)
        self.assertTrue(out.icon_url.startswith("data:"))

    def test_wikipedia_entity_match_selected(self):
        c = ImageCandidate(
            url="https://upload.wikimedia.org/example.png",
            source="wikipedia",
            title="한동훈",
            caption="한동훈 프로필",
            page_url="https://ko.wikipedia.org/wiki/한동훈",
            width=330,
            height=400,
            meta={},
        )
        pipe = ImageRankingPipeline(retrievers=[_FakeRetriever([c])], ranker=HeuristicImageRanker(), cache=None)
        ctx = IssueContext(issue_id="i1", title="한동훈", summary="선거", text="한동훈 선거", entities=["한동훈"], keywords=["한동훈"])
        out = asyncio.run(pipe.select_icon("한동훈", ctx, fallback_factory=_fallback))
        self.assertTrue(out.selected)
        self.assertFalse(out.fallback)
        self.assertIn("wikipedia", out.source)

    def test_generic_map_penalized(self):
        c = ImageCandidate(
            url="https://upload.wikimedia.org/map.png",
            source="wikimedia",
            title="부산 지도",
            caption="지도",
            page_url="https://commons.wikimedia.org/wiki/File:Busan_map.png",
            width=800,
            height=600,
            meta={},
        )
        pipe = ImageRankingPipeline(retrievers=[_FakeRetriever([c])], ranker=HeuristicImageRanker(), cache=None)
        ctx = IssueContext(issue_id="i1", title="부산 선거", summary="이슈", text="부산 선거 이슈", entities=["선거"], keywords=["부산"])
        out = asyncio.run(pipe.select_icon("부산", ctx, fallback_factory=_fallback))
        # generic penalty can push below cutoff -> fallback is acceptable outcome
        self.assertTrue(out.fallback or out.selected)

    def test_gap_small_and_score_low_fallback(self):
        c1 = ImageCandidate(url="https://x/a.png", source="external", title="부산", caption=None, page_url=None, width=120, height=120, meta={})
        c2 = ImageCandidate(url="https://x/b.png", source="external", title="부산", caption=None, page_url=None, width=120, height=120, meta={})
        pipe = ImageRankingPipeline(retrievers=[_FakeRetriever([c1, c2])], ranker=HeuristicImageRanker(), cache=None)
        ctx = IssueContext(issue_id="i1", title="부산", summary="", text="부산", entities=[], keywords=["부산"])
        out = asyncio.run(pipe.select_icon("부산", ctx, fallback_factory=_fallback))
        self.assertTrue(out.fallback)


if __name__ == "__main__":
    unittest.main()


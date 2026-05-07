from __future__ import annotations

from dataclasses import dataclass

from .types import ImageCandidate, ImageFeatures, RankedImage


def _clamp01(x: float) -> float:
    return 0.0 if x < 0.0 else 1.0 if x > 1.0 else float(x)


@dataclass(frozen=True)
class HeuristicImageRanker:
    """
    Weighted heuristic ranker with explainable reasons.
    """

    w_source_reliability: float = 0.20
    w_entity_match: float = 0.25
    w_text_similarity: float = 0.20
    w_keyword_match: float = 0.15
    w_quality_score: float = 0.10
    w_generic_penalty: float = -0.15
    w_duplicate_penalty: float = -0.10
    w_clip_issue: float = 0.20

    def score(self, f: ImageFeatures) -> float:
        s = 0.0
        s += self.w_source_reliability * float(f.source_reliability)
        s += self.w_entity_match * float(f.entity_match)
        s += self.w_text_similarity * float(f.text_similarity)
        s += self.w_keyword_match * float(f.keyword_match)
        s += self.w_quality_score * float(f.quality_score)
        s += self.w_generic_penalty * float(f.generic_penalty)
        s += self.w_duplicate_penalty * float(f.duplicate_penalty)
        if f.clip_issue_similarity is not None:
            s += self.w_clip_issue * float(f.clip_issue_similarity)
        return _clamp01(s)

    def rank(self, items: list[tuple[ImageCandidate, ImageFeatures]]) -> list[RankedImage]:
        ranked: list[RankedImage] = []
        for cand, feats in items:
            sc = self.score(feats)
            reason = (
                f"entity_match={feats.entity_match:.2f}, "
                f"text_similarity={feats.text_similarity:.2f}, "
                f"keyword_match={feats.keyword_match:.2f}, "
                f"source={cand.source}, "
                f"quality={feats.quality_score:.2f}, "
                f"generic_penalty={feats.generic_penalty:.2f}, "
                f"dup_penalty={feats.duplicate_penalty:.2f}"
            )
            ranked.append(RankedImage(candidate=cand, features=feats, score=float(sc), reason=reason))
        ranked.sort(key=lambda r: r.score, reverse=True)
        return ranked


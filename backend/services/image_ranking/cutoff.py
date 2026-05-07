from __future__ import annotations

from .types import RankedImage


def adaptive_cutoff(ranked_images: list[RankedImage]) -> tuple[RankedImage | None, str]:
    if not ranked_images:
        return None, "no_candidates"

    top1 = ranked_images[0]
    s1 = float(top1.score)
    s2 = float(ranked_images[1].score) if len(ranked_images) > 1 else 0.0
    gap = s1 - s2

    if s1 < 0.45:
        return None, f"fallback_low_score(s1={s1:.2f})"

    if s1 >= 0.55 and gap >= 0.08:
        return top1, f"select_gap(s1={s1:.2f},gap={gap:.2f})"

    if s1 >= 0.50 and top1.candidate.source in ("wikipedia", "article"):
        return top1, f"select_trusted_source(s1={s1:.2f},source={top1.candidate.source})"

    if gap < 0.05:
        return None, f"fallback_flat(gap={gap:.2f})"

    return None, f"fallback_uncertain(s1={s1:.2f},gap={gap:.2f})"


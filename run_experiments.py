from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from graph_pipeline.pipeline import PipelineConfig, run_full_graph_pipeline
from graph_pipeline.utils.io import load_issues_from_csv, read_json


def _load_input(path: Path) -> list[dict[str, Any]]:
    if path.suffix.lower() == ".json":
        obj = read_json(path)
        if isinstance(obj, dict) and "issues" in obj and isinstance(obj["issues"], list):
            return obj["issues"]
        if isinstance(obj, list):
            return obj
        raise ValueError("JSON input must be a list[issue] or an object with key 'issues' as list.")

    if path.suffix.lower() == ".csv":
        issues = load_issues_from_csv(path)
        return [
            {
                "issueid": it.issueid,
                "articles": it.articles,
                "keywords": it.keywords,
                **({"label": it.label} if it.label is not None else {}),
            }
            for it in issues
        ]

    raise ValueError(f"Unsupported input type: {path.suffix}")


def main() -> None:
    ap = argparse.ArgumentParser(description="Run graph pipeline experiments.")
    ap.add_argument("--input", required=True, help="Input issues file (.json or .csv).")
    ap.add_argument("--output", required=True, help="Output report path (.json).")
    ap.add_argument("--no-png", action="store_true", help="Disable graph PNG rendering.")
    ap.add_argument("--kg", action="store_true", help="Enable knowledge graph extraction (pluggable NER).")
    ap.add_argument("--keyword-threshold", type=float, default=0.0, help="Drop keywords with importance < threshold.")
    args = ap.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)

    issues = _load_input(input_path)

    cfg = PipelineConfig(
        output_dir=str(output_path.parent),
        draw_graph_png=not args.no_png,
        use_knowledge_graph=bool(args.kg),
    )
    cfg = PipelineConfig(
        output_dir=str(output_path.parent),
        draw_graph_png=not args.no_png,
        use_knowledge_graph=bool(args.kg),
        weighted_graph_config=cfg.weighted_graph_config.__class__(  # type: ignore
            keyword_importance_threshold=float(args.keyword_threshold),
            min_degree_non_issue=cfg.weighted_graph_config.min_degree_non_issue,
            keyword_size_min=cfg.weighted_graph_config.keyword_size_min,
            keyword_size_max=cfg.weighted_graph_config.keyword_size_max,
            issue_size=cfg.weighted_graph_config.issue_size,
            press_size_min=cfg.weighted_graph_config.press_size_min,
            press_size_max=cfg.weighted_graph_config.press_size_max,
            press_size_article_weight=cfg.weighted_graph_config.press_size_article_weight,
            press_size_keyword_weight=cfg.weighted_graph_config.press_size_keyword_weight,
            normalize_edge_weights=cfg.weighted_graph_config.normalize_edge_weights,
        ),
    )

    report = run_full_graph_pipeline(issues, config=cfg)

    # Write final report to requested path (copy of results/report.json)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    from graph_pipeline.utils.io import write_json

    write_json(output_path, report)

    print(f"Wrote report to: {output_path}")


if __name__ == "__main__":
    main()


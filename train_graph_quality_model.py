from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from graph_pipeline.models.graph_quality_model import (
    save_graph_quality_model,
    train_graph_quality_model,
)


def _load_issues(path: Path) -> list[dict[str, Any]]:
    obj = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(obj, dict) and "issues" in obj and isinstance(obj["issues"], list):
        return obj["issues"]
    if isinstance(obj, list):
        return obj
    raise ValueError("Input must be list[issue] or {issues:[...]}")


def main() -> None:
    ap = argparse.ArgumentParser(description="Train self-supervised graph quality model (original vs corrupted).")
    ap.add_argument("--input", required=True, help="Issues JSON (list or {issues:[...]}).")
    ap.add_argument(
        "--output",
        default="backend/data/graph_quality_model.joblib",
        help="Output model artifact path.",
    )
    ap.add_argument(
        "--metrics-out",
        default=None,
        help="Optional metrics json output path (default: <output>.metrics.json).",
    )
    args = ap.parse_args()

    issues = _load_issues(Path(args.input))
    artifact = train_graph_quality_model(issues, return_metrics=True)
    save_graph_quality_model(artifact, args.output)
    print(f"Wrote model artifact to: {args.output}")

    metrics = artifact.get("metrics")
    if metrics is not None:
        metrics_path = Path(args.metrics_out) if args.metrics_out else Path(str(args.output) + ".metrics.json")
        metrics_path.parent.mkdir(parents=True, exist_ok=True)
        metrics_path.write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Wrote metrics to: {metrics_path}")


if __name__ == "__main__":
    main()


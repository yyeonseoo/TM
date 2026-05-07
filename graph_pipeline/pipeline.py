from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import networkx as nx

from graph_pipeline.evaluation.self_supervised import evaluate_graphs_self_supervised
from graph_pipeline.evaluation.supervised import evaluate_graphs_supervised
from graph_pipeline.graphs.features import extract_graph_features
from graph_pipeline.graphs.knowledge_graph import extract_knowledge_graph
from graph_pipeline.graphs.weighted_graph import WeightedGraphBuildConfig, build_weighted_graph
from graph_pipeline.graphs.visualize import visualize_graph
from graph_pipeline.utils.io import ensure_issue_dicts, write_json


@dataclass(frozen=True)
class PipelineConfig:
    """
    End-to-end pipeline configuration.
    """

    output_dir: str = "results"
    draw_graph_png: bool = True
    draw_graph_html: bool = True
    weighted_graph_config: WeightedGraphBuildConfig = WeightedGraphBuildConfig()
    use_knowledge_graph: bool = False
    evaluate_pruning_comparison: bool = True


def _clone_config_no_prune(cfg: WeightedGraphBuildConfig) -> WeightedGraphBuildConfig:
    return WeightedGraphBuildConfig(
        keyword_importance_threshold=0.0,
        min_degree_non_issue=0,
        keyword_size_min=cfg.keyword_size_min,
        keyword_size_max=cfg.keyword_size_max,
        issue_size=cfg.issue_size,
        press_size_min=cfg.press_size_min,
        press_size_max=cfg.press_size_max,
        press_size_article_weight=cfg.press_size_article_weight,
        press_size_keyword_weight=cfg.press_size_keyword_weight,
        normalize_edge_weights=cfg.normalize_edge_weights,
    )


def run_full_graph_pipeline(
    all_issue_data: List[dict[str, Any]] | List[Any],
    *,
    config: PipelineConfig | None = None,
) -> Dict[str, Any]:
    """
    Run the full pipeline:
    - build weighted graph per issue (+ optional KG)
    - extract feature vectors
    - supervised evaluation (if labels exist)
    - self-supervised evaluation (original vs corrupted)
    - save per-issue artifacts (json/png) and summary report
    """
    cfg = config or PipelineConfig()
    out_dir = Path(cfg.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    issues = ensure_issue_dicts(all_issue_data)
    per_issue: list[dict[str, Any]] = []
    graphs: list[nx.Graph] = []
    features: list[dict[str, float]] = []
    labels: list[str] = []

    for issue in issues:
        issueid = str(issue.get("issueid") or issue.get("issueId") or issue.get("issue_id") or "issue")
        # Build both: raw (no pruning) vs pruned (cfg)
        raw_cfg = _clone_config_no_prune(cfg.weighted_graph_config) if cfg.evaluate_pruning_comparison else None
        G_raw, export_raw = build_weighted_graph(issue, config=raw_cfg) if raw_cfg else (None, None)
        G, export_json = build_weighted_graph(issue, config=cfg.weighted_graph_config)
        graphs.append(G)

        feat = extract_graph_features(G, issue_data=issue)
        features.append(feat)
        feat_raw = extract_graph_features(G_raw, issue_data=issue) if G_raw is not None else None

        issue_out: dict[str, Any] = {
            "issueid": issueid,
            "weightedgraph": export_json,
            "features": feat,
            "pruning": {
                "keyword_importance_threshold": cfg.weighted_graph_config.keyword_importance_threshold,
                "min_degree_non_issue": cfg.weighted_graph_config.min_degree_non_issue,
            },
        }
        if G_raw is not None and export_raw is not None:
            issue_out["weightedgraph_raw"] = export_raw
            issue_out["features_raw"] = feat_raw

        if cfg.use_knowledge_graph:
            KG, triples = extract_knowledge_graph(issue)
            issue_out["knowledgegraph"] = {
                "nodes": [{"id": n, **KG.nodes[n]} for n in KG.nodes()],
                "edges": [{"source": u, "target": v, **d} for u, v, d in KG.edges(data=True)],
                "triples": triples,
            }

        if cfg.draw_graph_png or cfg.draw_graph_html:
            base_path = out_dir / "graphs" / issueid / "weighted_graph"
            try:
                vis = visualize_graph(G, base_path)
                if cfg.draw_graph_png:
                    issue_out["weightedgraph_png"] = vis.get("png")
                if cfg.draw_graph_html:
                    issue_out["weightedgraph_html"] = vis.get("html")
            except Exception as e:
                issue_out["weightedgraph_visualize_error"] = str(e)

        # per-issue JSON
        issue_json_path = out_dir / "issues" / f"{issueid}.json"
        write_json(issue_json_path, issue_out)
        issue_out["output_json"] = str(issue_json_path)

        # optional label
        if "label" in issue and issue["label"] is not None:
            labels.append(str(issue["label"]))

        per_issue.append(issue_out)

    # evaluations
    evaluation: dict[str, Any] = {}
    if labels and len(labels) == len(features) and len(set(labels)) >= 2:
        evaluation["supervised"] = evaluate_graphs_supervised(features, labels)
    else:
        evaluation["supervised"] = None

    evaluation["selfsupervised"] = evaluate_graphs_self_supervised(
        graphs,
        lambda g: extract_graph_features(g),
    )

    # Optional comparison: evaluate on raw vs pruned feature sets (if labels exist)
    if cfg.evaluate_pruning_comparison and labels and len(labels) == len(features) and len(set(labels)) >= 2:
        try:
            raw_features = []
            for issue in issues:
                G0, _ = build_weighted_graph(issue, config=_clone_config_no_prune(cfg.weighted_graph_config))
                raw_features.append(extract_graph_features(G0, issue_data=issue))
            evaluation["supervised_raw"] = evaluate_graphs_supervised(raw_features, labels)
        except Exception:
            evaluation["supervised_raw"] = None
    else:
        evaluation["supervised_raw"] = None

    report = {
        "summary": {
            "num_issues": len(issues),
            "has_labels": bool(labels) and len(labels) == len(issues),
        },
        "evaluation": evaluation,
        "issues": [{"issueid": x["issueid"], "output_json": x.get("output_json")} for x in per_issue],
    }

    write_json(out_dir / "report.json", report)
    return report


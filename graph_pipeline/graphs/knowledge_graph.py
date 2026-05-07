from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Iterable, Optional

import networkx as nx


@dataclass(frozen=True)
class KGTriple:
    """A knowledge graph triple with confidence."""

    subject: str
    relation: str
    object: str
    confidence: float = 1.0


@dataclass(frozen=True)
class KnowledgeGraphConfig:
    """
    Configuration for knowledge graph extraction.

    This module is intentionally lightweight:
    - NER is pluggable via `ner_fn` to avoid forcing model downloads at runtime.
    - Relation extraction is rule-based via `relation_rules`.
    """

    min_confidence: float = 0.0


def _default_normalize_entity(text: str) -> str:
    return " ".join(text.strip().split())


def extract_knowledge_graph(
    issue_data: dict[str, Any],
    *,
    ner_fn: Optional[Callable[[str], Iterable[tuple[str, str, float]]]] = None,
    relation_rules: Optional[list[Callable[[str, list[str]], list[KGTriple]]]] = None,
    normalize_entity_fn: Callable[[str], str] = _default_normalize_entity,
    config: KnowledgeGraphConfig | None = None,
) -> tuple[nx.MultiDiGraph, list[dict[str, Any]]]:
    """
    Extract a directed knowledge graph (MultiDiGraph) from issue data.

    Parameters
    - ner_fn: function(text) -> iterable of (entity_text, entity_type, confidence)
      If None, uses a trivial placeholder that returns no entities.
    - relation_rules: list of functions (text, entities) -> list[KGTriple]
      Rules can be regex-based, dependency-pattern-based, etc.

    Output
    - MultiDiGraph with edges (subject -> object) and attributes:
      relation, confidence, source_issue
    - triples list as JSON-serializable dicts
    """
    cfg = config or KnowledgeGraphConfig()
    issueid = str(issue_data.get("issueid") or issue_data.get("issueId") or "issue")
    articles = issue_data.get("articles") or []

    if ner_fn is None:
        def ner_fn(_: str):
            return []

    relation_rules = relation_rules or []

    G = nx.MultiDiGraph()
    triples: list[KGTriple] = []

    for a in articles:
        if not isinstance(a, dict):
            continue
        text = " ".join(
            [str(a.get("title") or ""), str(a.get("rawtext") or a.get("content") or "")]
        ).strip()
        if not text:
            continue

        ents = []
        for ent_text, ent_type, conf in ner_fn(text):
            if conf < cfg.min_confidence:
                continue
            norm = normalize_entity_fn(str(ent_text))
            if not norm:
                continue
            ents.append(norm)
            G.add_node(norm, kind="entity", entity_type=str(ent_type))

        for rule in relation_rules:
            try:
                new_triples = rule(text, ents)
            except Exception:
                continue
            for t in new_triples:
                if t.confidence < cfg.min_confidence:
                    continue
                triples.append(t)
                G.add_edge(
                    t.subject,
                    t.object,
                    relation=t.relation,
                    confidence=float(t.confidence),
                    source_issue=issueid,
                )

    triples_json = [
        {"subject": t.subject, "relation": t.relation, "object": t.object, "confidence": float(t.confidence)}
        for t in triples
    ]
    return G, triples_json


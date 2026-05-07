from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import networkx as nx


def _importance_color(val01: float) -> str:
    """
    Blue-light gradient for keyword importance.
    """
    v = max(0.0, min(1.0, float(val01)))
    # interpolate between light blue and deeper blue
    r1, g1, b1 = (176, 224, 255)
    r2, g2, b2 = (47, 116, 192)
    r = int(r1 + (r2 - r1) * v)
    g = int(g1 + (g2 - g1) * v)
    b = int(b1 + (b2 - b1) * v)
    return f"#{r:02x}{g:02x}{b:02x}"


def visualize_graph(G: nx.Graph, filename: str | Path) -> dict[str, str]:
    """
    Visualize a weighted graph with improved readability.

    - spring layout: k = 1/sqrt(n), iterations=200
    - node size uses node attribute `size` (issue biggest, keyword scaled, press medium)
    - edge width uses normalized weight (`weight_norm` if available else `weight`)
    - labels: only top-5 keywords + top-5 presses by size
    - saves:
      - PNG: <filename>.png
      - HTML (pyvis): <filename>.html
    """
    base = Path(filename)
    base.parent.mkdir(parents=True, exist_ok=True)

    n = max(1, G.number_of_nodes())
    pos = nx.spring_layout(G, seed=42, k=1 / math.sqrt(n), iterations=200, weight="weight")

    # node styles
    node_sizes = []
    node_colors = []
    for node, attrs in G.nodes(data=True):
        kind = attrs.get("kind", "")
        size = float(attrs.get("size", 20.0))
        node_sizes.append(size)
        if kind == "issue":
            node_colors.append("#0B2A55")  # dark navy
        elif kind == "press":
            node_colors.append("#5B6F86")  # grey-blue
        elif kind == "keyword":
            imp = float(attrs.get("importance", 0.0))
            # map imp to [0,1] roughly assuming importance in [0,1]
            node_colors.append(_importance_color(max(0.0, min(1.0, imp))))
        else:
            node_colors.append("#999999")

    # edge styles
    widths = []
    for _, _, d in G.edges(data=True):
        w = d.get("weight_norm", d.get("weight", 0.0))
        try:
            w = float(w)
        except Exception:
            w = 0.0
        widths.append(0.6 + 5.0 * max(0.0, min(1.0, w)))

    plt.figure(figsize=(11, 8))
    nx.draw_networkx_nodes(G, pos, node_size=node_sizes, node_color=node_colors, alpha=0.92, linewidths=0.5, edgecolors="white")
    nx.draw_networkx_edges(G, pos, width=widths, alpha=0.4)

    # minimal labels
    keywords = [(n, float(G.nodes[n].get("size", 0.0))) for n in G.nodes() if G.nodes[n].get("kind") == "keyword"]
    presses = [(n, float(G.nodes[n].get("size", 0.0))) for n in G.nodes() if G.nodes[n].get("kind") == "press"]
    top_kw = {n for n, _ in sorted(keywords, key=lambda x: x[1], reverse=True)[:5]}
    top_press = {n for n, _ in sorted(presses, key=lambda x: x[1], reverse=True)[:5]}
    label_nodes = top_kw | top_press | {n for n in G.nodes() if G.nodes[n].get("kind") == "issue"}
    labels = {n: str(G.nodes[n].get("label", n))[:16] for n in label_nodes}
    nx.draw_networkx_labels(G, pos, labels=labels, font_size=9)

    plt.axis("off")
    plt.tight_layout()
    png_path = base.with_suffix(".png")
    plt.savefig(png_path, dpi=180)
    plt.close()

    # HTML via pyvis (optional)
    html_path = base.with_suffix(".html")
    try:
        from pyvis.network import Network  # type: ignore

        net = Network(height="720px", width="100%", directed=False, bgcolor="#ffffff")
        for node, attrs in G.nodes(data=True):
            kind = attrs.get("kind", "")
            size = float(attrs.get("size", 20.0))
            label = str(attrs.get("label", node))
            color = "#0B2A55" if kind == "issue" else ("#5B6F86" if kind == "press" else _importance_color(float(attrs.get("importance", 0.0))))
            title = f"{kind} | {label}"
            net.add_node(node, label=label if node in label_nodes else "", title=title, color=color, size=size / 8)
        for u, v, d in G.edges(data=True):
            w = d.get("weight_norm", d.get("weight", 0.0))
            try:
                w = float(w)
            except Exception:
                w = 0.0
            net.add_edge(u, v, value=max(0.1, w), title=str(d.get("kind", "")))
        net.force_atlas_2based()
        net.write_html(str(html_path))
    except Exception:
        # If pyvis isn't installed, skip HTML silently.
        pass

    return {"png": str(png_path), "html": str(html_path)}


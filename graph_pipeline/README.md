## Graph pipeline (Weighted graph / KG / Evaluation)

This folder implements an end-to-end graph pipeline for issue-level news data:

- Weighted undirected graph construction (MVP)
- Optional knowledge graph extraction (pluggable NER + rule-based relations)
- Graph feature extraction
- Supervised evaluation (if `label` exists)
- Self-supervised evaluation (original vs corrupted graphs)

### Quick start (CLI)

From repo root:

```bash
python run_experiments.py --input data/issues.csv --output results/report.json
```

Outputs:

- `results/report.json`
- `results/issues/<issueid>.json`
- `results/graphs/<issueid>.png` (unless `--no-png`)

### Input formats

- **JSON**: list of issue objects (or `{ "issues": [...] }`)
- **CSV**: the repo’s `data/issues.csv` (converted into the prompt-like schema)

### Notes

- The repo’s `data/issues.csv` is aggregated, so per-article raw sentences are synthesized from `press_data` evidence.
- Knowledge graph extraction is optional and intentionally lightweight by default. Pass your own `ner_fn` and `relation_rules` if you want a real KG.


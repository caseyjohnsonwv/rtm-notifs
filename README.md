Ingest: `uv run scrape.py`

Search: `uv run search.py --regex "/string/i"`

Two-stage run (scrape, then search | notify):

```bash
uv run scrape.py
uv run search.py --regex '/rare|first edition|signed/i' --limit 20 | uv run notify_from_jsonl.py --name 'Rare Books' --topic-env NTFY_TOPIC_RARE_BOOKS --limit 20
```

## GitHub Actions schedule

Workflow: `.github/workflows/scheduled-search.yml`

- Runs daily on cron and supports manual `workflow_dispatch`
- Stage 1: rebuild `products.db` by running `scrape.py`
- Stage 2: run chained `search.py | notify_from_jsonl.py` commands

## Required GitHub Secrets

Set one secret per configured topic, for example:

- `NTFY_TOPIC_RARE_BOOKS`
- `NTFY_TOPIC_VINTAGE_TOYS`

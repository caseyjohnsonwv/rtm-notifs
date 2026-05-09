import argparse
from datetime import datetime
import json
import os
import sys
from typing import Any

import apprise
import pytz


US_EAST_TZ = pytz.timezone('US/Eastern')


def _build_message(rows: list[dict[str, Any]]) -> str:
    lines: list[str] = []
    for i,row in enumerate(rows):
        name = str(row["name"]).strip().replace("\n", " ")
        price = float(row["price"])
        updated = datetime.fromisoformat(str(row["updated_date"])).astimezone(US_EAST_TZ).strftime('%-I:%M%p on %-m/%-d/%Y').lower()
        lines.append(f"#{i+1} - ${price:.2f}\n{name}\n(Updated at {updated})")
    return "\n\n-----\n".join(lines).strip()


def run(name: str, topic_env: str) -> int:
    topic = os.getenv(topic_env, "").strip()
    if not topic:
        raise ValueError(f"Environment variable '{topic_env}' is required")

    rows: list[dict[str, Any]] = []
    for lineno, raw in enumerate(sys.stdin, start=1):
        raw = raw.strip()
        if not raw:
            continue
        try:
            item = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON on stdin line {lineno}: {exc}") from exc

        if not isinstance(item, dict):
            raise ValueError(f"Expected JSON object on stdin line {lineno}")
        rows.append(item)

    if not rows:
        print(f"No matches for '{name}'")
        return 0

    title = f"{name}: {len(rows)} match(es)"
    body = _build_message(rows)

    apobj = apprise.Apprise()
    apprise_url = f"ntfy://{topic}"
    if not apobj.add(apprise_url):
        raise RuntimeError(f"Failed to register Apprise URL for topic: {topic}")

    ok = apobj.notify(title=title, body=body)
    if not ok:
        raise RuntimeError(f"Failed to send Apprise notification for '{name}'")

    print(f"Notified '{name}' with {len(rows)} match(es)")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Read JSONL search results from stdin and notify via Apprise")
    parser.add_argument("--name", required=True, help="Search label for notification title")
    parser.add_argument("--topic-env", required=True, help="Environment variable containing ntfy topic")
    args = parser.parse_args()

    try:
        code = run(name=args.name, topic_env=args.topic_env)
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1)

    raise SystemExit(code)


if __name__ == "__main__":
    main()

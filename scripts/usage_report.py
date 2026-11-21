"""What the model calls have cost, from the llm_usage table.

Usage: python scripts/usage_report.py [--days 7]
"""
import argparse
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.store.db import connect  # noqa: E402


def table(title: str, rows, key: str) -> None:
    print(f"\n{title}")
    print(f"  {key:<20} {'calls':>6} {'in':>10} {'out':>10} {'cost':>10}")
    for r in rows:
        cost = "?" if r["cost"] is None else f"${r['cost']:.4f}"
        print(f"  {r['k']:<20} {r['calls']:>6} {r['tin']:>10} {r['tout']:>10} {cost:>10}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--days", type=int, default=30, help="how far back to look (default 30)")
    args = parser.parse_args()
    since = (datetime.now(timezone.utc) - timedelta(days=args.days)).isoformat(timespec="seconds")
    columns = ("COUNT(*) AS calls, SUM(input_tokens + cache_read_tokens + cache_write_tokens) AS tin,"
               " SUM(output_tokens) AS tout, SUM(cost_usd) AS cost, SUM(cost_usd IS NULL) AS unpriced")

    with connect() as conn:
        total = conn.execute(f"SELECT {columns} FROM llm_usage WHERE created_at >= ?", (since,)).fetchone()
        if not total["calls"]:
            print(f"No model calls recorded in the last {args.days} days.")
            return
        by_day = conn.execute(f"SELECT substr(created_at, 1, 10) AS k, {columns} FROM llm_usage"
                              " WHERE created_at >= ? GROUP BY k ORDER BY k", (since,)).fetchall()
        by_task = conn.execute(f"SELECT task || ' / ' || replace(model, 'claude-', '') AS k, {columns}"
                               " FROM llm_usage WHERE created_at >= ? GROUP BY k ORDER BY cost DESC",
                               (since,)).fetchall()

    print(f"Last {args.days} days: {total['calls']} calls, ${total['cost'] or 0:.4f}")
    if total["unpriced"]:
        print(f"({total['unpriced']} calls to models without a price in backend/llm/usage.py: tokens only)")
    table("By day (UTC)", by_day, "day")
    table("By task / model", by_task, "task / model")


if __name__ == "__main__":
    main()

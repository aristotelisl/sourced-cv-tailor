"""What each model call cost (tokens always; dollars for models in PRICES): logged to the console and stored in the llm_usage table."""
import logging
from datetime import datetime, timezone

from backend.store.db import connect

log = logging.getLogger("cv_tailor.llm")

# USD per million tokens: (input, output, cache read, 5-minute cache write). Checked 2026-11.
PRICES: dict[str, tuple[float, float, float, float]] = {
    "claude-opus-5-5": (4.00, 20.00, 0.20, 5.00),
    "claude-sonnet-5-5": (2.00, 10.00, 0.10, 2.50),
    "claude-haiku-5-5": (0.10, 0.50, 0.01, 0.125),
}
# Haiku 5.5 charges more once a prompt is over 100K tokens.
HAIKU_LONG_PROMPT = 100_000
HAIKU_LONG_PRICES = (0.50, 2.50, 0.05, 0.625)


def _tokens(usage, name: str) -> int:
    return getattr(usage, name, None) or 0


def cost_usd(model: str, usage) -> float | None:
    """Dollar cost of one response, or None for a model without a known price."""
    prices = PRICES.get(model)
    if prices is None:
        return None
    fresh = _tokens(usage, "input_tokens")
    read = _tokens(usage, "cache_read_input_tokens")
    write = _tokens(usage, "cache_creation_input_tokens")
    if model == "claude-haiku-5-5" and fresh + read + write > HAIKU_LONG_PROMPT:
        prices = HAIKU_LONG_PRICES
    p_in, p_out, p_read, p_write = prices
    total = fresh * p_in + _tokens(usage, "output_tokens") * p_out + read * p_read + write * p_write
    return total / 1_000_000


def record(task: str, model: str, effort: str, usage) -> None:
    """Log and store one call's usage. Never raises: a bookkeeping failure must not lose the result."""
    try:
        cost = cost_usd(model, usage)
        row = (
            datetime.now(timezone.utc).isoformat(timespec="seconds"), task, model, effort,
            _tokens(usage, "input_tokens"), _tokens(usage, "output_tokens"),
            _tokens(usage, "cache_read_input_tokens"), _tokens(usage, "cache_creation_input_tokens"),
            cost,
        )
        log.info(
            "%s on %s (%s): %d in, %d out, %d cache read, %d cache write -> %s",
            task, model, effort, row[4], row[5], row[6], row[7],
            "unknown cost" if cost is None else f"${cost:.4f}",
        )
        with connect() as conn:
            conn.execute(
                "INSERT INTO llm_usage (created_at, task, model, effort, input_tokens, output_tokens,"
                " cache_read_tokens, cache_write_tokens, cost_usd) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                row,
            )
    except Exception:
        log.warning("Could not record LLM usage", exc_info=True)

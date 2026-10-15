"""japan-price-alert-mcp — FastMCP server wrapping the Kensho price-monitor engine.

Tools:
  - create_price_watch
  - list_price_watches
  - get_price_watch
  - update_price_watch
  - delete_price_watch
  - check_price_watch
  - run_due_price_checks
  - get_price_history
  - detect_platform_url
"""
from __future__ import annotations

import logging
import os
from typing import Any

from fastmcp import FastMCP

from .notifier import PriceNotifier
from .scraper import detect_platform
from .service import PriceWatchService
from .store import PriceWatchStore

mcp = FastMCP("japan-price-alert-mcp")

logger = logging.getLogger(__name__)


def _service() -> PriceWatchService:
    db_path = os.environ.get("PRICE_WATCH_DB")
    store = PriceWatchStore(db_path=db_path) if db_path else PriceWatchStore()
    return PriceWatchService(store=store, notifier=PriceNotifier())


@mcp.tool()
async def create_price_watch(
    user_id: str,
    url: str,
    target_price_jpy: int | None = None,
    condition: str = "lte",
    drop_percentage: float | None = None,
    notification_channel: str = "log",
    notification_destination: str | None = None,
    check_interval_minutes: int = 60,
) -> dict[str, Any]:
    """Register a Japanese EC product URL for price-change monitoring."""
    svc = _service()
    watch = svc.create_watch(
        user_id=user_id, url=url, target_price_jpy=target_price_jpy,
        condition=condition, drop_percentage=drop_percentage,
        notification_channel=notification_channel,
        notification_destination=notification_destination,
        check_interval_minutes=check_interval_minutes,
    )
    return {"ok": True, "watch": watch}


@mcp.tool()
async def list_price_watches(user_id: str | None = None, only_active: bool = False) -> dict[str, Any]:
    """List registered price watches."""
    svc = _service()
    watches = svc.store.list_watches(user_id=user_id, only_active=only_active)
    return {"count": len(watches), "watches": watches}


@mcp.tool()
async def get_price_watch(watch_id: str) -> dict[str, Any]:
    """Get a single price watch by id."""
    svc = _service()
    watch = svc.store.get_watch(watch_id)
    if not watch:
        return {"ok": False, "error": f"watch {watch_id} not found"}
    return {"ok": True, "watch": watch}


@mcp.tool()
async def update_price_watch(
    watch_id: str,
    title: str | None = None,
    target_price_jpy: int | None = None,
    condition: str | None = None,
    drop_percentage: float | None = None,
    notification_channel: str | None = None,
    notification_destination: str | None = None,
    check_interval_minutes: int | None = None,
    is_active: bool | None = None,
) -> dict[str, Any]:
    """Update fields of an existing price watch."""
    svc = _service()
    allowed = {
        "title": title,
        "target_price_jpy": target_price_jpy,
        "condition": condition,
        "drop_percentage": drop_percentage,
        "notification_channel": notification_channel,
        "notification_destination": notification_destination,
        "check_interval_minutes": check_interval_minutes,
        "is_active": is_active,
    }
    fields = {k: v for k, v in allowed.items() if v is not None}
    watch = svc.store.update_watch(watch_id, **fields) if fields else None
    if not watch:
        watch = svc.store.get_watch(watch_id)
    if not watch:
        return {"ok": False, "error": f"watch {watch_id} not found"}
    return {"ok": True, "watch": watch}


@mcp.tool()
async def delete_price_watch(watch_id: str) -> dict[str, Any]:
    """Delete a price watch and all its price history."""
    svc = _service()
    ok = svc.store.delete_watch(watch_id)
    return {"ok": ok, "watch_id": watch_id}


@mcp.tool()
async def check_price_watch(watch_id: str, force: bool = False) -> dict[str, Any]:
    """Immediately scrape the product URL and evaluate the alert condition."""
    svc = _service()
    try:
        result = svc.check_watch(watch_id, force=force)
        return {"ok": True, **result}
    except ValueError as e:
        return {"ok": False, "error": str(e)}
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}


@mcp.tool()
async def run_due_price_checks() -> dict[str, Any]:
    """Run due price checks for all active watches."""
    svc = _service()
    results = svc.run_due_checks()
    triggered = [r for r in results if r.get("triggered")]
    return {
        "checked_count": len(results),
        "triggered_count": len(triggered),
        "results": results,
    }


@mcp.tool()
async def get_price_history(watch_id: str, limit: int = 50) -> dict[str, Any]:
    """Return the recorded price history for a watch."""
    svc = _service()
    history = svc.store.get_price_history(watch_id, limit=limit)
    return {"watch_id": watch_id, "count": len(history), "history": history}


@mcp.tool()
async def detect_platform_url(url: str) -> dict[str, Any]:
    """Detect the EC platform for a product URL."""
    return {"url": url, "platform": detect_platform(url)}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=None)
    mcp.run()
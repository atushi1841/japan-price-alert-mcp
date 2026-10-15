"""Price-watch service: rule evaluation, scraping, alert orchestration."""
from __future__ import annotations

import logging
from typing import Any

from .notifier import PriceNotifier
from .scraper import fetch_price
from .store import PriceWatchStore

logger = logging.getLogger(__name__)


class PriceWatchService:
    def __init__(self, store: PriceWatchStore | None = None,
                 notifier: PriceNotifier | None = None):
        self.store = store or PriceWatchStore()
        self.notifier = notifier or PriceNotifier()

    def create_watch(self, user_id: str, url: str, title: str | None = None,
                     platform: str | None = None, target_price_jpy: int | None = None,
                     condition: str = "lte", drop_percentage: float | None = None,
                     notification_channel: str = "log",
                     notification_destination: str | None = None,
                     check_interval_minutes: int = 60) -> dict[str, Any]:
        from .scraper import detect_platform
        platform = platform or detect_platform(url)
        title = title or "Monitored Item"
        watch = self.store.create_watch(
            user_id=user_id, url=url, title=title, platform=platform,
            target_price_jpy=target_price_jpy, condition=condition,
            drop_percentage=drop_percentage, notification_channel=notification_channel,
            notification_destination=notification_destination,
            check_interval_minutes=check_interval_minutes,
        )
        # Seed initial price
        try:
            snap = fetch_price(url)
            self.store.record_price(watch["id"], snap.price_jpy, snap.in_stock)
            if not title or title == "Monitored Item":
                if snap.title:
                    self.store.update_watch(watch["id"], title=snap.title)
            watch = self.store.get_watch(watch["id"]) or watch
        except Exception as e:
            logger.warning("initial price fetch failed for %s: %s", url, e)
        return watch

    def evaluate(self, watch: dict[str, Any], current_price: int, in_stock: bool) -> bool:
        cond = (watch.get("condition") or "lte").lower()
        if cond == "lte":
            target = watch.get("target_price_jpy")
            return target is not None and current_price <= target
        if cond == "any_drop":
            baseline = watch.get("last_price_jpy") or watch.get("initial_price_jpy")
            return baseline is not None and current_price < baseline
        if cond == "percent_drop":
            baseline = watch.get("last_price_jpy") or watch.get("initial_price_jpy")
            pct = watch.get("drop_percentage")
            if baseline and baseline > 0 and pct:
                return ((baseline - current_price) / baseline) * 100.0 >= pct
        if cond == "in_stock":
            return in_stock
        return False

    def check_watch(self, watch_id: str, force: bool = False) -> dict[str, Any]:
        watch = self.store.get_watch(watch_id)
        if not watch:
            raise ValueError(f"watch {watch_id} not found")
        if not watch.get("is_active") and not force:
            return {"watch_id": watch_id, "skipped": "inactive"}
        snap = fetch_price(watch["url"])
        old_price = watch.get("last_price_jpy")
        triggered = self.evaluate(watch, snap.price_jpy, snap.in_stock)
        self.store.record_price(watch["id"], snap.price_jpy, snap.in_stock)
        notification: dict[str, Any] | None = None
        if triggered:
            ok, status = self.notifier.dispatch(watch, snap.price_jpy, snap.in_stock)
            notification = {"status": status, "sent": ok}
        return {
            "watch_id": watch_id,
            "url": watch["url"],
            "title": watch["title"],
            "platform": watch["platform"],
            "current_price_jpy": snap.price_jpy,
            "previous_price_jpy": old_price,
            "in_stock": snap.in_stock,
            "triggered": triggered,
            "notification": notification,
            "scraped_at": snap.scraped_at,
        }

    def run_due_checks(self) -> list[dict[str, Any]]:
        from datetime import datetime, timedelta
        watches = self.store.list_watches(only_active=True)
        now = datetime.now()
        results: list[dict[str, Any]] = []
        for w in watches:
            last = w.get("last_checked_at")
            interval = w.get("check_interval_minutes") or 60
            due = False
            if not last:
                due = True
            else:
                try:
                    elapsed = (now - datetime.fromisoformat(last)).total_seconds() / 60.0
                    due = elapsed >= interval
                except ValueError:
                    due = True
            if due:
                try:
                    results.append(self.check_watch(w["id"]))
                except Exception as e:
                    logger.error("check failed for %s: %s", w["id"], e)
                    results.append({"watch_id": w["id"], "error": str(e)})
        return results
"""Notification dispatcher for price-change alerts (stdlib only)."""
from __future__ import annotations

import json
import logging
import os
import urllib.parse
import urllib.request
from typing import Any

logger = logging.getLogger(__name__)


class PriceNotifier:
    """Dispatches price-change alerts to Telegram / Webhook / Email / Log."""

    @staticmethod
    def build_alert_message(watch: dict[str, Any], current_price: int, in_stock: bool) -> str:
        old_price = watch.get("last_price_jpy") or watch.get("initial_price_jpy")
        diff_yen = (old_price - current_price) if old_price else 0
        diff_pct = (diff_yen / old_price * 100.0) if (old_price and old_price > 0) else 0.0
        lines = [
            "🔔 <b>【価格監視アラート】値下がりを検知しました！</b>",
            f"📦 <b>商品名:</b> {watch.get('title', 'Monitored Item')}",
            f"🏷️ <b>プラットフォーム:</b> {watch.get('platform', '').upper()}",
            f"💰 <b>現在価格:</b> ¥{current_price:,}",
        ]
        if old_price and diff_yen > 0:
            lines.append(f"📉 <b>変動:</b> -¥{diff_yen:,} ({diff_pct:.1f}% OFF)")
        if watch.get("target_price_jpy"):
            lines.append(f"🎯 <b>目標価格:</b> ¥{watch['target_price_jpy']:,} 以下達成")
        if not in_stock:
            lines.append("⚠️ 在庫状態: 売り切れ検知")
        lines.append(f"🔗 <b>商品リンク:</b> {watch.get('url', '')}")
        return "\n".join(lines)

    def dispatch(self, watch: dict[str, Any], current_price: int, in_stock: bool) -> tuple[bool, str]:
        msg = self.build_alert_message(watch, current_price, in_stock)
        channel = (watch.get("notification_channel") or "log").lower()
        destination = watch.get("notification_destination") or ""

        try:
            if channel == "telegram":
                ok = self._telegram(msg, destination)
                return ok, "sent" if ok else "failed_telegram_api"
            if channel == "webhook":
                return self._webhook(watch, current_price, in_stock, destination)
            if channel == "email":
                logger.info(f"[EMAIL ALERT] To: {destination}\nSubject: [Price Alert] {watch.get('title')}\n{msg}")
                return True, "sent"
            # log (default)
            logger.info(f"[LOG ALERT] {watch.get('id')}: {msg}")
            print(f"[LOG ALERT] {watch.get('id')}: {msg}")
            return True, "sent"
        except Exception as e:
            logger.error("dispatch error: %s", e)
            return False, str(e)

    @staticmethod
    def _telegram(message: str, chat_id: str) -> bool:
        token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
        chat_id = (chat_id or os.environ.get("TELEGRAM_CHAT_ID", "")).strip()
        if not token or not chat_id:
            logger.warning("Telegram token/chat_id 未設定 — 通知スキップ")
            return False
        text = urllib.parse.quote_plus(message[:4096])
        url = f"https://api.telegram.org/bot{token}/sendMessage?chat_id={chat_id}&text={text}&parse_mode=HTML"
        try:
            with urllib.request.urlopen(url, timeout=10) as resp:
                return resp.status == 200
        except Exception as e:
            logger.warning("Telegram送信失敗: %s", e)
            return False

    @staticmethod
    def _webhook(watch: dict[str, Any], current_price: int, in_stock: bool, url: str) -> tuple[bool, str]:
        if not url:
            return False, "webhook_url_empty"
        payload = {
            "event": "price_drop_alert",
            "watch_id": watch.get("id"),
            "user_id": watch.get("user_id"),
            "url": watch.get("url"),
            "title": watch.get("title"),
            "platform": watch.get("platform"),
            "current_price_jpy": current_price,
            "previous_price_jpy": watch.get("last_price_jpy"),
            "target_price_jpy": watch.get("target_price_jpy"),
            "in_stock": in_stock,
        }
        req = urllib.request.Request(
            url, data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"}, method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return resp.status < 400, "sent" if resp.status < 400 else f"webhook_status_{resp.status}"
        except Exception as e:
            return False, str(e)
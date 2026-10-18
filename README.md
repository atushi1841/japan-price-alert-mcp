# japan-price-alert-mcp

Japanese EC price-change monitoring and notification MCP server for AI agents.

[![Smithery](https://smithery.ai/badge/atushi1841/japan_price_alert_mcp)](https://smithery.ai/server/atushi1841/japan_price_alert_mcp)

## Overview

Monitor product prices across major Japanese e-commerce platforms (Mercari, Yahoo Auctions, Rakuten, SUUMO, Kakaku.com) and receive instant alerts on price drops.

Built on the [Kensho](https://github.com/atushi1841/kensho) project's price monitoring engine.

## Platforms

- **Mercari Japan** (メルカリ) - jp.mercari.com
- **Yahoo! Auctions / Shopping** (ヤフオク) - auctions.yahoo.co.jp, shopping.yahoo.co.jp
- **Rakuten Ichiba** (楽天市場) - item.rakuten.co.jp
- **SUUMO** (SUUMO) - suumo.jp
- **Kakaku.com** (価格.com) - kakaku.com
- **Suruga-ya** (駿河屋) - suruga-ya.jp

## Tools

| Tool | Description |
|---|---|
| `create_price_watch` | Register a new product URL for price monitoring |
| `list_price_watches` | List all registered watches |
| `get_price_watch` | Get details of a specific watch |
| `update_price_watch` | Update watch parameters (target price, interval, etc.) |
| `delete_price_watch` | Remove a watch |
| `check_price_watch` | Force immediate price check |
| `run_due_price_checks` | Batch check all due watches |
| `get_price_history` | Get historical price data |
| `detect_platform_url` | Detect platform from URL |

## Installation

### Smithery (Recommended)

```bash
npx @smithery/cli install atushi1841/japan_price_alert_mcp
```

### Manual

```bash
# Clone or extract the MCPB bundle
# Configure in your MCP client:
{
  "servers": {
    "japan-price-alert-mcp": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/bundle", "src/stdio_main.py"]
    }
  }
}
```

## Configuration

| Environment Variable | Description | Default |
|---|---|---|
| `PRICE_WATCH_DB` | Custom SQLite database path | `<bundle>/data/price_watch.db` |
| `TELEGRAM_BOT_TOKEN` | Telegram bot token (for notifications) | - |
| `TELEGRAM_CHAT_ID` | Telegram chat ID (for notifications) | - |

## Usage Examples

```typescript
// Create a price watch
const result = await mcp.callTool("create_price_watch", {
  user_id: "user123",
  url: "https://www.mercari.com/us/item/m123456789/",
  target_price_jpy: 5000,
  notification_channel: "telegram",
  notification_destination: "123456789",
  check_interval_minutes: 30
});

// Check a specific watch
const check = await mcp.callTool("check_price_watch", {
  watch_id: "pw_abc123"
});

// List all watches
const list = await mcp.callTool("list_price_watches", {
  user_id: "user123"
});
```

## Alert Conditions

- **lte** (default): Alert when price <= target_price_jpy
- **any_drop**: Alert on any price decrease
- **percent_drop**: Alert when price drops by >= drop_percentage%
- **in_stock**: Alert when item comes back in stock

## Notification Channels

- **log** (default): Log to stderr
- **telegram**: Send to Telegram bot (requires token + chat_id)
- **webhook**: POST to specified URL
- **email**: Log email alert (SMTP not implemented)

## Dependencies

- Python >=3.10
- fastmcp >=3.0.0
- stdlib only for scraping (no external dependencies beyond fastmcp)

## License

MIT

## Author

atushi1841

---
## Data & Store

- **Apify Store:** https://apify.com/fruitful_quintessence
- **Gumroad datasets:** https://atushi5.gumroad.com/l/kutuxe

"""Sync manifest tools from live MCP server (FastMCP introspection).

Smitheryのstdio公開APIは各ツールに inputSchema を要求する（欠けると400）。
サーバー実装を正として manifest を生成するため、手書きせずここで同期する。
"""

import asyncio
import json
import os
import sys

BUNDLE_DIR = sys.argv[1] if len(sys.argv) > 1 else "/mnt/d/Project2/kensho/mcp_servers/japan_price_alert_mcp"
MANIFEST = os.path.join(BUNDLE_DIR, "manifest.json")


def fetch_tools() -> list[dict]:
    sys.path.insert(0, BUNDLE_DIR)
    from src.server import mcp

    raw = asyncio.run(mcp._list_tools())
    out: list[dict] = []
    for t in raw:
        entry: dict[str, object] = {"name": t.name}
        if t.description:
            entry["description"] = t.description
        schema = getattr(t, "parameters", None)
        if not isinstance(schema, dict):
            schema = {"type": "object", "properties": {}}
        entry["inputSchema"] = schema
        out.append(entry)
    return out


def main() -> None:
    tools = fetch_tools()
    with open(MANIFEST, encoding="utf-8") as f:
        manifest = json.load(f)
    manifest["tools"] = tools
    with open(MANIFEST, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(f"Synced {len(tools)} tools -> {MANIFEST}")
    for t in tools:
        print(" -", t["name"], "| schema keys:", list(t["inputSchema"].get("properties", {})))


if __name__ == "__main__":
    main()
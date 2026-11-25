"""Pull one certified packet from the NOMAD feed.

Reads the public feed and adds one packet as an optional domain packet.
Does not write back. PacketLM remains the authority on its own store.
"""

from __future__ import annotations
import json
from pathlib import Path
from .store import PacketStore
from .train import load_corpus, window_stories

FEED_URL = "https://raw.githubusercontent.com/jacksonjp0311-gif/NOMAD/main/feed/latest.json"

def pull_one() -> dict:
    try:
        import urllib.request
        with urllib.request.urlopen(FEED_URL, timeout=15) as r:
            data = json.loads(r.read().decode())
    except Exception as e:
        return {"pulled": False, "reason": str(e)}

    # take the first available text-like field or a summary
    text = None
    if isinstance(data, dict):
        for key in ("claim", "text", "summary", "description", "program"):
            if key in data and isinstance(data[key], str):
                text = data[key]
                break
        if text is None and "packets" in data and data["packets"]:
            first = data["packets"][0]
            text = first.get("text") or first.get("claim") or str(first)[:200]
    if not text:
        text = json.dumps(data)[:200]

    store = PacketStore()
    for t in window_stories(load_corpus()):
        store.add(t, provenance="corpus")
    store.add(text, provenance="nomad_feed")
    store.save("artifacts/packet_store_with_feed.json")
    return {
        "pulled": True,
        "source": FEED_URL,
        "text": text[:120],
        "total_packets": len(store.packets),
        "claim": "one optional domain packet pulled from NOMAD feed; no write-back"
    }

def run() -> dict:
    result = pull_one()
    Path("artifacts").mkdir(exist_ok=True)
    Path("artifacts/feedpull_receipt.json").write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))
    return result

if __name__ == "__main__":
    run()

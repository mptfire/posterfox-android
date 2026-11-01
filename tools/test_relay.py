#!/usr/bin/env python3
"""A minimal Nostr relay for the bookmark round-trip test: stores every event, answers REQ (ids/kinds/authors/#d/#l,
limit), sends EOSE, streams new events to open subscriptions, and records every EVENT it receives to a JSONL file.
No AUTH, no checks: it is a test fixture on a private network, never a service.

    test_relay.py PORT SEED.jsonl RECEIVED.jsonl
"""
import asyncio
import json
import sys

import websockets

PORT, SEED, LOG = int(sys.argv[1]), sys.argv[2], sys.argv[3]
events = {}
subs = set()


def matches(ev, f):
    if "ids" in f and ev["id"] not in f["ids"]:
        return False
    if "kinds" in f and ev["kind"] not in f["kinds"]:
        return False
    if "authors" in f and ev["pubkey"] not in f["authors"]:
        return False
    for k, v in f.items():
        if k.startswith("#") and len(k) == 2:
            if not any(t[0] == k[1] and t[1] in v for t in ev.get("tags", []) if len(t) > 1):
                return False
    return True


def store(ev):
    d = next((t[1] for t in ev.get("tags", []) if t[0] == "d"), None)
    if 30000 <= ev["kind"] < 40000 and d is not None:
        for k, old in list(events.items()):
            if old["kind"] == ev["kind"] and old["pubkey"] == ev["pubkey"] and \
                    next((t[1] for t in old.get("tags", []) if t[0] == "d"), None) == d:
                if old["created_at"] > ev["created_at"]:
                    return False
                del events[k]
    events[ev["id"]] = ev
    return True


async def handle(ws):
    mine = {}
    entry = (ws, mine)
    subs.add(entry)
    try:
        async for raw in ws:
            m = json.loads(raw)
            if m[0] == "EVENT":
                ev = m[1]
                with open(LOG, "a") as fh:
                    fh.write(json.dumps(ev) + "\n")
                store(ev)
                await ws.send(json.dumps(["OK", ev["id"], True, ""]))
                for other_ws, other in list(subs):
                    for sid, fs in other.items():
                        if any(matches(ev, f) for f in fs):
                            try:
                                await other_ws.send(json.dumps(["EVENT", sid, ev]))
                            except Exception:
                                pass
            elif m[0] == "REQ":
                sid, fs = m[1], m[2:]
                mine[sid] = fs
                out = [e for e in events.values() if any(matches(e, f) for f in fs)]
                out.sort(key=lambda e: -e["created_at"])
                lim = min([f.get("limit", 10 ** 9) for f in fs] or [10 ** 9])
                for e in out[:lim]:
                    await ws.send(json.dumps(["EVENT", sid, e]))
                await ws.send(json.dumps(["EOSE", sid]))
            elif m[0] == "CLOSE":
                mine.pop(m[1], None)
    except websockets.ConnectionClosed:
        pass
    finally:
        subs.discard(entry)


async def main():
    for line in open(SEED):
        if line.strip():
            store(json.loads(line))
    async with websockets.serve(handle, "0.0.0.0", PORT, max_size=None):
        print("relay up on", PORT, "with", len(events), "seeded events", flush=True)
        await asyncio.Future()


asyncio.run(main())

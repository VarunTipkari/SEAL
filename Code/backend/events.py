"""Simple async event bus for SSE streaming"""
from __future__ import annotations

import asyncio
import json
import time
from collections import deque
from typing import Any

_bus: list[asyncio.Queue] = []
_history: deque[dict] = deque(maxlen=500)
_seq = 0


class EventBus:
    def __init__(self):
        self._bus = []
        self._history = deque(maxlen=500)
        self._seq = 0

    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=1000)
        self._bus.append(q)
        return q

    def unsubscribe(self, q: asyncio.Queue):
        if q in self._bus:
            self._bus.remove(q)

    def publish(self, evt: str, **payload):
        self._seq += 1
        rec = {
            "evt": evt,
            "seq": self._seq,
            "ts": round(time.time(), 3),
            "t": time.strftime("%H:%M:%S"),
            **payload
        }
        # Remove non-serializable items
        for k, v in list(rec.items()):
            if not isinstance(v, (str, int, float, bool, list, dict, type(None))):
                rec[k] = str(v)
        
        self._history.append(rec)
        line = json.dumps(rec)
        dead = []
        for q in self._bus:
            try:
                q.put_nowait(line)
            except asyncio.QueueFull:
                dead.append(q)
        for q in dead:
            self.unsubscribe(q)

    def history(self) -> list[dict]:
        return list(self._history)


# Global event bus instance
_event_bus = EventBus()


def publish(evt: str, **payload):
    _event_bus.publish(evt, **payload)


def subscribe() -> asyncio.Queue:
    return _event_bus.subscribe()


def unsubscribe(q: asyncio.Queue):
    _event_bus.unsubscribe(q)


def history() -> list[dict]:
    return _event_bus.history()
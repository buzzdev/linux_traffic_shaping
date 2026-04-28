"""
net_monitor.py — async /proc/net/dev reader.

Emits NetSample(rx_kbps, tx_kbps, ts) every INTERVAL_S seconds by
computing the byte-counter delta from /proc/net/dev.
"""

import asyncio
import time
from collections.abc import AsyncGenerator
from dataclasses import dataclass
from pathlib import Path

INTERVAL_S: float = 0.5
_PROC_NET_DEV = Path("/proc/net/dev")


@dataclass
class NetSample:
    rx_kbps: float
    tx_kbps: float
    ts: float  # time.monotonic() timestamp


def _read_bytes(iface: str) -> tuple[int, int]:
    """Return (rx_bytes, tx_bytes) for iface from /proc/net/dev.

    /proc/net/dev column layout (after "iface:"):
      rx: bytes packets errs drop fifo frame compressed multicast
      tx: bytes packets errs drop fifo colls carrier compressed
    """
    for line in _PROC_NET_DEV.read_text().splitlines():
        stripped = line.strip()
        if not stripped.startswith(iface + ":"):
            continue
        # Remove the "iface:" prefix, then split
        parts = stripped.split(":")[1].split()
        rx_bytes = int(parts[0])
        tx_bytes = int(parts[8])
        return rx_bytes, tx_bytes
    raise ValueError(f"Interface {iface!r} not found in /proc/net/dev")


async def get_rate(iface: str) -> AsyncGenerator[NetSample, None]:
    """Async generator that yields a NetSample every INTERVAL_S seconds."""
    prev_rx, prev_tx = _read_bytes(iface)
    prev_ts = time.monotonic()
    while True:
        await asyncio.sleep(INTERVAL_S)
        rx, tx = _read_bytes(iface)
        ts = time.monotonic()
        dt = ts - prev_ts
        rx_kbps = (rx - prev_rx) * 8 / dt / 1000
        tx_kbps = (tx - prev_tx) * 8 / dt / 1000
        prev_rx, prev_tx, prev_ts = rx, tx, ts
        yield NetSample(
            rx_kbps=max(0.0, rx_kbps),
            tx_kbps=max(0.0, tx_kbps),
            ts=ts,
        )

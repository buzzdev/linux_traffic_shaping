"""
tc_runner.py — tc/ip subprocess wrappers for bandwidth shaping.

All commands run with shell=False. Interface names and rates are
validated against strict whitelists before any subprocess call.
"""

import json
import re
import subprocess
from dataclasses import dataclass, field
from typing import Optional

try:
    from manuf import manuf as _manuf_module
    _mac_parser = _manuf_module.MacParser()
except Exception:
    _mac_parser = None

# ---------------------------------------------------------------------------
# Constants (derived from scripts/config.sh)
# ---------------------------------------------------------------------------

BURST = "10kb"
LATENCY = "70ms"
MINBURST = "1540"

# Allowed rate presets: rate_kbps -> (tc_rate_str, tc_peakrate_str)
# Values use SI kilo (×1000) to match tc's mbit/kbit notation.
ALLOWED_RATES: dict[int, tuple[str, str]] = {
    64:    ("64kbit",  "100kbit"),
    128:   ("128kbit", "200kbit"),
    256:   ("256kbit", "300kbit"),
    384:   ("384kbit", "500kbit"),
    512:   ("512kbit", "700kbit"),
    1000:  ("1mbit",   "1200kbit"),
    2000:  ("2mbit",   "2200kbit"),
    3000:  ("3mbit",   "3300kbit"),
    4000:  ("4mbit",   "4400kbit"),
    5000:  ("5mbit",   "5500kbit"),
    50000: ("50mbit",  "55mbit"),
}

_IFACE_RE = re.compile(r"^[a-zA-Z0-9._:-]{1,15}$")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _validate_iface(iface: str) -> None:
    if not _IFACE_RE.match(iface):
        raise ValueError(f"Invalid interface name: {iface!r}")


def _run(cmd: list[str], check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=check,
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

@dataclass
class IfaceInfo:
    name: str
    iface_type: str  # "wlan" | "eth" | "other"


def get_interfaces() -> list[IfaceInfo]:
    """Return host network interfaces parsed from `ip -j link show`."""
    result = _run(["ip", "-j", "link", "show"])
    links: list[dict] = json.loads(result.stdout)
    out: list[IfaceInfo] = []
    for link in links:
        name: str = link.get("ifname", "")
        if not name or name == "lo":
            continue
        link_type: str = link.get("link_type", "")
        # Classify by prefix and link_type
        if link_type == "ether" and (
            name.startswith("wl") or name.startswith("wlan")
        ):
            itype = "wlan"
        elif link_type == "ether" and (
            name.startswith("eth")
            or name.startswith("en")
        ):
            itype = "eth"
        else:
            itype = "other"
        out.append(IfaceInfo(name=name, iface_type=itype))
    return out


def get_qdisc(iface: str) -> Optional[int]:
    """
    Return the current TBF rate in kbps, or None if no TBF qdisc is active.
    Parses `tc qdisc show dev <iface>` text output.

    Example line:
      qdisc tbf 8001: dev wlp0s20f3 root refcnt 2 rate 2Mbit burst 10Kb lat 70.0ms peakrate 2.2Mbit minburst 1540b
    """
    _validate_iface(iface)
    result = _run(["tc", "qdisc", "show", "dev", iface])
    for line in result.stdout.splitlines():
        if "tbf" not in line:
            continue
        # Match: "rate 2Mbit", "rate 512Kbit", "rate 50Mbit", "rate 64000bit"
        m = re.search(r"\brate\s+([0-9.]+)([KMGkmg]?)bit\b", line)
        if not m:
            continue
        val = float(m.group(1))
        unit = m.group(2).upper()
        if unit == "K":
            rate_kbps = int(val)
        elif unit == "M":
            rate_kbps = int(val * 1000)
        elif unit == "G":
            rate_kbps = int(val * 1_000_000)
        else:
            rate_kbps = max(1, int(val // 1000))  # raw bps → kbps
        return rate_kbps
    return None


def _qdisc_exists(iface: str) -> bool:
    """Return True if a TBF root qdisc is already present on iface."""
    result = _run(["tc", "qdisc", "show", "dev", iface])
    return any("tbf" in line for line in result.stdout.splitlines())


def set_rate(iface: str, rate_kbps: int) -> None:
    """Apply TBF shaping to iface at rate_kbps (must be a key in ALLOWED_RATES)."""
    _validate_iface(iface)
    if rate_kbps not in ALLOWED_RATES:
        raise ValueError(
            f"rate_kbps {rate_kbps} not in allowed set: {sorted(ALLOWED_RATES)}"
        )
    rate_str, peakrate_str = ALLOWED_RATES[rate_kbps]
    verb = "change" if _qdisc_exists(iface) else "add"
    _run([
        "tc", "qdisc", verb, "dev", iface, "root", "tbf",
        "rate", rate_str,
        "burst", BURST,
        "latency", LATENCY,
        "peakrate", peakrate_str,
        "minburst", MINBURST,
    ])


def clear_rate(iface: str) -> None:
    """Remove root TBF qdisc from iface. Silently ignores 'no such qdisc'."""
    _validate_iface(iface)
    result = _run(["tc", "qdisc", "del", "dev", iface, "root"], check=False)
    if result.returncode != 0:
        # rc=2 or "No such file or directory" → qdisc was already absent
        stderr = result.stderr.strip()
        if result.returncode != 2 and "No such" not in stderr:
            raise RuntimeError(
                f"tc qdisc del failed (rc={result.returncode}): {stderr}"
            )


# ---------------------------------------------------------------------------
# WiFi client list
# ---------------------------------------------------------------------------

@dataclass
class ClientInfo:
    mac: str
    ip: Optional[str] = None
    hostname: Optional[str] = None
    signal_dbm: Optional[int] = None
    tx_kbps: Optional[int] = None
    rx_kbps: Optional[int] = None
    vendor: Optional[str] = None
    device_type: Optional[str] = None


# Hostname patterns → device type labels
_HOSTNAME_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"iphone", re.I), "iPhone"),
    (re.compile(r"ipad", re.I), "iPad"),
    (re.compile(r"macbook|mac-book", re.I), "MacBook"),
    (re.compile(r"android|pixel|galaxy|samsung", re.I), "Android"),
    (re.compile(r"windows|win-|desktop|laptop", re.I), "PC"),
    (re.compile(r"raspberrypi|rpi", re.I), "Raspberry Pi"),
]

# Vendor name substrings → device type labels (fallback when hostname is unhelpful)
_VENDOR_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"apple", re.I), "Apple device"),
    (re.compile(r"samsung", re.I), "Samsung device"),
    (re.compile(r"google", re.I), "Google device"),
    (re.compile(r"qualcomm", re.I), "Android device"),
    (re.compile(r"intel", re.I), "PC / Laptop"),
    (re.compile(r"realtek", re.I), "PC / Laptop"),
    (re.compile(r"raspberry", re.I), "Raspberry Pi"),
]


def _guess_device_type(hostname: Optional[str], vendor: Optional[str]) -> Optional[str]:
    if hostname:
        for pattern, label in _HOSTNAME_PATTERNS:
            if pattern.search(hostname):
                return label
    if vendor:
        for pattern, label in _VENDOR_PATTERNS:
            if pattern.search(vendor):
                return label
    return None


def get_clients(iface: str) -> list[ClientInfo]:
    """
    Return connected WiFi stations on *iface* using `iw dev <iface> station dump`.
    Enriches each entry with IP from the ARP table and hostname from /etc/hosts
    or reverse DNS (best-effort).
    """
    _validate_iface(iface)

    result = _run(["iw", "dev", iface, "station", "dump"], check=False)
    if result.returncode != 0:
        return []

    # Parse iw station dump output into per-MAC blocks
    clients: dict[str, ClientInfo] = {}
    current_mac: Optional[str] = None
    for line in result.stdout.splitlines():
        mac_match = re.match(r"^Station\s+([0-9a-f:]{17})\s+", line, re.I)
        if mac_match:
            current_mac = mac_match.group(1).lower()
            clients[current_mac] = ClientInfo(mac=current_mac)
            continue
        if current_mac is None:
            continue
        line = line.strip()
        signal_match = re.match(r"signal:\s+(-\d+)\s+dBm", line)
        if signal_match:
            clients[current_mac].signal_dbm = int(signal_match.group(1))
        tx_match = re.match(r"tx bitrate:\s+([\d.]+)\s+MBit/s", line)
        if tx_match:
            clients[current_mac].tx_kbps = int(float(tx_match.group(1)) * 1000)
        rx_match = re.match(r"rx bitrate:\s+([\d.]+)\s+MBit/s", line)
        if rx_match:
            clients[current_mac].rx_kbps = int(float(rx_match.group(1)) * 1000)

    if not clients:
        return []

    # Enrich with IP from ARP table (`ip -j neigh show dev <iface>`)
    neigh = _run(["ip", "-j", "neigh", "show", "dev", iface], check=False)
    if neigh.returncode == 0:
        try:
            for entry in json.loads(neigh.stdout):
                mac = entry.get("lladdr", "").lower()
                ip = entry.get("dst")
                if mac in clients and ip:
                    clients[mac].ip = ip
        except (json.JSONDecodeError, KeyError):
            pass

    # Best-effort hostname via reverse lookup
    import socket
    for c in clients.values():
        if c.ip:
            try:
                c.hostname = socket.gethostbyaddr(c.ip)[0]
            except (socket.herror, socket.gaierror):
                pass

    # OUI vendor + device type
    for c in clients.values():
        if _mac_parser is not None:
            try:
                c.vendor = _mac_parser.get_manuf(c.mac) or None
            except Exception:
                pass
        c.device_type = _guess_device_type(c.hostname, c.vendor)

    return list(clients.values())

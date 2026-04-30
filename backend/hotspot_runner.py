"""hotspot_runner.py — nmcli-based WiFi hotspot lifecycle management."""

import os
import re
import subprocess
from pathlib import Path
from typing import Optional

from pydantic import BaseModel

# ── Config persistence ───────────────────────────────────────────────────────
DATA_DIR = Path("/app/data")
CONFIG_FILE = DATA_DIR / "hotspot_config.json"

_IFACE_RE = re.compile(r"^[a-zA-Z0-9._:-]{1,15}$")
_NM_PROFILE_NAME = "Hotspot"

# Standard D-Bus socket paths (both resolve to the same socket on most distros)
_DBUS_PATHS = [
    "/run/dbus/system_bus_socket",
    "/var/run/dbus/system_bus_socket",
]


class HotspotConfig(BaseModel):
    ssid: str
    password: str
    iface: str
    auto_start: bool = False


class HotspotStatus(BaseModel):
    available: bool
    active: bool
    ssid: Optional[str] = None
    iface: Optional[str] = None
    auto_start: bool = False


# ── Validation helpers ───────────────────────────────────────────────────────

def _validate_iface(iface: str) -> None:
    if not _IFACE_RE.match(iface):
        raise ValueError(f"Invalid interface name: {iface!r}")


def _validate_ssid(ssid: str) -> None:
    if not 1 <= len(ssid) <= 32:
        raise ValueError("SSID must be 1–32 characters")


def _validate_password(password: str) -> None:
    if not 8 <= len(password) <= 63:
        raise ValueError("Password must be 8–63 characters (WPA2 requirement)")


def _nmcli_available() -> bool:
    """Return True if nmcli binary exists and a D-Bus socket is reachable."""
    if not any(os.path.exists(p) for p in _DBUS_PATHS):
        return False
    try:
        result = subprocess.run(
            ["nmcli", "--version"],
            capture_output=True,
            timeout=5,
            shell=False,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


# ── Config persistence ───────────────────────────────────────────────────────

def get_hotspot_config() -> Optional[HotspotConfig]:
    """Read persisted hotspot config from disk. Returns None if not set."""
    if not CONFIG_FILE.exists():
        return None
    try:
        return HotspotConfig.model_validate_json(CONFIG_FILE.read_text())
    except Exception:
        return None


def save_hotspot_config(cfg: HotspotConfig) -> None:
    """Write hotspot config to disk (stored in a local-only Docker volume)."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(cfg.model_dump_json())


# ── Status / start / stop ────────────────────────────────────────────────────

def get_hotspot_status() -> HotspotStatus:
    """Return current hotspot status by querying nmcli."""
    if not _nmcli_available():
        return HotspotStatus(available=False, active=False)

    cfg = get_hotspot_config()
    auto_start = cfg.auto_start if cfg else False

    try:
        result = subprocess.run(
            ["nmcli", "-t", "-f", "NAME,TYPE,DEVICE", "con", "show", "--active"],
            capture_output=True,
            text=True,
            timeout=10,
            shell=False,
        )
        for line in result.stdout.splitlines():
            parts = line.split(":")
            if (
                len(parts) >= 3
                and parts[0] == _NM_PROFILE_NAME
                and parts[1] == "802-11-wireless"
            ):
                iface = parts[2] or (cfg.iface if cfg else None)
                return HotspotStatus(
                    available=True,
                    active=True,
                    ssid=cfg.ssid if cfg else None,
                    iface=iface,
                    auto_start=auto_start,
                )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return HotspotStatus(available=False, active=False)

    return HotspotStatus(available=True, active=False, auto_start=auto_start)


def start_hotspot(ssid: str, password: str, iface: str) -> None:
    """
    Create and activate a WiFi hotspot via nmcli.
    Deletes any existing 'Hotspot' profile first to allow reconfiguration.
    """
    _validate_iface(iface)
    _validate_ssid(ssid)
    _validate_password(password)

    if not _nmcli_available():
        raise RuntimeError(
            "NetworkManager is not reachable. "
            "Ensure the D-Bus socket is mounted and NetworkManager is running on the host."
        )

    # Delete old profile so SSID/password changes take effect (ignore errors)
    subprocess.run(
        ["nmcli", "con", "delete", _NM_PROFILE_NAME],
        capture_output=True,
        timeout=10,
        shell=False,
    )

    # Disconnect the interface first — NM rejects AP creation on a managed/connected device
    subprocess.run(
        ["nmcli", "device", "disconnect", iface],
        capture_output=True,
        timeout=10,
        shell=False,
    )

    result = subprocess.run(
        [
            "nmcli", "device", "wifi", "hotspot",
            "ifname", iface,
            "ssid", ssid,
            "password", password,
        ],
        capture_output=True,
        text=True,
        timeout=30,
        shell=False,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"Failed to start hotspot: {result.stderr.strip() or result.stdout.strip()}"
        )


def stop_hotspot(iface: str) -> None:
    """Disconnect the hotspot interface and remove the profile."""
    _validate_iface(iface)

    if not _nmcli_available():
        raise RuntimeError("NetworkManager is not reachable.")

    # Best-effort disconnect; may already be down
    subprocess.run(
        ["nmcli", "device", "disconnect", iface],
        capture_output=True,
        text=True,
        timeout=15,
        shell=False,
    )
    subprocess.run(
        ["nmcli", "con", "delete", _NM_PROFILE_NAME],
        capture_output=True,
        timeout=10,
        shell=False,
    )

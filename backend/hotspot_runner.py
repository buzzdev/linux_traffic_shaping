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
_NM_CONNECTIONS_DIR = Path("/etc/NetworkManager/system-connections")
_NM_PROFILE_FILE = _NM_CONNECTIONS_DIR / f"{_NM_PROFILE_NAME}.nmconnection"

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


def _write_nm_profile(ssid: str, password: str, iface: str) -> None:
    """Write a NetworkManager .nmconnection file for the hotspot."""
    _NM_CONNECTIONS_DIR.mkdir(parents=True, exist_ok=True)
    content = (
        "[connection]\n"
        f"id={_NM_PROFILE_NAME}\n"
        "type=wifi\n"
        f"interface-name={iface}\n"
        "autoconnect=false\n"
        "\n"
        "[wifi]\n"
        "mode=ap\n"
        f"ssid={ssid}\n"
        "band=bg\n"
        "\n"
        "[wifi-security]\n"
        "key-mgmt=wpa-psk\n"
        f"psk={password}\n"
        "\n"
        "[ipv4]\n"
        "method=shared\n"
        "\n"
        "[ipv6]\n"
        "method=ignore\n"
    )
    _NM_PROFILE_FILE.write_text(content)
    _NM_PROFILE_FILE.chmod(0o600)


def start_hotspot(ssid: str, password: str, iface: str) -> None:
    """
    Create and activate a WiFi hotspot.
    Writes the NM connection profile directly to disk to avoid polkit
    restrictions on D-Bus connection-creation from inside a container,
    then reloads NM and brings the connection up.
    """
    _validate_iface(iface)
    _validate_ssid(ssid)
    _validate_password(password)

    if not _nmcli_available():
        raise RuntimeError(
            "NetworkManager is not reachable. "
            "Ensure the D-Bus socket is mounted and NetworkManager is running on the host."
        )

    # Write the connection profile directly — avoids polkit 'create connection' check
    _write_nm_profile(ssid, password, iface)

    # Tell NM to pick up the new/updated file
    reload = subprocess.run(
        ["nmcli", "con", "reload"],
        capture_output=True,
        text=True,
        timeout=10,
        shell=False,
    )
    if reload.returncode != 0:
        raise RuntimeError(
            f"Failed to reload NM connections: {reload.stderr.strip() or reload.stdout.strip()}"
        )

    # Activate the profile
    result = subprocess.run(
        ["nmcli", "con", "up", _NM_PROFILE_NAME],
        capture_output=True,
        text=True,
        timeout=30,
        shell=False,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"Failed to start hotspot: {result.stderr.strip() or result.stdout.strip()}"
        )

    # Docker Engine sets the FORWARD chain default policy to DROP, which blocks
    # hotspot clients from routing through to the upstream interface.
    # Insert rules into DOCKER-USER (which Docker never flushes) to allow it.
    _fix_forwarding(iface)


def _fix_forwarding(hotspot_iface: str) -> None:
    """
    Ensure Docker Engine's FORWARD DROP policy doesn't block hotspot NAT.
    Inserts ACCEPT rules into the DOCKER-USER chain for traffic to/from
    the hotspot interface, and ensures IP forwarding is enabled.
    """
    # Enable IP forwarding (NM shared should do this, but be explicit)
    subprocess.run(
        ["sh", "-c", "echo 1 > /proc/sys/net/ipv4/ip_forward"],
        capture_output=True, shell=False,
    )

    # Detect the DOCKER-USER chain — only present when Docker Engine is running
    probe = subprocess.run(
        ["iptables", "-L", "DOCKER-USER", "-n"],
        capture_output=True, shell=False,
    )
    if probe.returncode != 0:
        # No Docker, NM's own rules are sufficient
        return

    rules = [
        # Allow all forwarded traffic originating from the hotspot interface
        ["iptables", "-C", "DOCKER-USER", "-i", hotspot_iface, "-j", "ACCEPT"],
        # Allow return traffic back to hotspot clients
        ["iptables", "-C", "DOCKER-USER", "-o", hotspot_iface,
         "-m", "state", "--state", "RELATED,ESTABLISHED", "-j", "ACCEPT"],
    ]
    insert_rules = [
        ["iptables", "-I", "DOCKER-USER", "-i", hotspot_iface, "-j", "ACCEPT"],
        ["iptables", "-I", "DOCKER-USER", "-o", hotspot_iface,
         "-m", "state", "--state", "RELATED,ESTABLISHED", "-j", "ACCEPT"],
    ]
    for check, insert in zip(rules, insert_rules):
        exists = subprocess.run(check, capture_output=True, shell=False)
        if exists.returncode != 0:
            subprocess.run(insert, capture_output=True, shell=False)


def stop_hotspot(iface: str) -> None:
    """Disconnect the hotspot interface and remove the profile."""
    _validate_iface(iface)

    if not _nmcli_available():
        raise RuntimeError("NetworkManager is not reachable.")

    # Bring down the connection and remove the profile file
    subprocess.run(
        ["nmcli", "con", "down", _NM_PROFILE_NAME],
        capture_output=True,
        text=True,
        timeout=15,
        shell=False,
    )
    _NM_PROFILE_FILE.unlink(missing_ok=True)
    subprocess.run(
        ["nmcli", "con", "reload"],
        capture_output=True,
        timeout=10,
        shell=False,
    )

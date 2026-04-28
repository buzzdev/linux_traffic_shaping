# Plan: Bandwidth Shaping Web GUI — Docker Compose Stack

## TL;DR

Replace the bash scripts with a Docker Compose stack: React + Vite SPA (frontend),
Python FastAPI backend (with `CAP_NET_ADMIN` + `network_mode: host` to run `tc` on the host),
and Caddy as HTTPS reverse proxy with internal TLS.
Runs on Raspberry Pi (ARM64) or any Linux PC (AMD64).

---

## Original System Summary

| File | Purpose |
|---|---|
| `scripts/config.sh` | Rate tiers (64kbit–50mbit), TBF params, interface names |
| `scripts/shaping.sh` | Adds TBF qdisc, steps down over time, then removes it |
| `scripts/speed.sh` | Wrapper around `speedometer` CLI |

Linux tools used: `tc` (TBF qdisc).

---

## Architecture Decisions

| Concern | Decision |
|---|---|
| Reverse proxy | Caddy with `tls internal` (self-signed local CA, no public domain needed) |
| Frontend | React + Vite + TypeScript SPA, Tailwind CSS, Recharts |
| Backend | Python FastAPI |
| Root privilege | `CAP_NET_ADMIN` + `network_mode: host` on the backend container |
| Shaping mode | Manual set-and-forget (user picks rate, Apply holds it until Clear or change) |
| Live chart | RX + TX scrolling line chart via WebSocket stream (500 ms cadence) |
| Legacy scripts | Moved to `scripts/` folder, not deleted |

---

## Network Topology

```
Internet ── [Upstream Router] ──(eth)── RPi ──(wlan/hotspot)── Clients
                                                 ↑
                               tc TBF shaping on wlan interface (egress)
                               Web GUI accessible on BOTH eth and wlan IPs
```

- **`enp0s31f6` / `eth0`** — WAN-side; RPi receives internet here
- **`wlp0s20f3` / `wlan0`** — LAN-side hotspot; mobile/TV clients connect here
- Shaping target: always the **wlan/hotspot interface**
- Caddy binds `:443` on all host IPs → reachable from both networks automatically
- `hostapd` + `dnsmasq` (hotspot configuration) are **out of scope** — assumed pre-configured on the host

---

## Project Structure

```
linux_traffic_shaping/
├── scripts/
│   ├── config.sh               ← legacy, moved here
│   ├── shaping.sh              ← legacy, moved here
│   └── speed.sh                ← legacy, moved here
├── PLAN.md                     ← this file
├── README.md
├── docker-compose.yml
├── backend/
│   ├── Dockerfile              ← python:3.12-slim + iproute2 (multi-arch)
│   ├── .dockerignore
│   ├── requirements.txt        ← fastapi, uvicorn, websockets
│   ├── main.py                 ← FastAPI app (REST + WebSocket endpoints)
│   ├── tc_runner.py            ← tc/ip subprocess wrappers
│   └── net_monitor.py          ← /proc/net/dev async reader
├── frontend/
│   ├── Dockerfile              ← multi-stage: node:20-alpine build → caddy:2-alpine
│   ├── .dockerignore
│   ├── index.html
│   ├── package.json
│   ├── vite.config.ts          ← dev proxy: /api + /ws → localhost:8000
│   ├── tsconfig*.json
│   ├── tailwind.config.js
│   ├── postcss.config.js
│   └── src/
│       ├── main.tsx
│       ├── App.tsx             ← root component, layout, shared state
│       ├── index.css           ← Tailwind base
│       ├── vite-env.d.ts
│       ├── api/
│       │   └── client.ts       ← typed fetch + WebSocket wrappers
│       └── components/
│           ├── InterfaceSelector.tsx  ← dropdown; auto-selects first wlan iface
│           ├── RateControl.tsx        ← rate preset grid + Apply/Clear buttons
│           └── NetworkChart.tsx       ← Recharts scrolling RX/TX + limit line
└── caddy/
    └── Caddyfile               ← tls internal, file_server, reverse_proxy
```

---

## Backend Detail

### `tc_runner.py`

- `get_interfaces()` — parses `ip -j link show` JSON; classifies each interface as `wlan`, `eth`, or `other`
- `get_qdisc(iface)` — parses `tc qdisc show dev <iface>` text output; returns active rate in kbps or `None`
- `set_rate(iface, rate_kbps)` — builds `tc qdisc add|change dev <iface> root tbf rate … burst … latency … peakrate … minburst …`; auto-detects `add` vs `change` from existing qdisc
- `clear_rate(iface)` — `tc qdisc del dev <iface> root`; silently ignores "no such qdisc"
- All subprocess calls with `shell=False`
- Input validation: interface name matches `^[a-zA-Z0-9._:-]{1,15}$`; rate must be a key in `ALLOWED_RATES` (strict enum)
- TBF constants from `scripts/config.sh`: `BURST=10kb`, `LATENCY=70ms`, `MINBURST=1540`

Allowed rate presets (kbps → tc rate string):

| kbps | tc rate | peakrate |
|---:|---|---|
| 64 | 64kbit | 100kbit |
| 128 | 128kbit | 200kbit |
| 256 | 256kbit | 300kbit |
| 384 | 384kbit | 500kbit |
| 512 | 512kbit | 700kbit |
| 1000 | 1mbit | 1200kbit |
| 2000 | 2mbit | 2200kbit |
| 3000 | 3mbit | 3300kbit |
| 4000 | 4mbit | 4400kbit |
| 5000 | 5mbit | 5500kbit |
| 50000 | 50mbit | 55mbit |

### `net_monitor.py`

- `get_rate(iface)` — async generator; reads `/proc/net/dev` byte counters every 500 ms via `asyncio.sleep`; yields `NetSample(rx_kbps, tx_kbps, ts)`

### `main.py` — FastAPI REST + WebSocket

| Method | Path | Description |
|---|---|---|
| GET | `/api/interfaces` | List interfaces with type (`wlan`/`eth`/`other`) |
| GET | `/api/rates` | List of allowed rate_kbps values |
| GET | `/api/status/{iface}` | `{iface, rate_kbps, active}` |
| POST | `/api/apply` | `{iface, rate_kbps}` → calls `set_rate` |
| DELETE | `/api/clear/{iface}` | calls `clear_rate` |
| WS | `/ws/stats?iface=<iface>` | Streams `{rx_kbps, tx_kbps, ts}` at 500 ms |

CORS allowed for `localhost:5173` (dev only); production traffic goes through Caddy.

---

## Frontend Detail

### `api/client.ts`

Typed wrappers: `fetchInterfaces()`, `fetchRates()`, `fetchStatus(iface)`, `applyRate(iface, rate_kbps)`, `clearRate(iface)`, `createStatsSocket(iface, onData)`.

WebSocket URL auto-adapts to `wss://` when served over HTTPS — works from both eth and wlan IPs without config.

### `InterfaceSelector.tsx`

- Dropdown populated from `/api/interfaces`
- On mount: auto-selects first `wlan` interface (falls back to first available)
- Status badge: shows active rate (`1 Mbit/s`) or `Unshaped`

### `RateControl.tsx`

- Grid of preset buttons; selected rate shown in large display
- **Apply** — calls `applyRate`; shows spinner while in-flight
- **Clear** — calls `clearRate`
- Inline error display on failure

### `NetworkChart.tsx`

- Recharts `LineChart`, 60-sample rolling buffer (30 seconds)
- RX line: blue `#3b82f6`; TX line: orange `#f97316`
- Dashed amber `ReferenceLine` at the active shaping rate limit
- Y-axis auto-scales in kbit/s; X-axis shows last 30 s
- Animation disabled (`isAnimationActive={false}`) for smooth 500 ms updates

---

## Caddy & Compose

### `caddy/Caddyfile`

```
:443 {
  tls internal
  root * /srv
  file_server
  reverse_proxy /api/* localhost:8000
  reverse_proxy /ws/*  localhost:8000
  try_files {path} /index.html
}

:80 {
  redir https://{host}{uri} permanent
}
```

`localhost:8000` is reachable because both Caddy and backend share `network_mode: host`.

### `docker-compose.yml`

- **`backend`**: `network_mode: host`, `cap_add: [NET_ADMIN]`, `restart: unless-stopped`
- **`caddy`**: `network_mode: host`; mounts `./caddy/Caddyfile:/etc/caddy/Caddyfile:ro`; named volume `caddy_data:/data` for persistent TLS certs; React `dist/` is baked into the image at `/srv`
- No `ports:` needed — host network mode binds directly

---

## Running

```bash
# First run (or after code changes)
docker compose up --build

# Subsequent starts
docker compose up -d

# Trust the Caddy internal CA once (run on the Pi)
docker exec $(docker compose ps -q caddy) caddy trust

# Access from hotspot clients
https://<wlan-ip>         # e.g. https://192.168.50.1

# Access from upstream LAN
https://<eth-ip>          # e.g. https://192.168.1.42

# Verify shaping is applied on host
tc qdisc show dev wlp0s20f3
```

---

## Verification Checklist

- [ ] `docker compose up --build` completes on AMD64
- [ ] `docker compose up --build` completes on ARM64 (Raspberry Pi)
- [ ] `https://<host-ip>` — browser reaches the UI (TLS warning expected on first visit)
- [ ] Interface dropdown populates; wlan interface pre-selected
- [ ] Apply 2 Mbit/s → `tc qdisc show dev <wlan-iface>` shows `tbf rate 2Mbit`
- [ ] Chart shows live RX/TX; amber dashed reference line appears at 2 Mbit/s
- [ ] Clear → `tc qdisc show` shows no tbf; badge shows "Unshaped"; reference line gone
- [ ] Stack restart → Caddy reuses stored cert (no new browser warning)
- [ ] WebSocket reconnects after brief network drop

---

## Out of Scope

- `hostapd` / `dnsmasq` hotspot configuration on the host
- Ingress shaping (only egress/download from hotspot clients is shaped)
- Per-client shaping (TBF shapes the whole wlan interface, not individual IPs)
- Authentication / access control on the web UI

# Linux Traffic Shaper (LTS)

A browser-based bandwidth throttling tool for Linux hosts. Select a network interface, choose a rate preset, and apply real-time traffic shaping — no terminal required.

Designed to run on a Raspberry Pi (or any Linux machine with **two network interfaces**): one Ethernet interface receives internet from an upstream router, and one WiFi interface shares that connection as a hotspot. Traffic shaping is applied on the WiFi (egress) side, letting you simulate slow internet conditions for any device connected to the hotspot — mobile phones, smart TVs, IoT devices, etc.

---

## Features

- **Web UI** — React + Tailwind SPA served over HTTPS (self-signed CA, no public domain needed)
- **Bandwidth presets** — 64 kbit/s → 50 Mbit/s in one click; holds until you clear or change it
- **Live traffic chart** — real-time RX/TX line chart updated every 500 ms via WebSocket
- **WiFi hotspot management** — create, start, stop, and auto-start a WPA2 hotspot from the UI (requires NetworkManager)
- **Multi-arch** — tested on ARM64 (Raspberry Pi 4/5) and AMD64

---

## How it works

```
Internet ── [Router] ──(eth0)── Linux Host ──(wlan0/hotspot)── Clients
                         ↑            ↑               ↑
                    upstream       IP forward      tc TBF shaping
                    internet       + NAT           on wlan (egress)
```

**Two network interfaces are required:**

| Interface        | Role                                                                | Example name         |
| ---------------- | ------------------------------------------------------------------- | -------------------- |
| Ethernet (`eth`) | Uplink — receives internet from the upstream router                 | `eth0`, `enp0s31f6`  |
| WiFi (`wlan`)    | Hotspot — clients connect here; traffic is shaped on this interface | `wlan0`, `wlp0s20f3` |

The Linux host acts as a router: it receives internet on the Ethernet interface and re-shares it over WiFi. IP forwarding and NAT (`iptables` masquerade) route traffic between the two interfaces. LTS then applies `tc qdisc` Token Bucket Filter shaping on the WiFi egress, throttling all bandwidth seen by connected clients.

The Docker container uses `network_mode: host` and `CAP_NET_ADMIN` so it operates directly on the host's real network interfaces. Caddy serves the frontend and proxies API/WebSocket traffic to FastAPI — both bind to all host IPs automatically, making the Web UI reachable from both the Ethernet and WiFi networks.

---

## Requirements

**Host (target Linux machine):**

| Requirement       | Notes                                                                             |
| ----------------- | --------------------------------------------------------------------------------- |
| Linux kernel 4.x+ | Any modern distro: Raspberry Pi OS Bookworm, Ubuntu 22.04+, Debian 12+            |
| Docker Engine 24+ | [Install guide](https://docs.docker.com/engine/install/)                          |
| Docker Compose v2 | Included with Docker Desktop; `docker compose` (not `docker-compose`)             |
| NetworkManager    | Only needed for WiFi hotspot feature. Install: `sudo apt install network-manager` |

**For local development (macOS/Windows):**

| Requirement    | Notes                                   |
| -------------- | --------------------------------------- |
| Docker Desktop | Provides Docker + Compose               |
| Node.js 20+    | For running the Vite dev server locally |

> **Note:** `tc` traffic shaping and WiFi hotspot management only work on a real Linux host. On macOS/Windows the UI and API work but shaping commands have no effect.

---

## Network setup (host prerequisites)

Before starting the Docker stack, the host must be configured to bridge WiFi clients to the internet via the Ethernet interface. This is a one-time setup.

### 1. Enable IP forwarding

```bash
# Apply immediately
sudo sysctl -w net.ipv4.ip_forward=1

# Persist across reboots
echo "net.ipv4.ip_forward=1" | sudo tee /etc/sysctl.d/99-ipforward.conf
```

### 2. Add NAT masquerade rule

Replace `eth0` with your actual Ethernet interface name:

```bash
sudo iptables -t nat -A POSTROUTING -o eth0 -j MASQUERADE
```

To persist the rule across reboots:

```bash
sudo apt install iptables-persistent
sudo netfilter-persistent save
```

### 3. Start the WiFi hotspot

Use the **Web UI** (recommended — see [WiFi hotspot](#wifi-hotspot) in Usage), or manually via `nmcli`:

```bash
# Replace wlan0, MyNetwork, and MyPassword with your values
sudo nmcli device wifi hotspot ifname wlan0 ssid MyNetwork password MyPassword
```

Once these three steps are done, devices connected to the WiFi hotspot will have internet access through the Ethernet uplink, and LTS can shape their bandwidth.

---

## Installation

### 1. Clone the repository

```bash
git clone <repo-url>
cd linux_traffic_shaping
```

### 2. (Optional) Enable NetworkManager for hotspot support

Skip if you don't need the hotspot feature.

```bash
sudo apt install network-manager
sudo systemctl enable --now NetworkManager
```

### 3. Build and start the stack

```bash
docker compose up --build -d
```

This builds two containers:

- **backend** — FastAPI + `tc`/`nmcli` wrappers (Python 3.12)
- **caddy** — Multi-stage build: Vite builds the React SPA, then Caddy serves it over HTTPS

### 4. Trust the Caddy CA certificate (first run only)

To silence the browser's HTTPS warning on client devices:

```bash
# On the host:
docker compose exec caddy caddy trust
```

Then open the host's IP in your browser: `https://<host-ip>`

---

## Usage

### Web UI

Open `https://<host-ip>` in any browser on the local network.

| Section             | Description                                                                       |
| ------------------- | --------------------------------------------------------------------------------- |
| **Interface**       | Dropdown of all network interfaces; auto-selects the first WiFi interface         |
| **Bandwidth Limit** | Click a rate preset, then **Apply** to start shaping or **Clear** to remove it    |
| **Live Traffic**    | Scrolling RX/TX chart (last 30 seconds); dashed amber line shows the active limit |
| **WiFi Hotspot**    | Configure SSID and password, start/stop the hotspot, toggle auto-start on boot    |

### Bandwidth presets

| Preset     | Simulates                                               |
| ---------- | ------------------------------------------------------- |
| 64 kbit/s  | 2G GPRS edge                                            |
| 128 kbit/s | 2G / slow EDGE                                          |
| 256 kbit/s | 3G low-end                                              |
| 512 kbit/s | 3G typical                                              |
| 1 Mbit/s   | 3G good                                                 |
| 2–5 Mbit/s | 4G / slow broadband                                     |
| 50 Mbit/s  | Full rate (effectively unthrottled on most connections) |

### WiFi hotspot

1. Open the **WiFi Hotspot** section in the sidebar.
2. Enter an SSID and a WPA2 password (8–63 characters).
3. Select the WiFi interface (only `wlan` interfaces are shown).
4. Toggle **Auto-start on boot** to restart the hotspot automatically when the Docker stack starts.
5. Click **Start Hotspot**.

Hotspot config (SSID, interface, auto-start flag) is persisted in a Docker named volume (`hotspot_data`) and survives container restarts. The password is stored locally on the host only.

> **Requirement:** NetworkManager must be installed and running on the host. The D-Bus socket (`/run/dbus/system_bus_socket`) must be accessible — it is mounted automatically by `docker-compose.yml`.

---

## Local Development (macOS / Windows)

Traffic shaping and hotspot management won't work, but the UI and API run fine.

### 1. Start the backend

```bash
# docker-compose.override.yml switches the backend to bridge mode and exposes port 8000
docker compose up backend
```

### 2. Start the Vite dev server

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`. API calls are proxied to `localhost:8000` automatically.

---

## Project structure

```
linux_traffic_shaping/
├── backend/
│   ├── Dockerfile              # python:3.12-slim + iproute2 + network-manager
│   ├── main.py                 # FastAPI app — REST + WebSocket endpoints
│   ├── tc_runner.py            # tc/ip subprocess wrappers
│   ├── net_monitor.py          # /proc/net/dev async RX/TX reader (500 ms)
│   ├── hotspot_runner.py       # nmcli hotspot lifecycle + config persistence
│   └── requirements.txt
├── frontend/
│   ├── Dockerfile              # Multi-stage: node build → caddy:2-alpine
│   └── src/
│       ├── App.tsx
│       ├── api/client.ts       # Typed fetch + WebSocket wrappers
│       └── components/
│           ├── InterfaceSelector.tsx
│           ├── RateControl.tsx
│           ├── HotspotControl.tsx
│           └── NetworkChart.tsx
├── caddy/
│   └── Caddyfile               # TLS internal, file_server, reverse_proxy
├── scripts/                    # Legacy bash scripts (kept for reference)
│   ├── config.sh
│   ├── shaping.sh
│   └── speed.sh
└── docker-compose.yml
```

---

## API reference

| Method   | Path                     | Description                                                        |
| -------- | ------------------------ | ------------------------------------------------------------------ |
| `GET`    | `/api/interfaces`        | List interfaces with type (`wlan`/`eth`/`other`)                   |
| `GET`    | `/api/rates`             | List of allowed rate presets (kbps)                                |
| `GET`    | `/api/status/{iface}`    | Current shaping state for an interface                             |
| `POST`   | `/api/apply`             | Apply rate: `{"iface": "wlan0", "rate_kbps": 1000}`                |
| `DELETE` | `/api/clear/{iface}`     | Remove shaping from interface                                      |
| `WS`     | `/ws/stats?iface=wlan0`  | Stream `{rx_kbps, tx_kbps, ts}` at 500 ms                          |
| `GET`    | `/api/hotspot`           | Current hotspot status                                             |
| `GET`    | `/api/hotspot/config`    | Stored hotspot config (password redacted)                          |
| `POST`   | `/api/hotspot/configure` | Configure and start: `{"ssid", "password", "iface", "auto_start"}` |
| `POST`   | `/api/hotspot/stop`      | Stop hotspot and disable auto-start                                |

---

## Troubleshooting

**Browser shows HTTPS warning**
Run `docker compose exec caddy caddy trust` on the host, then re-open the page.

**"NetworkManager not available" in the hotspot panel**
Ensure NetworkManager is installed and running on the host:

```bash
sudo systemctl status NetworkManager
```

**Shaping has no effect**
Confirm the container has `NET_ADMIN` capability and is using `network_mode: host`:

```bash
docker compose exec backend tc qdisc show
```

**Port 443/80 already in use**
Another service (nginx, apache) is binding those ports. Stop it or change Caddy's ports in `docker-compose.yml`.

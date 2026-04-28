// API client — typed wrappers around fetch and WebSocket.

export interface IfaceInfo {
  name: string
  iface_type: 'wlan' | 'eth' | 'other'
}

export interface StatusInfo {
  iface: string
  rate_kbps: number | null
  active: boolean
}

export interface NetSample {
  rx_kbps: number
  tx_kbps: number
  ts: number
}

async function _checkResponse(res: Response): Promise<Response> {
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error((body as { detail?: string }).detail ?? res.statusText)
  }
  return res
}

export async function fetchInterfaces(): Promise<IfaceInfo[]> {
  const res = await _checkResponse(await fetch('/api/interfaces'))
  return res.json()
}

export async function fetchRates(): Promise<number[]> {
  const res = await _checkResponse(await fetch('/api/rates'))
  const data = (await res.json()) as { rates: number[] }
  return data.rates
}

export async function fetchStatus(iface: string): Promise<StatusInfo> {
  const res = await _checkResponse(
    await fetch(`/api/status/${encodeURIComponent(iface)}`),
  )
  return res.json()
}

export async function applyRate(
  iface: string,
  rate_kbps: number,
): Promise<StatusInfo> {
  const res = await _checkResponse(
    await fetch('/api/apply', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ iface, rate_kbps }),
    }),
  )
  return res.json()
}

export async function clearRate(iface: string): Promise<StatusInfo> {
  const res = await _checkResponse(
    await fetch(`/api/clear/${encodeURIComponent(iface)}`, {
      method: 'DELETE',
    }),
  )
  return res.json()
}

/**
 * Open a WebSocket to /ws/stats?iface=<iface> and call onData on each frame.
 * Returns a cleanup function that closes the socket.
 */
export function createStatsSocket(
  iface: string,
  onData: (sample: NetSample) => void,
  onError?: (e: Event) => void,
): () => void {
  const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const url = `${proto}//${window.location.host}/ws/stats?iface=${encodeURIComponent(iface)}`
  const ws = new WebSocket(url)

  ws.onmessage = (e: MessageEvent) => {
    try {
      onData(JSON.parse(e.data as string) as NetSample)
    } catch {
      // ignore malformed frames
    }
  }

  if (onError) ws.onerror = onError

  return () => ws.close()
}

// ── Hotspot API ──────────────────────────────────────────────────────────────

export interface HotspotStatus {
  available: boolean
  active: boolean
  ssid: string | null
  iface: string | null
  auto_start: boolean
}

export interface HotspotConfig {
  ssid: string
  iface: string
  auto_start: boolean
}

export async function fetchHotspotStatus(): Promise<HotspotStatus> {
  const res = await _checkResponse(await fetch('/api/hotspot'))
  return res.json()
}

export async function fetchHotspotConfig(): Promise<HotspotConfig> {
  const res = await _checkResponse(await fetch('/api/hotspot/config'))
  return res.json()
}

export async function configureHotspot(
  ssid: string,
  password: string,
  iface: string,
  auto_start: boolean,
): Promise<HotspotStatus> {
  const res = await _checkResponse(
    await fetch('/api/hotspot/configure', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ssid, password, iface, auto_start }),
    }),
  )
  return res.json()
}

export async function stopHotspot(): Promise<HotspotStatus> {
  const res = await _checkResponse(
    await fetch('/api/hotspot/stop', { method: 'POST' }),
  )
  return res.json()
}

import { useEffect, useState } from 'react'
import {
  configureHotspot,
  fetchHotspotStatus,
  fetchInterfaces,
  stopHotspot,
  type HotspotStatus,
  type IfaceInfo,
} from '../api/client'

export default function HotspotControl() {
  const [status, setStatus] = useState<HotspotStatus | null>(null)
  const [ifaces, setIfaces] = useState<IfaceInfo[]>([])

  // Form state
  const [ssid, setSsid] = useState('')
  const [password, setPassword] = useState('')
  const [selectedIface, setSelectedIface] = useState('')
  const [autoStart, setAutoStart] = useState(false)
  const [showPassword, setShowPassword] = useState(false)

  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    fetchHotspotStatus()
      .then(setStatus)
      .catch(() => setStatus(null))

    fetchInterfaces()
      .then((all) => {
        const wlans = all.filter((i) => i.iface_type === 'wlan')
        setIfaces(wlans)
        if (wlans[0]) setSelectedIface(wlans[0].name)
      })
      .catch(() => {})
  }, [])

  const handleStart = async () => {
    if (!ssid || !password || !selectedIface) return
    setLoading(true)
    setError(null)
    try {
      const s = await configureHotspot(ssid, password, selectedIface, autoStart)
      setStatus(s)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Unknown error')
    } finally {
      setLoading(false)
    }
  }

  const handleStop = async () => {
    setLoading(true)
    setError(null)
    try {
      const s = await stopHotspot()
      setStatus(s)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Unknown error')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <label className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
          WiFi Hotspot
        </label>
        {status && (
          <span
            className={`text-xs px-2 py-0.5 rounded-full font-medium ${
              !status.available
                ? 'bg-slate-700 text-slate-500'
                : status.active
                  ? 'bg-emerald-900/60 text-emerald-400'
                  : 'bg-slate-700 text-slate-400'
            }`}
          >
            {!status.available ? 'Unavailable' : status.active ? 'Active' : 'Inactive'}
          </span>
        )}
      </div>

      {/* nmcli not reachable */}
      {status && !status.available && (
        <div className="text-xs text-slate-500 bg-slate-700/40 rounded-lg px-3 py-2">
          NetworkManager not available on this host. Mount the D-Bus socket and
          ensure NetworkManager is running.
        </div>
      )}

      {/* Active state: info + stop */}
      {status?.available && status.active && (
        <div className="flex flex-col gap-3">
          <div className="bg-slate-700/50 rounded-lg px-4 py-3 text-sm space-y-1">
            <div className="flex justify-between">
              <span className="text-slate-400">SSID</span>
              <span className="text-white font-medium">{status.ssid ?? '—'}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-400">Interface</span>
              <span className="text-white font-medium">{status.iface ?? '—'}</span>
            </div>
          </div>
          <button
            onClick={handleStop}
            disabled={loading}
            className="py-3 bg-red-700 hover:bg-red-600 disabled:opacity-40 disabled:cursor-not-allowed text-white font-semibold rounded-lg transition-colors"
          >
            {loading ? 'Stopping…' : 'Stop Hotspot'}
          </button>
        </div>
      )}

      {/* Inactive state: configuration form */}
      {(!status || (status.available && !status.active)) && (
        <div className="flex flex-col gap-3">
          {/* SSID */}
          <div className="flex flex-col gap-1">
            <label className="text-xs text-slate-400">SSID</label>
            <input
              type="text"
              value={ssid}
              onChange={(e) => setSsid(e.target.value)}
              maxLength={32}
              placeholder="Network name"
              className="bg-slate-700 border border-slate-600 rounded-lg px-3 py-2 text-sm text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>

          {/* Password */}
          <div className="flex flex-col gap-1">
            <label className="text-xs text-slate-400">Password</label>
            <div className="relative">
              <input
                type={showPassword ? 'text' : 'password'}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                maxLength={63}
                placeholder="Min 8 characters"
                className="w-full bg-slate-700 border border-slate-600 rounded-lg px-3 py-2 pr-14 text-sm text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
              <button
                type="button"
                onClick={() => setShowPassword((v) => !v)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-xs text-slate-400 hover:text-slate-200"
              >
                {showPassword ? 'Hide' : 'Show'}
              </button>
            </div>
          </div>

          {/* Interface selector (wlan only) */}
          {ifaces.length > 0 && (
            <div className="flex flex-col gap-1">
              <label className="text-xs text-slate-400">Interface</label>
              <select
                value={selectedIface}
                onChange={(e) => setSelectedIface(e.target.value)}
                className="bg-slate-700 border border-slate-600 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                {ifaces.map((i) => (
                  <option key={i.name} value={i.name}>
                    {i.name}
                  </option>
                ))}
              </select>
            </div>
          )}

          {/* Auto-start toggle */}
          <label className="flex items-center gap-3 cursor-pointer select-none">
            <div
              onClick={() => setAutoStart((v) => !v)}
              className={`w-10 h-5 rounded-full transition-colors relative ${
                autoStart ? 'bg-blue-600' : 'bg-slate-600'
              }`}
            >
              <div
                className={`absolute top-0.5 w-4 h-4 bg-white rounded-full shadow transition-transform ${
                  autoStart ? 'translate-x-5' : 'translate-x-0.5'
                }`}
              />
            </div>
            <span className="text-sm text-slate-300">Auto-start on boot</span>
          </label>

          <button
            onClick={handleStart}
            disabled={loading || !ssid || password.length < 8 || !selectedIface}
            className="py-3 bg-emerald-700 hover:bg-emerald-600 disabled:opacity-40 disabled:cursor-not-allowed text-white font-semibold rounded-lg transition-colors"
          >
            {loading ? 'Starting…' : 'Start Hotspot'}
          </button>
        </div>
      )}

      {error && (
        <div className="bg-red-900/50 border border-red-500 text-red-300 text-sm rounded-lg px-4 py-2">
          {error}
        </div>
      )}
    </div>
  )
}

import { useEffect, useState } from 'react'
import { fetchClients, type ClientInfo } from '../api/client'

interface Props {
  iface: string
  hotspotActive: boolean
}

function signalBar(dbm: number | null): string {
  if (dbm == null) return '—'
  if (dbm >= -55) return '▂▄▆█'
  if (dbm >= -65) return '▂▄▆·'
  if (dbm >= -75) return '▂▄··'
  return '▂···'
}

function fmtRate(kbps: number | null): string {
  if (kbps == null) return '—'
  if (kbps >= 1000) return `${(kbps / 1000).toFixed(0)} Mbit/s`
  return `${kbps} kbit/s`
}

export default function WifiClients({ iface, hotspotActive }: Props) {
  const [clients, setClients] = useState<ClientInfo[]>([])

  useEffect(() => {
    if (!iface || !hotspotActive) {
      setClients([])
      return
    }

    const poll = () => {
      fetchClients(iface)
        .then(setClients)
        .catch(() => setClients([]))
    }

    poll()
    const id = setInterval(poll, 5000)
    return () => clearInterval(id)
  }, [iface, hotspotActive])

  if (!hotspotActive) return null

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
          Connected Clients
        </span>
        <span className="text-xs text-slate-500">
          {clients.length} {clients.length === 1 ? 'device' : 'devices'}
        </span>
      </div>

      {clients.length === 0 ? (
        <p className="text-sm text-slate-500 italic">No clients connected</p>
      ) : (
        <div className="overflow-x-auto rounded-lg border border-slate-700">
          <table className="w-full text-sm text-left">
            <thead>
              <tr className="text-xs text-slate-400 uppercase bg-slate-800 border-b border-slate-700">
                <th className="px-3 py-2">Device</th>
                <th className="px-3 py-2">IP</th>
                <th className="px-3 py-2">Signal</th>
                <th className="px-3 py-2">TX</th>
                <th className="px-3 py-2">RX</th>
              </tr>
            </thead>
            <tbody>
              {clients.map((c) => (
                <tr
                  key={c.mac}
                  className="border-b border-slate-700 last:border-0 hover:bg-slate-800/50"
                >
                  <td className="px-3 py-2">
                    <div className="font-mono text-xs text-slate-300">{c.mac}</div>
                    {c.device_type && (
                      <div className="text-xs text-blue-400 font-medium">{c.device_type}</div>
                    )}
                    {!c.device_type && c.vendor && (
                      <div className="text-xs text-slate-500">{c.vendor}</div>
                    )}
                    {c.hostname && (
                      <div className="text-xs text-slate-500">{c.hostname}</div>
                    )}
                  </td>
                  <td className="px-3 py-2 text-slate-300 font-mono text-xs">
                    {c.ip ?? '—'}
                  </td>
                  <td className="px-3 py-2 text-slate-300 font-mono text-xs">
                    <span title={c.signal_dbm != null ? `${c.signal_dbm} dBm` : undefined}>
                      {signalBar(c.signal_dbm)}
                    </span>
                  </td>
                  <td className="px-3 py-2 text-slate-300 text-xs">{fmtRate(c.tx_kbps)}</td>
                  <td className="px-3 py-2 text-slate-300 text-xs">{fmtRate(c.rx_kbps)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

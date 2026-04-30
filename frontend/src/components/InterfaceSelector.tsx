import { useEffect, useState } from 'react'
import {
  fetchInterfaces,
  type IfaceInfo,
  type StatusInfo,
} from '../api/client'

interface Props {
  selected: string
  onSelect: (iface: string) => void
  status: StatusInfo | null
}

function formatRate(status: StatusInfo | null): string {
  if (!status || !status.active || status.rate_kbps == null) return 'Unshaped'
  const r = status.rate_kbps
  if (r >= 1000) return `${r / 1000} Mbit/s`
  return `${r} kbit/s`
}

function ifaceLabel(i: IfaceInfo): string {
  if (i.iface_type === 'wlan') return `${i.name} (WiFi)`
  if (i.iface_type === 'eth') return `${i.name} (Ethernet)`
  return i.name
}

export default function InterfaceSelector({ selected, onSelect, status }: Props) {
  const [interfaces, setInterfaces] = useState<IfaceInfo[]>([])
  const [loading, setLoading] = useState(true)

  // Load interface list once; auto-select first wlan interface
  useEffect(() => {
    fetchInterfaces()
      .then((ifaces) => {
        setInterfaces(ifaces)
        if (!selected) {
          const wlan = ifaces.find((i) => i.iface_type === 'wlan')
          const first = wlan ?? ifaces[0]
          if (first) onSelect(first.name)
        }
      })
      .finally(() => setLoading(false))
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const isActive = status?.active ?? false

  return (
    <div className="flex flex-col gap-2">
      <label className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
        Interface
      </label>
      <div className="flex items-center gap-3">
        <select
          value={selected}
          onChange={(e) => onSelect(e.target.value)}
          disabled={loading}
          className="
            flex-1 bg-slate-700 text-white rounded-lg px-3 py-2 text-sm
            border border-slate-600 focus:outline-none focus:ring-2
            focus:ring-blue-500 disabled:opacity-50 cursor-pointer
          "
        >
          {interfaces.map((i) => (
            <option key={i.name} value={i.name}>
              {ifaceLabel(i)}
            </option>
          ))}
        </select>

        <span
          className={`
            px-3 py-1 rounded-full text-xs font-bold whitespace-nowrap
            ${isActive ? 'bg-amber-500 text-black' : 'bg-emerald-700 text-white'}
          `}
        >
          {formatRate(status)}
        </span>
      </div>
    </div>
  )
}

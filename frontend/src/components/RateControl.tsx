import { useState } from 'react'
import { applyRate, clearRate, type StatusInfo } from '../api/client'

interface Props {
  iface: string
  rates: number[]
  onStatusChange: (status: StatusInfo) => void
}

function rateLabel(kbps: number): string {
  if (kbps >= 1000) return `${kbps / 1000} Mbit/s`
  return `${kbps} kbit/s`
}

export default function RateControl({ iface, rates, onStatusChange }: Props) {
  const [selected, setSelected] = useState<number | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleApply = async () => {
    if (!iface || selected == null) return
    setLoading(true)
    setError(null)
    try {
      const status = await applyRate(iface, selected)
      onStatusChange(status)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Unknown error')
    } finally {
      setLoading(false)
    }
  }

  const handleClear = async () => {
    if (!iface) return
    setLoading(true)
    setError(null)
    try {
      const status = await clearRate(iface)
      onStatusChange(status)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Unknown error')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <label className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
        Bandwidth Limit
      </label>

      {/* Rate preset grid */}
      <div className="grid grid-cols-3 gap-2">
        {rates.map((r) => (
          <button
            key={r}
            onClick={() => setSelected(r)}
            className={`
              px-2 py-2 rounded-lg text-sm font-medium transition-colors
              ${
                selected === r
                  ? 'bg-blue-600 text-white ring-2 ring-blue-400'
                  : 'bg-slate-700 text-slate-300 hover:bg-slate-600'
              }
            `}
          >
            {rateLabel(r)}
          </button>
        ))}
      </div>

      {/* Selected rate large display */}
      <div className="text-center py-5 bg-slate-800 rounded-xl border border-slate-700">
        <span className="text-4xl font-bold text-white tracking-tight">
          {selected != null ? rateLabel(selected) : '—'}
        </span>
      </div>

      {/* Action buttons */}
      <div className="flex gap-3">
        <button
          onClick={handleApply}
          disabled={loading || !iface || selected == null}
          className="
            flex-1 py-3 bg-blue-600 hover:bg-blue-500
            disabled:opacity-40 disabled:cursor-not-allowed
            text-white font-semibold rounded-lg transition-colors
          "
        >
          {loading ? 'Applying…' : 'Apply'}
        </button>
        <button
          onClick={handleClear}
          disabled={loading || !iface}
          className="
            flex-1 py-3 bg-slate-600 hover:bg-slate-500
            disabled:opacity-40 disabled:cursor-not-allowed
            text-white font-semibold rounded-lg transition-colors
          "
        >
          Clear
        </button>
      </div>

      {/* Error message */}
      {error && (
        <div className="bg-red-900/50 border border-red-500 text-red-300 text-sm rounded-lg px-4 py-2">
          {error}
        </div>
      )}
    </div>
  )
}

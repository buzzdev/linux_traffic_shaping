import { useEffect, useState } from 'react'
import { fetchRates, fetchStatus, type HotspotStatus, type StatusInfo } from './api/client'
import HotspotControl from './components/HotspotControl'
import InterfaceSelector from './components/InterfaceSelector'
import NetworkChart from './components/NetworkChart'
import RateControl from './components/RateControl'
import WifiClients from './components/WifiClients'

export default function App() {
  const [selectedIface, setSelectedIface] = useState('')
  const [rates, setRates] = useState<number[]>([])
  const [status, setStatus] = useState<StatusInfo | null>(null)
  const [hotspotStatus, setHotspotStatus] = useState<HotspotStatus | null>(null)

  useEffect(() => {
    fetchRates().then(setRates).catch(console.error)
  }, [])

  useEffect(() => {
    if (!selectedIface) return
    fetchStatus(selectedIface)
      .then(setStatus)
      .catch(() => setStatus(null))
  }, [selectedIface])

  const handleIfaceSelect = (iface: string) => {
    setSelectedIface(iface)
    setStatus(null)
  }

  const handleStatusChange = (s: StatusInfo) => {
    setStatus(s)
  }

  const shapingActive = status?.active ?? false

  return (
    <div className="min-h-screen bg-slate-900 text-white flex flex-col">
      {/* ── Header ─────────────────────────────────────────────── */}
      <header className="px-6 py-3 border-b border-slate-700 flex items-center gap-4 shrink-0">
        <div className="flex items-baseline gap-2">
          <span className="text-xl font-bold text-blue-400 tracking-tight">LTS</span>
          <span className="text-slate-400 text-sm">Linux Traffic Shaper</span>
        </div>

        {selectedIface && (
          <div className="ml-auto text-xs">
            {shapingActive ? (
              <span className="text-amber-400">
                ⬤ Shaping active on {selectedIface}
              </span>
            ) : (
              <span className="text-emerald-400">
                ⬤ No shaping on {selectedIface}
              </span>
            )}
          </div>
        )}
      </header>

      {/* ── Body ───────────────────────────────────────────────── */}
      <main className="flex-1 flex flex-col lg:flex-row overflow-hidden">
        {/* Left panel: controls */}
        <aside className="w-full lg:w-80 xl:w-96 bg-slate-800 border-r border-slate-700 p-6 flex flex-col gap-8 overflow-y-auto shrink-0">
          <InterfaceSelector
            selected={selectedIface}
            onSelect={handleIfaceSelect}
            status={status}
          />

          <RateControl
            iface={selectedIface}
            rates={rates}
            onStatusChange={handleStatusChange}
          />

          <HotspotControl onStatusChange={setHotspotStatus} />
        </aside>

        {/* Right panel: live chart + client list */}
        <section className="flex-1 p-6 min-h-[420px] lg:min-h-0 overflow-y-auto flex flex-col gap-6">
          <div className="flex-1 min-h-[300px]">
            <NetworkChart
              iface={selectedIface}
              limitKbps={shapingActive ? (status?.rate_kbps ?? null) : null}
            />
          </div>
          <WifiClients
            iface={hotspotStatus?.iface ?? selectedIface}
            hotspotActive={hotspotStatus?.active ?? false}
          />
        </section>
      </main>
    </div>
  )
}

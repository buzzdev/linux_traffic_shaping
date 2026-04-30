import { useEffect, useRef, useState } from 'react'
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { createStatsSocket, type NetSample } from '../api/client'

interface ChartPoint {
  /** Seconds relative to the most-recent sample (0 = now, -30 = 30 s ago) */
  t: number
  rx: number
  tx: number
}

interface Props {
  iface: string
  limitKbps: number | null
}

const MAX_SAMPLES = 60 // 30 seconds at 500 ms interval

function fmtKbps(value: number): string {
  if (value >= 1000) return `${(value / 1000).toFixed(1)} M`
  return `${Math.round(value)} k`
}

export default function NetworkChart({ iface, limitKbps }: Props) {
  const [data, setData] = useState<ChartPoint[]>([])
  const bufferRef = useRef<{ rx: number; tx: number; ts: number }[]>([])

  // Re-open the WebSocket whenever the selected interface changes
  useEffect(() => {
    if (!iface) return
    bufferRef.current = []
    setData([])

    const cleanup = createStatsSocket(iface, (sample: NetSample) => {
      const buf = bufferRef.current
      buf.push({ rx: sample.rx_kbps, tx: sample.tx_kbps, ts: sample.ts })
      if (buf.length > MAX_SAMPLES) buf.shift()

      const now = buf[buf.length - 1].ts
      const points: ChartPoint[] = buf.map((s) => ({
        t: Math.round((s.ts - now) * 2) / 2, // 0.5 s resolution
        rx: Math.round(s.rx),
        tx: Math.round(s.tx),
      }))
      setData(points)
    })

    return cleanup
  }, [iface])

  return (
    <div className="flex flex-col gap-2 h-full">
      <label className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
        Live Traffic — <span className="text-slate-300">{iface || '…'}</span>
      </label>

      <div className="flex-1 min-h-0">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart
            data={data}
            margin={{ top: 8, right: 24, left: 0, bottom: 0 }}
          >
            <CartesianGrid strokeDasharray="3 3" stroke="#334155" />

            <XAxis
              dataKey="t"
              type="number"
              domain={[-30, 0]}
              ticks={[-30, -25, -20, -15, -10, -5, 0]}
              tickFormatter={(v: number) => `${v}s`}
              stroke="#475569"
              tick={{ fill: '#94a3b8', fontSize: 11 }}
            />

            <YAxis
              tickFormatter={fmtKbps}
              stroke="#475569"
              tick={{ fill: '#94a3b8', fontSize: 11 }}
              width={60}
              unit="bit/s"
              domain={([, dataMax]: [number, number]) => [0, Math.max(dataMax * 1.15, 500)]}
            />

            <Tooltip
              contentStyle={{
                backgroundColor: '#1e293b',
                border: '1px solid #334155',
                borderRadius: 8,
                fontSize: 12,
              }}
              labelFormatter={(l: number) => `${l}s`}
              formatter={(value: number, name: string) => [
                `${fmtKbps(value)}bit/s`,
                name.toUpperCase(),
              ]}
            />

            <Legend
              wrapperStyle={{ color: '#94a3b8', fontSize: 12, paddingTop: 8 }}
            />

            {/* Dashed reference line at the active shaping limit */}
            {limitKbps != null && (
              <ReferenceLine
                y={limitKbps}
                stroke="#f59e0b"
                strokeDasharray="6 3"
                label={{
                  value: `Limit: ${fmtKbps(limitKbps)}bit/s`,
                  fill: '#f59e0b',
                  fontSize: 11,
                  position: 'insideTopRight',
                }}
              />
            )}

            <Line
              type="monotone"
              dataKey="rx"
              name="RX"
              stroke="#3b82f6"
              strokeWidth={2}
              dot={false}
              isAnimationActive={false}
            />
            <Line
              type="monotone"
              dataKey="tx"
              name="TX"
              stroke="#f97316"
              strokeWidth={2}
              dot={false}
              isAnimationActive={false}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}

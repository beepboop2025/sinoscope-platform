import { useMemo, useState, type ChangeEvent } from 'react'
import {
  ResponsiveContainer, LineChart, Line, XAxis, YAxis, Tooltip, CartesianGrid, Legend,
} from 'recharts'
import { DRUGS } from '../data/prices'
import { useData } from '../lib/dataStore'
import { affordabilityDays, purityAdjustedPrice } from '../lib/metrics'
import { explainPrices } from '../lib/explain'
import Explainer from './Explainer'

const fmtUsd = (v: number | string | null | undefined): string =>
  (v == null ? 'n/a' : `$${Number(v).toFixed(2)}`)

export default function Explorer() {
  const { priceRecords } = useData()
  const [drug, setDrug] = useState('cocaine')
  const [purityAdjusted, setPurityAdjusted] = useState(false)

  const rows = useMemo(
    () => priceRecords.filter((r) => r.drug === drug),
    [priceRecords, drug],
  )

  // Build a per-country price series for the chart (year on X, price on Y).
  const chartData = useMemo(() => {
    const years = [...new Set(rows.map((r) => r.year))].sort()
    return years.map((year) => {
      const point: Record<string, number> = { year }
      rows.filter((r) => r.year === year).forEach((r) => {
        const value = purityAdjusted
          ? purityAdjustedPrice(r.priceUsdPerGram, r.purityPct)
          : r.priceUsdPerGram
        if (value != null) point[r.country] = Number(value.toFixed(2))
      })
      return point
    })
  }, [rows, purityAdjusted])

  const countries = useMemo(() => [...new Set(rows.map((r) => r.country))], [rows])
  const drugLabel = DRUGS.find((d) => d.id === drug)?.label ?? drug
  const explanation = useMemo(() => explainPrices(rows, drugLabel), [rows, drugLabel])

  return (
    <section>
      <div className="controls">
        <label>
          Drug&nbsp;
          <select value={drug} onChange={(e: ChangeEvent<HTMLSelectElement>) => setDrug(e.target.value)}>
            {DRUGS.map((d) => <option key={d.id} value={d.id}>{d.label}</option>)}
          </select>
        </label>
        <label className="toggle">
          <input
            type="checkbox"
            checked={purityAdjusted}
            onChange={(e: ChangeEvent<HTMLInputElement>) => setPurityAdjusted(e.target.checked)}
          />
          &nbsp;Price per <em>pure</em> gram (purity-adjusted)
        </label>
      </div>

      <Explainer text={explanation} />

      <div className="chart-card">
        <h3>Retail price trend — {drugLabel}</h3>
        <ResponsiveContainer width="100%" height={280}>
          <LineChart data={chartData} margin={{ top: 8, right: 16, bottom: 8, left: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#26314a" />
            <XAxis dataKey="year" stroke="#8aa0c6" />
            <YAxis stroke="#8aa0c6" tickFormatter={(v) => `$${v}`} />
            <Tooltip
              contentStyle={{ background: '#0e1626', border: '1px solid #26314a' }}
              formatter={(v) => fmtUsd(v as number)}
            />
            <Legend />
            {countries.map((c, i) => (
              <Line key={c} type="monotone" dataKey={c} stroke={LINE_COLORS[i % LINE_COLORS.length]} dot strokeWidth={2} />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>

      <table className="data-table">
        <thead>
          <tr>
            <th>Country</th><th>Region</th><th>Year</th>
            <th>Price / g</th><th>Purity</th>
            <th>Price / pure g</th><th>Affordability</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => {
            const pure = purityAdjustedPrice(r.priceUsdPerGram, r.purityPct)
            const aff = affordabilityDays(r.priceUsdPerGram, r.iso3)
            return (
              <tr key={i}>
                <td>{r.country}</td>
                <td>{r.region}</td>
                <td>{r.year}</td>
                <td>{fmtUsd(r.priceUsdPerGram)}</td>
                <td>{r.purityPct == null ? 'n/a' : `${r.purityPct}%`}</td>
                <td>{fmtUsd(pure)}</td>
                <td title="Days of average local income per gram">
                  {aff == null ? 'n/a' : `${aff.toFixed(2)} days`}
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </section>
  )
}

const LINE_COLORS = ['#6ea8fe', '#ff9f6e', '#79e0a8', '#e06ec0', '#e0d36e']

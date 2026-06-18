#!/usr/bin/env node
/**
 * Fetch GDP-per-capita (current US$) from the World Bank for a list of ISO3 codes.
 *
 * Prints ready-to-paste entries for `GDP_PER_CAPITA_USD`.
 * This script only touches public World Bank data — it does NOT invent any
 * drug-trade figures.
 *
 * Usage:
 *   node fetch-gdp.mjs USA DEU COL AFG THA MMR
 *
 * Output:
 *   // GDP_PER_CAPITA_USD
 *   USA: 76398.1,
 *   DEU: 51203.55,
 *   // TODO: GDP for MMR
 */

const API_URL =
  'https://api.worldbank.org/v2/country/all/indicator/NY.GDP.PCAP.CD?format=json&per_page=20000&date=2020:2024'

const requested = process.argv.slice(2).map((s) => s.trim().toUpperCase()).filter(Boolean)

if (requested.length === 0) {
  console.error('Usage: node fetch-gdp.mjs <iso3> [<iso3> ...]')
  process.exit(1)
}

const requestedSet = new Set(requested)

async function main() {
  const res = await fetch(API_URL)
  if (!res.ok) {
    throw new Error(`World Bank API error: ${res.status} ${res.statusText}`)
  }

  const payload = await res.json()
  // World Bank returns [metadata, dataArray]
  const rows = Array.isArray(payload) && payload.length > 1 ? payload[1] : []

  /** @type {Map<string, { year: number; value: number }>} */
  const latest = new Map()

  for (const row of rows) {
    if (!row || typeof row !== 'object') continue
    const iso3 = String(row.countryiso3code || '').toUpperCase()
    const year = Number(row.date)
    const value = row.value

    if (!iso3 || !requestedSet.has(iso3)) continue
    if (value === null || value === undefined) continue
    if (!Number.isFinite(year)) continue

    const existing = latest.get(iso3)
    if (!existing || year > existing.year) {
      latest.set(iso3, { year, value: Number(value) })
    }
  }

  console.log('// GDP_PER_CAPITA_USD')
  let found = 0
  for (const iso3 of requested) {
    const entry = latest.get(iso3)
    if (entry) {
      console.log(`  ${iso3}: ${JSON.stringify(entry.value)}, // ${entry.year}`)
      found++
    } else {
      console.log(`  // TODO: GDP for ${iso3}`)
    }
  }
  console.log(`// Found ${found} / ${requested.length} requested countries`)
}

main().catch((err) => {
  console.error(err.message || err)
  process.exit(1)
})

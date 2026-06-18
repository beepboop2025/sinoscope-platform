#!/usr/bin/env node
/**
 * Best-effort extractor for Myanmar opium-cultivation hectares from PDF text.
 *
 * This script only converts PDF text into CSV cells; it does NOT invent any
 * numbers. `methIndex` is left blank because it is not published by UNODC.
 *
 * Usage:
 *   node from-pdf.mjs <input.pdf> <output.csv> [--year=2023]
 *
 * Outputs:
 *   - <output.csv>            CSV with headers region,year,opiumHa,methIndex
 *   - <output.csv>.raw.txt    Raw extracted text for operator verification
 *   - <output.csv>.warnings.txt  Ambiguous or heuristic-failure rows
 */

import fs from 'node:fs/promises'
import path from 'node:path'
import { getDocument } from 'pdfjs-dist/legacy/build/pdf.mjs'

// Region patterns in priority order (more specific patterns first).
const REGION_PATTERNS = [
  { pattern: /Shan\s*\(\s*North\s*\)|Shan\s+North/i, id: 'shan_north' },
  { pattern: /Shan\s*\(\s*South\s*\)|Shan\s+South/i, id: 'shan_south' },
  { pattern: /Shan\s*\(\s*East\s*\)|Shan\s+East/i, id: 'shan_east' },
  { pattern: /\bShan\b/i, id: 'shan' },
  { pattern: /\bKachin\b/i, id: 'kachin' },
  { pattern: /\bKayah\b/i, id: 'kayah' },
  { pattern: /\bKayin\b/i, id: 'kayin' },
  { pattern: /\bChin\b/i, id: 'chin' },
  { pattern: /\bMon\b/i, id: 'mon' },
  { pattern: /\bRakhine\b/i, id: 'rakhine' },
  { pattern: /\bBago\b/i, id: 'bago' },
  { pattern: /\bMagway\b/i, id: 'magway' },
  { pattern: /\bMandalay\b/i, id: 'mandalay' },
  { pattern: /\bSagaing\b/i, id: 'sagaing' },
  { pattern: /\bTanintharyi\b/i, id: 'tanintharyi' },
  { pattern: /\bYangon\b/i, id: 'yangon' },
  { pattern: /\bAyeyarwady\b|\bIrrawaddy\b/i, id: 'ayeyarwady' },
  { pattern: /\bNay\s*Pyi\s*Taw\b|\bNaypyitaw\b/i, id: 'naypyitaw' },
  { pattern: /\bWa\b/i, id: 'wa' },
  { pattern: /\bKokang\b/i, id: 'kokang' },
]

const HECTARE_RE = /([\d,]+(?:\.\d+)?)\s*(?:ha|hectares)\b/i

function parseArgs(argv) {
  const args = argv.slice(2)
  let year = ''
  const positional = []
  for (const arg of args) {
    const yearMatch = arg.match(/^--year(?:=(.+))?$/)
    if (yearMatch) {
      year = (yearMatch[1] ?? '').trim()
    } else {
      positional.push(arg)
    }
  }
  return { positional, year }
}

async function extractText(pdfPath) {
  const data = await fs.readFile(pdfPath)
  const loadingTask = getDocument({
    data: new Uint8Array(data),
    useSystemFonts: true,
  })
  const pdf = await loadingTask.promise
  const parts = []
  for (let i = 1; i <= pdf.numPages; i++) {
    const page = await pdf.getPage(i)
    const content = await page.getTextContent()
    const text = content.items.map((item) => item.str).join('\n')
    parts.push(`--- Page ${i} ---\n${text}`)
  }
  return parts.join('\n\n')
}

function matchRegion(line) {
  for (const { pattern, id } of REGION_PATTERNS) {
    if (pattern.test(line)) return id
  }
  return null
}

function extractRows(text, year) {
  const rows = []
  const warnings = []
  const seen = new Set()
  const lines = text.split(/\r?\n/)

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i].trim()
    if (!line) continue

    const region = matchRegion(line)
    if (!region) continue

    // PDFs often split a table row across lines; look a few lines ahead for
    // the hectare value while avoiding values that belong to the next region.
    let haMatch = null
    let valueLineIndex = -1
    for (let offset = 0; offset <= 2 && i + offset < lines.length; offset++) {
      const candidate = lines[i + offset].trim()
      // If we hit another region before a hectare value, stop looking ahead.
      if (offset > 0 && matchRegion(candidate)) break
      const match = candidate.match(HECTARE_RE)
      if (match) {
        haMatch = match
        valueLineIndex = i + offset
        break
      }
    }

    if (!haMatch) {
      warnings.push(
        `Line ${i + 1}: matched region "${region}" but no hectare value found`
      )
      continue
    }

    const opiumHa = parseFloat(haMatch[1].replace(/,/g, ''))
    if (!Number.isFinite(opiumHa) || opiumHa < 0) {
      warnings.push(
        `Line ${i + 1}: invalid hectare value "${haMatch[1]}" for region "${region}"`
      )
      continue
    }

    const key = `${region}|${opiumHa}`
    if (seen.has(key)) continue
    seen.add(key)

    rows.push({
      region,
      year: year || '',
      opiumHa,
      methIndex: '',
    })

    // Skip the line that held the value so it is not re-processed.
    if (valueLineIndex > i) {
      i = valueLineIndex
    }
  }

  return { rows, warnings }
}

function escapeCsvCell(value) {
  const str = String(value ?? '')
  if (/[",\n\r]/.test(str)) {
    return `"${str.replace(/"/g, '""')}"`
  }
  return str
}

function toCsv(rows, headers) {
  const lines = [headers.join(',')]
  for (const row of rows) {
    lines.push(headers.map((h) => escapeCsvCell(row[h])).join(','))
  }
  return lines.join('\n') + '\n'
}

async function main() {
  const { positional, year } = parseArgs(process.argv)
  if (positional.length < 2) {
    console.error(
      'Usage: node from-pdf.mjs <input.pdf> <output.csv> [--year=2023]'
    )
    process.exit(1)
  }

  const [inputPath, outputPath] = positional
  const rawPath = `${outputPath}.raw.txt`
  const warningsPath = `${outputPath}.warnings.txt`

  const text = await extractText(inputPath)
  await fs.mkdir(path.dirname(outputPath), { recursive: true })
  await fs.writeFile(rawPath, text, 'utf8')

  const { rows, warnings } = extractRows(text, year)
  const csv = toCsv(rows, ['region', 'year', 'opiumHa', 'methIndex'])
  await fs.writeFile(outputPath, csv, 'utf8')

  if (warnings.length > 0) {
    await fs.writeFile(warningsPath, warnings.join('\n') + '\n', 'utf8')
  } else {
    await fs.writeFile(
      warningsPath,
      '// No ambiguous rows detected by the heuristic.\n',
      'utf8'
    )
  }

  console.log(
    '\n⚠️  IMPORTANT: Every extracted row MUST be verified against the PDF before loading.'
  )
  console.log(
    '   The heuristic can misread headers, totals, footnotes, and multi-line cells.\n'
  )
  console.log(`Rows extracted: ${rows.length}`)
  console.log(`Ambiguous rows: ${warnings.length}`)
  console.log(`Output CSV:     ${outputPath}`)
  console.log(`Raw text:       ${rawPath}`)
  console.log(`Warnings:       ${warningsPath}`)
}

main().catch((err) => {
  console.error(err.message || err)
  process.exit(1)
})

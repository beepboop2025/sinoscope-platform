# Source-file conversion scripts

These scripts help turn raw downloads into the exact CSV schemas expected by the
app loaders in `src/lib/ingest.ts`. They are deliberately strict: missing or
ambiguous rows are reported, never silently patched.

## Where to put raw files

Drop your downloaded source files in:

```
scripts/convert/input/
```

Scripts write their outputs to:

```
scripts/convert/output/
```

Never overwrite the app's bundled data files directly — review the CSV and its
warnings first.

## Where to download each source

| Dataset | App loader | Source(s) |
|---|---|---|
| Street prices | `parsePrices` | UNODC *Drugs: prices* — https://dataunodc.un.org (Drugs → Prices); World Drug Report annex price tables; EUDA/EMCDDA price & purity tables — https://www.euda.europa.eu/data |
| Precursor prices | `parsePrecursorPrices` | INCB *Precursors* annual report — https://www.incb.org/incb/en/precursors/; UNODC *Synthetic Drugs in East & Southeast Asia* |
| Precursor flows / seizures | `parseFlows` | INCB PICS aggregate statistics; UNODC seizures (dataUNODC); World Drug Report precursor chapter |
| Myanmar regions (geo table) | `parseMyanmarRegions` | Administrative-region centroids — build once by hand |
| Myanmar border nodes (geo table) | `parseMyanmarBorderNodes` | Named corridor-town coordinates — build once by hand |
| Myanmar region stats | `parseMyanmarRegionRecords` | UNODC **Myanmar Opium Survey** cultivation by region (hectares) |
| Myanmar flows | `parseMyanmarFlows` | UNODC *Synthetic Drugs in East & Southeast Asia*, Mekong/Golden Triangle seizure reporting |
| GDP per capita | `GDP_PER_CAPITA_USD` | World Bank `NY.GDP.PCAP.CD` — https://api.worldbank.org/v2/country/all/indicator/NY.GDP.PCAP.CD |

## How to run each script

### `fetch-gdp.mjs` — pull GDP-per-capita from the World Bank

```bash
node scripts/convert/fetch-gdp.mjs USA DEU COL AFG THA MMR
```

Copy the printed block into `src/data/prices.js` under `GDP_PER_CAPITA_USD`.
The script prints a `// TODO` line for any ISO3 code that has no recent value.

### `from-spreadsheet.mjs` — convert Excel/CSV sheets to loader CSVs

Install the script-only dependency first:

```bash
npm install --save-dev xlsx
```

Run it with a schema, input file, and output file:

```bash
node scripts/convert/from-spreadsheet.mjs prices \
  scripts/convert/input/unodc-prices.xlsx \
  scripts/convert/output/prices.csv

node scripts/convert/from-spreadsheet.mjs flows \
  scripts/convert/input/incb-pics.csv \
  scripts/convert/output/flows.csv

node scripts/convert/from-spreadsheet.mjs precursorPrices \
  scripts/convert/input/precursor-prices.xlsx \
  scripts/convert/output/precursor-prices.csv

node scripts/convert/from-spreadsheet.mjs mmRegionRecords \
  scripts/convert/input/myanmar-opium-survey.xls \
  scripts/convert/output/myanmar-region-records.csv
```

Open the generated CSV and its `.warnings.txt` sibling, fix any flagged rows,
then load the CSV through the footer **"Load official data (CSV)"** panel.

### `from-pdf.mjs` — best-effort Myanmar opium hectares from PDF text

Install the script-only dependency first:

```bash
npm install --save-dev pdfjs-dist
```

```bash
node scripts/convert/from-pdf.mjs \
  scripts/convert/input/unodc-myanmar-opium-2023.pdf \
  scripts/convert/output/myanmar-region-records-2023.csv \
  --year=2023
```

The PDF extractor is heuristic only. It writes the raw extracted text to
`<output.csv>.raw.txt` and warnings to `<output.csv>.warnings.txt`.

## ⚠️ VERIFY BEFORE LOADING

Every generated CSV, especially from PDF extraction, **must be spot-checked
against the original source** before it is loaded into the app. Bad or ambiguous
rows are reported in `.warnings.txt`, but the final responsibility for accuracy
is yours.

## Important: `methIndex` must be filled by the operator

The UNODC Myanmar Opium Survey publishes regional **opium cultivation in
hectares** (`opiumHa`). It does **not** publish a synthetic-drug activity index.
The `methIndex` column in `mmRegionRecords` is a relative 0–100 indicator that
**you** must construct from regional meth seizure / lab-dismantling counts (or
another documented method). Leave it blank if you have not yet constructed it;
`from-pdf.mjs` leaves it blank automatically.

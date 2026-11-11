# Spreadsheet workflow (metadata + image links)

Use this when Getty won't let you mass-download files but you can keep metadata and preview URLs.

## Option A — Auto-export from the board (recommended)

1. Open the board signed in to Getty and **scroll** so every thumbnail loads.
2. Open the console: **Option+Command+J** (Mac) or **F12** → Console.
3. If Chrome blocks paste, type exactly: `allow pasting` then press **Enter**.
4. Open `scripts/export_getty_board.js` in Cursor, copy all, paste into Console, **Enter**.
5. You should see an alert **“Success: exported N portraits”** and a file in Downloads.

### Console messages you can ignore

| Message | Meaning |
|---------|---------|
| `apple-mobile-web-app-capable` is deprecated | Getty’s page HTML — not our script |
| `px.airpr.com` … `ERR_NAME_NOT_RESOLVED` | Getty analytics failing — not our script |
| “Don’t paste code into DevTools…” | Chrome security — type `allow pasting` first |

If there is **no success alert**, use Option B below.

## Option B — Build the sheet manually

1. Copy `getty_portraits.template.csv` → `getty_portraits.csv`
2. Open in Excel or Google Sheets.
3. One row per portrait. Required columns: **id**, **imageUrl**  
   Recommended: title, artist, date, sourceUrl

To get **imageUrl** for one asset:

- Open the image on Getty → right-click the large preview → **Copy image address**  
  (URLs usually look like `https://media.gettyimages.com/id/1234567890/...`)

## Scan all rows

```bash
pip install -r requirements.txt
python3 build_from_spreadsheet.py --fresh
```

This fetches each `imageUrl`, scans the face, saves a copy under `assets/`, and writes `art_database.json` with your metadata intact.

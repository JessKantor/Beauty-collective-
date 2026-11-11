# The Beauty Collective

An exhibition prototype for the **International Center of Photography**, matching visitor face shapes to portraits sourced from **Getty Images**.

## Live demo

After GitHub Pages is enabled: `https://jesskantor.github.io/Beauty-collective-/`

## Quick start

```bash
python3 -m http.server 8080
# Open http://localhost:8080
```

## Building the Getty database

### Spreadsheet (metadata + image links) — recommended

Keep full metadata without mass-downloading files:

1. Run `scripts/export_getty_board.js` in your browser console on the Getty board, **or**
2. Fill in `getty_portraits.csv` from `getty_portraits.template.csv` (Excel / Google Sheets)

```bash
pip install -r requirements.txt
python3 build_from_spreadsheet.py --fresh
```

Each row is fetched from `imageUrl`, face-scanned, saved to `assets/`, and written to `art_database.json`.

See `getty_images/SPREADSHEET.md` for details.

### Local file download

Save board previews into `getty_images/`, then `python3 scan_getty_downloads.py --fresh`.

## Partners

International Center of Photography · Getty Images

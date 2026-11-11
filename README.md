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

Getty collaboration boards require sign-in; export your board assets into `getty_manifest.json` (see `getty_manifest.example.json`), then:

```bash
pip install -r requirements.txt
python3 build_getty_database.py --fresh
```

This scans each image, classifies face shape, and writes `art_database.json`.

## Partners

International Center of Photography · Getty Images

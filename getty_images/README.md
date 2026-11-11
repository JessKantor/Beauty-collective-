# Getty board downloads

1. Open the board in your browser (signed in to Getty):
   https://www.gettyimages.com/collaboration/boards/eAGAgBoofEe_WRznFnIkxw?invitation_code=QYdrFq7FQEm1pKCfXf2umA

2. Download preview/comp images from the board into **this folder**.

3. Run from the project root:

```bash
pip install -r requirements.txt
python3 scan_getty_downloads.py --fresh
```

4. Commit `assets/` and `art_database.json`, then push to GitHub.

## Optional metadata

Add `metadata.json` here to set titles and photographers:

```json
{
  "1234567890": {
    "title": "Portrait title",
    "artist": "Photographer name",
    "date": "1972",
    "sourceUrl": "https://www.gettyimages.com/detail/1234567890"
  }
}
```

Use the Getty image ID from the filename (6–12 digits) as the key.

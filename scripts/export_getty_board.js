/**
 * Export Getty collaboration board metadata + image URLs as CSV.
 *
 * HOW TO RUN IN CHROME
 * 1. Open your board while signed in (scroll so thumbnails load).
 * 2. Press Option+Command+J (Mac) or F12 → Console tab.
 * 3. If Chrome says “Don’t paste code…”, TYPE this exactly (no quotes):  allow pasting
 *    Then press Enter. Now you can paste.
 * 4. Paste this entire file, press Enter.
 * 5. You should get an alert + getty_portraits.csv download.
 *
 * IGNORE these (they are Getty’s site, not this script):
 *   - apple-mobile-web-app-capable deprecated
 *   - px.airpr.com … ERR_NAME_NOT_RESOLVED
 */

(async () => {
  const BOARD_ID = "eAGAgBoofEe_WRznFnIkxw";
  const headers = [
    "id",
    "title",
    "artist",
    "date",
    "collection",
    "culture",
    "category",
    "medium",
    "imageUrl",
    "sourceUrl",
  ];

  const esc = (value) => {
    const text = String(value ?? "").replace(/\r?\n/g, " ").trim();
    if (/[",\n]/.test(text)) return `"${text.replace(/"/g, '""')}"`;
    return text;
  };

  const row = (r) => headers.map((h) => esc(r[h])).join(",");

  const byId = new Map();

  const add = (asset) => {
    const id = String(asset.id || asset.assetId || asset.asset_id || "").trim();
    if (!id || byId.has(id)) return;
    const imageUrl =
      asset.imageUrl ||
      asset.previewUrl ||
      asset.uri ||
      (asset.display_sizes || [])
        .map((s) => s.uri)
        .find(Boolean) ||
      "";
    const title = asset.title || asset.caption || asset.name || "";
    const artist = asset.artist || asset.photographer || asset.creator || "";
    const date = asset.date || asset.dateCreated || asset.year || "";
    byId.set(id, {
      id,
      title,
      artist,
      date,
      collection: asset.collection || asset.boardName || "Getty Board",
      culture: asset.culture || "",
      category: asset.category || asset.asset_type || "Portrait",
      medium: asset.medium || "Photography",
      imageUrl,
      sourceUrl: asset.sourceUrl || `https://www.gettyimages.com/detail/${id}`,
    });
  };

  // Strategy 1: in-page JSON bootstrap (Next.js / hydration)
  const nextData = document.getElementById("__NEXT_DATA__");
  if (nextData) {
    try {
      const blob = JSON.stringify(JSON.parse(nextData.textContent));
      const idMatches = blob.matchAll(/"id"\s*:\s*"?(\d{6,12})"?/g);
      for (const m of idMatches) {
        const id = m[1];
        const title = (blob.match(new RegExp(`"id"\\s*:\\s*"${id}"[^}]*"title"\\s*:\\s*"([^"]+)"`)) || [])[1] || "";
        const uri = (blob.match(new RegExp(`"id"\\s*:\\s*"${id}"[^}]*"uri"\\s*:\\s*"([^"]+)"`)) || [])[1] || "";
        add({ id, title, imageUrl: uri });
      }
    } catch (_) {}
  }

  // Strategy 2: authenticated board API (uses your browser session)
  const apiPaths = [
    `/collaboration/api/v1/boards/${BOARD_ID}/assets`,
    `/collaboration/api/boards/${BOARD_ID}/assets`,
    `/api/v3/boards/${BOARD_ID}`,
  ];
  for (const path of apiPaths) {
    try {
      const res = await fetch(path, { credentials: "include" });
      if (!res.ok) continue;
      const data = await res.json();
      const assets = data.assets || data.items || data.data || (Array.isArray(data) ? data : []);
      for (const asset of assets) add(asset);
    } catch (_) {}
  }

  // Strategy 3: visible thumbnails on the page
  document.querySelectorAll("img[src*='gettyimages'], img[srcset*='gettyimages']").forEach((img) => {
    const src = img.currentSrc || img.src || "";
    const idMatch = src.match(/\b(\d{6,12})\b/);
    if (!idMatch) return;
    const id = idMatch[1];
    const card = img.closest("article, li, [data-testid], [class*='asset'], [class*='Asset']");
    const title =
      card?.querySelector("h2, h3, [class*='title'], [class*='Title']")?.textContent?.trim() || "";
    const artist =
      card?.querySelector("[class*='artist'], [class*='Artist'], [class*='creator']")?.textContent?.trim() || "";
    add({ id, title, artist, imageUrl: src });
  });

  // Strategy 4: detail links on the board
  document.querySelectorAll("a[href*='/detail/']").forEach((a) => {
    const idMatch = a.href.match(/detail\/(\d{6,12})/);
    if (!idMatch) return;
    add({
      id: idMatch[1],
      title: a.textContent.trim(),
      sourceUrl: a.href,
    });
  });

  const rows = Array.from(byId.values());
  if (rows.length === 0) {
    const msg =
      "No assets found.\n\nTry:\n• Scroll through the entire board first\n• Refresh the page, wait for thumbnails\n• Run the script again\n\nOr build getty_portraits.csv manually (see getty_images/SPREADSHEET.md).";
    console.warn(msg);
    alert(msg);
    return;
  }

  const csv = [headers.join(","), ...rows.map(row)].join("\n");
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = "getty_portraits.csv";
  link.click();
  URL.revokeObjectURL(url);

  console.log(`Exported ${rows.length} rows to getty_portraits.csv`);
  alert(`Success: exported ${rows.length} portraits.\n\nCheck your Downloads folder for getty_portraits.csv`);
})();

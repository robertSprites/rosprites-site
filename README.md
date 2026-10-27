# Rosprites

A static personal website with an independent UGC analytics section. The collector remains
in `%LOCALAPPDATA%\RospritesPrivate\better-ugc-analytics-tool`, outside this repository.

## Refresh the website data

First let the private analytics tool sync. In PowerShell, from this website folder, run:

```powershell
python .\tools\refresh_site.py
```

This exports group **233120758 / ALT Studios!**, then builds `dist/`. The refresh command
uses installed Python and needs no extra packages or Roblox credentials.

The requested full version includes revenue, group funds, pending Robux, item counts,
daily item totals, and personal account balance (displayed separately near the page title).
To omit the personal balance, add `--no-balance`. For counts only with no balance, add
`--counts-only --no-balance`. To use a different group, pass `--group-id` and `--group-name`.

For direct control over the exporter:

```powershell
python .\tools\export_analytics.py --group-id 233120758 --group-name "ALT Studios!" --include-financials --include-balance
python .\tools\build_site.py
```

By default the exporter publishes counts only. `--include-financials` also enables earned
Robux; `--include-balance` separately enables personal balance. `--db` can select a different
private database. The output is `data/ugc-stats.json`.

## Preview locally

```powershell
python -m http.server 8000 --bind 127.0.0.1 --directory dist
```

Open **http://127.0.0.1:8000**. Stop with Ctrl+C. Serve `dist/`, not the private collector
folder. Opening `index.html` directly from disk will not load the JSON reliably.

## What is public

`data/ugc-stats.json` is deliberately public, including any financial fields you enable.
It contains day-level aggregates per item, catalog item IDs/names, group ID/name, and
selected current financial snapshots. Visitors can download every field in that JSON.

The exporter opens SQLite in read-only mode and does not open `roblox_cookie.txt`, `.env`,
or the collector configuration. It does not import or run the collector, call Roblox,
read buyer IDs or transaction IDs, export individual sale times, or copy raw metadata.
The website fetches only its own static JSON with browser credentials omitted.

The build script copies only explicitly listed public files to `dist/`; it never copies
the collector, cookie, database, CSV imports, tests, or development tools. `.gitignore`
also excludes common secret and private-data filenames, but never put them in this repo.

## Publishing and updates

Use the existing hosting for rosprites.com. The static publishing folder is `dist/`; no
Python server is required on the public host. If the host builds from GitHub, commit the
generated public JSON with the website source and run `python tools/build_site.py` in the
host build, using `dist` as its output folder. If it serves the repository directly,
`index.html`, `assets/`, `data/ugc-stats.json`, and `preview.jpg` work from the root too.
Confirm the actual Cloudflare/GitHub hosting setup before changing deployment settings.

This version uses snapshots, not live browser access to the private tool. Running the
collector updates the private database. Running the export refreshes the local snapshot.
Publishing that snapshot refreshes what visitors see. While your computer is off, the
last published snapshot remains visible, with its original timestamp.

After the initial website integration is published, this single command refreshes the
snapshot, rebuilds the preview, commits only `data/ugc-stats.json`, and pushes it through
the existing GitHub-to-Cloudflare connection:

```powershell
python .\tools\refresh_site.py --publish
```

It uses your existing Git authentication and never force-pushes. Other staged source files
are excluded from the snapshot commit. Run the private collector's sync first for new data.

History reflects records actually synced or imported. It is not labelled lifetime history.
UTC dates match the collector's day buckets; today is included and marked partial.
Missing monetary values display as unknown rather than zero. Financial values are the
collector's latest cached readings; the collector may retain an older individual value
after a partially failed refresh, so its shared updated time is not per-field freshness.

## Extending the site

`assets/site.css` owns general typography and layout. `assets/analytics.css` scopes all its
rules to `.ugc-analytics`; `assets/analytics.js` initializes only that section. Add future
sections alongside `#ugc` without adding another analytics application or iframe. The graph
uses native SVG, with no remote chart scripts. The original social preview remains intact.

The data collector is [zdragonxi/better-ugc-analytics-tool](https://github.com/zdragonxi/better-ugc-analytics-tool).

## Verification

```powershell
python -m unittest discover -s tests -p test_export_analytics.py
node tests/test_analytics.mjs
```

These checks use synthetic data, including private-data sentinels, to verify filtering,
group isolation, opt-in financial fields, date ranges, and unknown-revenue handling.

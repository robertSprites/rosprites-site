# Rosprites

A pure black first screen with one centered Little Plustergeist image button.
Clicking, tapping, or activating it with the keyboard makes smaller ghost PNGs
rain down the screen. Scroll below it for "ads to fund our website" and a wall
of real game promotional artwork. There is no audio.

The static site needs no build step. Serve the repository root; `index.html`
loads `assets/little-plustergeist.png`. Every click adds more rain without
removing ghosts already falling. Rain uses one canvas, removes ghosts after
they fall offscreen, and stops when empty or when the tab is hidden.
Reduced motion preferences use fewer ghosts without spinning or swaying.

The ad wall contains 5,820 distinct promotional images as ordinary, unlinked
image elements with native lazy loading.
Artwork is hosted locally in `assets/ads/`; no advertising SDK, remote image
request, click handler, or tracking code is used for the wall. The responsive
grid shows three columns on desktop, two on tablets, and one on phones.

`data/ads.json` records each image's title, official store page, original image
URL, dimensions, and checksum. `tools/collect_ads.py` collects publisher-supplied
Steam promotional banners, filters sexual-content tags and descriptors, skips
unavailable artwork, and removes exact duplicates. It respects source cooldowns
and resumes downloaded files. `tools/render_ads.py` rebuilds the image markup
from that manifest; the published site needs no Python or build process.

Link previews use the requested Grabify title, description, and logo as a
prank. The logo is served locally from `assets/discord-preview.png`; the
preview metadata does not add tracking or change the ghost page.

The private Roblox analytics collector remains separate from this website.

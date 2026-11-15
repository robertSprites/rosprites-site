# Rosprites

A pure black page with one centered Little Plustergeist image button. Clicking,
tapping, or activating it with the keyboard makes smaller ghost PNGs rain down
the screen. There is no visible text or audio.

The static site needs no build step. Serve the repository root; `index.html`
loads `assets/little-plustergeist.png`. Every click adds more rain without
removing ghosts already falling. Rain uses one canvas, removes ghosts after
they fall offscreen, and stops when empty or when the tab is hidden.
Reduced motion preferences use fewer ghosts without spinning or swaying.

Link previews use the requested Grabify title, description, and logo as a
prank. The logo is served locally from `assets/discord-preview.png`; the
preview metadata does not add tracking or change the ghost page.

The private Roblox analytics collector remains separate from this website.

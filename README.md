# Rosprites

A pure black page with one centered Little Plustergeist image button. Clicking,
tapping, or activating it with the keyboard makes smaller ghost PNGs rain down
the screen. There is no visible text or audio.

The static site needs no build step. Serve the repository root; `index.html`
loads `assets/little-plustergeist.png`. Rain uses one canvas, stops when empty
or when the tab is hidden, and caps active ghosts during repeated clicks.
Reduced motion preferences use fewer ghosts without spinning or swaying.

The private Roblox analytics collector remains separate from this website.

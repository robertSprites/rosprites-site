# Rosprites

An intentionally blank static page that alternates full white and full black
every 3.492 seconds. A CSS animation runs a 6.984-second cycle with an instant
change halfway through. Serve `index.html` directly; there is no build step
or visible interface.

`assets/background.mp3` is the full supplied background track, encoded at
96 kbps to fit the hosting limit. Audio loops without visible controls.
Playback starts automatically when the browser allows it; otherwise, clicking,
tapping, or pressing a key anywhere on the page starts it. Playback retries do
not restart a track that is already playing. The audio is hosted locally and
uses metadata preloading so the full recording need not load before playback.

Earlier versions of the website are preserved in Git history.
The private Roblox analytics collector remains separate from this website.

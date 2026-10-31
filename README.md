# PosterFox for Android

PosterFox — the PosterChan-branded Firefox — for Android. It is Mozilla's Firefox for Android (Fenix) at the release
tag in `UPSTREAM`, with the changes in `patches/`, built on GitHub Actions and published to Zapstore.

Planned, in this order:

1. Build an unmodified Fenix on GitHub Actions (artifact mode: Mozilla's compiled engine, our Gradle build).
2. PosterFox name, icon and colours; telemetry off; uBlock Origin and Privacy Badger; privacy defaults.
3. **Bookmark sync with PosterChan**, built into the app. Firefox for Android has no `bookmarks` WebExtension API, so
   the PosterChan extension cannot sync bookmarks there; the browser does it itself, sharing one set with desktop
   PosterFox and the extension.
4. Signed releases on GitHub and Zapstore.

Not available on Android: per-tab containers and the AI sidebar.

"""The hauling part of the monthly run (H1, SD14): hauling templates and station positions from the game files, as
StarCitizenWiki/scunpacked-data publishes them, normalized to the app's contract (sc-cargoplan/docs/hauling-data-format.md,
schema 1) and released as two flat assets with a manifest section `hauling`.

  source     the commit (gh api) and its tarball (one GET), streamed: contracts/*.json and starmap_positions.json
  templates  a raw contract -> a template of schema 1, or the reason it is left out (V8: nothing estimated)
  positions  pool names -> starmap entries (alias table, K1), the positions file (stations, planets, stars, pool places)
  check      the app's loader checks and the pipeline's own rules on the two files
  diff       against the last release: templates and places new, gone, changed; the changelog text
  stage      run.py hauling and run.py hauling-pr; never stops the ship data (K2)"""

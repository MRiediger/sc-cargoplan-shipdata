# SC-CargoPlan Ship Data

Datenpipeline für [SC-CargoPlan](https://github.com/MRiediger/sc-cargoplan): Frachtgitter, Umrisse und Hologramm-Meshes aller Star-Citizen-Schiffe, monatlich von GitHub Actions gebaut und als Data-Release `ships-YYYY.MM[.N]` veröffentlicht. Die App holt sich den Stand selbst.
**Ziel: läuft ohne Martin.** Ein Lauf endet mit nichts, einem Release oder einem PR – nie mit einer Aufgabe für einen Menschen.

## Wer hier arbeitet

Martin, 20+ Jahre IT (PowerShell, M365, Power Platform, Netzwerk). Python ist Lernfeld, PowerShell-Hintergrund hilft. Will den Code verstehen, nicht nur ausführen.

## Rollen (verbindlich)

- **Claude Code** plant und baut. Ein Task pro Session.
- **Claude.ai** reviewt jeden Plan im Master-Chat (Phase 12: „SC-CargoPlan | Phase 12“; Phase 13, H-Tasks: „SC-CargoPlan | Cargo-Routen Umsetzung“): Freigabe oder `korrektur-<Task>.md` im Repo-Ordner.
- **Martin** entscheidet, klickt (Dispatch, Approve, Merge, Repo-Settings), testet am Aufzug. **Martin tippt keine Pipeline-Befehle.** Braucht ein Schritt einen Befehl von ihm, ist das ein Befund gegen die Pipeline.

## Arbeitsweise (verbindlich)

- Wir sind per Du. Prägnant, direkt, keine Höflichkeitsfloskeln.
- **Bei jedem Schritt und jedem Befehl in einem Satz erklären, warum er nötig ist.**
- **Unterhaltung Deutsch. Code, Kommentare, Commits, README, Workflow-Logs: Englisch.** `TASKS.md`, Pläne und `docs/decisions.md` Deutsch.
- **Plan zuerst, dann stoppen.** Jeder Task beginnt mit `docs/plans/<Task>.md`, committet und gepusht. Weiter erst nach wörtlicher **„Freigabe“** (ggf. mit Korrektur-Datei). Ein Neustart des Plan Mode hebt eine ausstehende Freigabe nicht auf.
- **Abweichungen vom Task-Text** in der Planphase heißen „Präzisierung in der Planphase, ratifiziert durch Freigabe“ – in Plan, TASKS.md und Commit-Body, auch wenn Martin sie selbst gewählt hat.
- Bei Mehrdeutigkeit **nachfragen statt raten**. Fachbegriffe korrigieren, wenn Martin sie falsch verwendet.
- **Tests vor Implementierung** bei allem mit Logik (Diff, Regeln, Manifest, Vergleich). Erst rot sehen, dann bauen.
- **Zahlen statt Eindrücke.** Laufzeit, Größen, Abweichungen als Messwert in TASKS.md. Spike-Code nur für Fragen, deren Antwort das Design ändert; Spike-Code wird nie gestylt oder ausgebaut, nur gemessen.
- Keine neue Abhängigkeit (pip, npm, Action) ohne kurze Begründung und Pin in `TOOLS.md`.
- Direkt auf `main`, solange das Repo nur die Pipeline trägt. Branch + `git merge --no-ff` erst, wenn ein Lauf produktiv ist (ab T12.6).
- Commits **ohne** `Co-Authored-By`, mit Task-Prefix (`S12.0: …`, `T12.1: …`). Vor jedem Push `gh run list -L 3`.

## Das Problem

v0.5.1 der App brauchte einen halben Tag Handarbeit für drei neue Schiffe: vier Skripte in zwei Repos, stumme Logs, Zustand nur in Dateien, Doppel-Modelle nach dem Fetch, `modelKey`-Verlust im `-Create`-Zweig, ein Schiff aus dem Katalog verschwunden (Cyclone), ein Grid ohne Transform (135c), Holo-Tag als Konstante in der App. Jede Datenänderung war ein App-Release.

## Der Ansatz

**Daten und App trennen.** Dieses Repo baut, prüft und veröffentlicht die Daten; das App-Repo liest sie.

```
ship-data.yml – cron `23 4 1 * *` + workflow_dispatch (dry-run)
  1  Motherlode-API (Secret MOTHERLODE_API_KEY) + Modelle holen, Cache nach Modell-SHA
  1b hauling (H1, SD14): scunpacked-data (ein Commit: contracts/ + starmap_positions.json) → hauling-templates.json,
     positions.json, Alias-Tabelle, Loader-Checks der App, Diff; Fehlschlag = `failed`, nie ein Stopp (K2),
     hauling-pr meldet ihn (Alias-PR auf data/hauling-aliases oder Issue „Hauling job failed“)
  2  Diff gegen das letzte Data-Release: neu / geändert / verschwunden; ein Hauling-Diff allein zählt (SD14)
  3  kein Unterschied → kein Release; Lebenszeichen-Commit `state/last-run.json`
  4  Racks, Holos (nur geänderte Modelle), Umrisse, Anker – ein Lauf
  5  Regressions-Gate (windows-latest): Checkout sc-cargoplan auf gepinntem Tag,
     alter und neuer Datenstand im selben Job gerendert (ShipPictureTests),
     nur geänderte Schiffe dürfen abweichen
  6  Entwurfs-Release ships-YYYY.MM[.N] (SD10), Assets flach (SD4): manifest.json (zuletzt), NOTICE.md,
     ships.zip (ships/** + outlines.json), <slug>.holo je Schiff, hauling-templates.json + positions.json
     (Abschnitt `hauling`, H1); Kontaktabzug am Entwurf
     grün → Entwurf veröffentlichen, Hygiene, Modell-Cache prunen
     Regel feuert → PR auf data/YYYY.MM (state/pending.json + Befund); Martins Merge = Freigabe →
     publish-merged veröffentlicht genau diesen Entwurf; Gate rot → roter Lauf (SD11)
  7  heartbeat: state/last-run.json mit einer Zeile für Martin, in jedem Lauf außer Dry-Run
App: liest …/releases/latest/download/manifest.json, lädt ships.zip (assets.ships im Manifest),
     Holos lazy pro Schiff aus …/releases/download/<dataVersion>/<slug>.holo.
     release.yml der App zieht beim Build die Baseline ins ZIP.
```

**Regeln als Code** (jede mit Test; Begründung und Zahlen in `docs/decisions.md`):

| Fall | Regel |
|---|---|
| Judge (SD5, ersetzt P9) | Verschlechterung heißt Metrik, nicht Flag. PR mit Metriken und Bild, wenn `passed` true → false kippt; > 110 % Budget; Hausdorff um mehr als `HAUSDORFF_TOLERANCE` (0,0025, bestätigt in T12.1b: Re-Export-Rauschen 0 Pixel) schlechter als der Vorgänger; kein vergleichbarer Vorgänger (neues Schiff, Quellwechsel); bei `passed=false` eine zusätzliche Metrik verfehlt. Sonst Hinweis, auch bei `passed=false` (holo-v3: 22 Schiffe, alle nur Hausdorff) |
| Schiff aus dem Katalog verschwunden (SD6) | behalten, letzte Daten + Holo bleiben, `missingSince` im Manifest; nach 3 Läufen Backlog-Zeile. Mehr als **3** neu Verschwundene ohne Basis → PR |
| Variante verschwunden (SD6) | Basis-`className` im Katalog und Racks im letzten Manifest hash-gleich zur Basis → `follows` die Basis; sonst wie verschwunden |
| Schiff wieder da (SD6) | `missingSince` und `follows` → `null`, normal durch Diff, Build, Judge |
| Grid-Reihenfolge geändert | `orderKeys` im Manifest gegen den Katalog; gleiche Grids in anderer Reihenfolge → nicht schreiben → PR (schützt gespeicherte Pläne, App-V1) |
| Grid ohne Transform | Schiff bleibt auf seinem Stand – Eintrag in `overrides.json`, Hinweis |
| überlappende Grids | nicht schreiben → PR |
| Doppel-Modell nach Fetch | der Fetch räumt alte Hashes selbst weg |
| neues Schiff | `modelKey` aus der Map, Anker aus dem Modell – kein Rack-Mitte-Fallback |
| Lauf ohne Änderung | kein Release, aber Lebenszeichen-Commit (GitHub schaltet Cron nach 60 Tagen Repo-Stille ab) |
| Motherlode weg | letzter Datenstand bleibt gültig (A11-Exit-Plan) |
| Hauling-Job scheitert (Quelle, unbekanntes Titelwort, Prüfung rot, Absturz; K2, SD14) | Schiffsrelease läuft weiter; die Hauling-Dateien des Vorgängers gehen unverändert mit, ohne gültigen Vorgänger `hauling: null`; Issue „Hauling job failed“ (E1) |
| Ortsname ohne Position (Alias-Lücke) | wie oben, dazu PR auf `data/hauling-aliases` mit vorgeschlagenen Einträgen; Merge erweitert `tools/hauling-aliases.json`, die Daten kommen mit dem nächsten Lauf |
| Hauling-Inhalt geändert, Schiffe nicht (SD14) | Release mit 0 gebauten Modellen; das Gate rendert unveränderte Schiffe |

## Domänenfakten

- **Quelle:** Motherlode (Sciirof, cryon.rocks). Katalog per API mit Key; Modell-URLs stehen nicht in der API, sondern auf der Seite `cryon.rocks/ops/cargo` (RSC-Stream, ohne Key); Modelle liegen in einem öffentlichen Supabase-Bucket. Die OpenAPI-Spezifikation bestätigt: kein Modell-Endpunkt („Data only: no 3D models“, Zitat und Transform-Konvention in `docs/provenance.md`). Bis Sciirof einen liefert, bleibt der Seiten-Scraper – mit klarem Fehler und PR, sobald die Seite sich ändert. **Die API einmal pro Lauf rufen, nie in Schleife.** Sciirofs Freigabe für den Monatslauf ist erteilt (18.11.2026).
- **Schiffs-JSON:** Format in `sc-cargoplan/docs/ship-format.md`, `schemaVersion` aktuell 6 (`ShipLoader.SupportedSchemaVersion`; 4 und 5 liest die App noch) (Racks mit `origin`, `grid`, `stackAxis`, optional `rotation`; `modelKey`, `holoOrigin`, `outlineOrigin`). Koordinaten x Bug+, y Backbord+, z oben+, 1 Zelle = 1 SCU = 1,25 m. **Schema-Bump nur zusammen mit einem App-Release.**
- **Umriss:** `outlines.json`, Meter, Ursprung unabhängig vom Rack-Nullpunkt, Zuordnung per `modelKey` (App-D90, D94).
- **Holo:** Format SCH2 (`sc-cargoplan/docs/holo-format.md`), aus dem Motherlode-Modell: Flatten → Cull → Leiter 20k/30k/40k (meshoptimizer) → Export. CIG-Material: nie im Repo, nur Cache und Release-Asset, mit NOTICE; `holo: null` im Manifest ist der Kill-Switch.
- **Anker:** `tools/import-motherlode.ps1` (seit T12.1 hier; die App-Kopie geht mit T12.5).
- **Manifest** (`manifest.json` im Release, Format `docs/manifest-format.md`, ratifiziert mit SD2): `dataVersion`, `schemaVersion`, `generatedAt`, `builtFrom {motherlode {gameBuild, updatedAt}, appTag, pipelineCommit, tools}`, `assets {ships: "ships.zip"}`, `files {pfad im ZIP: sha256}`, `holo {formatVersion, ships {slug: {file, bytes, sha256, model, rawSha256, budget, …, passed, metrics}}} | null`, `hauling {schemaVersion, templates {file, bytes, sha256}, positions {…}} | null` (optional, H1), `ships {id: {source, modelKey, racksSha256, orderKeys, missingSince, follows}}`.
- **Hauling-Daten** (H1, SD14): Quelle `StarCitizenWiki/scunpacked-data` (octfx/ScDataDumper, dieselbe Extraktion wie api.star-citizen.wiki), `contracts/<uuid>.json` und `starmap_positions.json` aus **einem** Commit, Build aus der Commit-Message. Format: `sc-cargoplan/docs/hauling-data-format.md` (Schema 1 + Addenda der H1-Freigabe). CIG-Material wie die Holos: nie im Repo außer der Alias-Tabelle (Ortsnamen), nur Release-Asset mit NOTICE. Kein `holo.baseUrl`: die URL folgt aus `dataVersion`. Zähler und Herkunft je Schiff stehen **hier**, nicht in Extradateien.
- **Lizenz:** Code MIT (`LICENSE`), Daten und Holos unter eigener `NOTICE.md` (CIG-Material, nicht MIT). Katalog, Modelle, Bilder, Erecs PDF nie committen.

## Technische Entscheidungen

| Was | Entscheidung | Warum |
|---|---|---|
| Laufumgebung | **GitHub Actions**, `ubuntu-24.04` für die Kette (gepinnt: Python 3.14.5 gibt es für 26.04 = `ubuntu-latest` nicht, S12.0, SD8), `windows-latest` nur fürs Render-Gate | Kein eigener Server; Windows nur, wo WPF rendert. Kein Pin fürs Gate nötig: beide Stände entstehen im selben Job (SD3). |
| Kette | **Python** (numpy, opencv-python-headless) + **Node** (meshoptimizer WASM) + **pwsh** für Anker/Import, ein Einstieg `run.py` mit Unterbefehlen `fetch · diff · build · verify · release` | Bestehender, bewährter Code aus `sc-ship-outlines`; kein Blender, keine GPU, kein Display. |
| Pins | **eine maschinenlesbare Quelle je Pin** (SD8): `.python-version`, `.nvmrc` (`setup-python`/`setup-node` per `*-version-file`), `tools/pins.json` (`appTag`, `runner`, `pwsh`), `requirements*.txt`, `package-lock.json`. `TOOLS.md` ist die Abschrift für Menschen, `tests/test_versions.py` prüft beide | Lokal = CI nur mit denselben Versionen; Abweichung ist ein Befund. Kein Parser für Markdown, keine Logik im YAML. |
| Gate | **beide Stände im selben Job rendern**, Hash-exakt (`ShipPictureTests`), Schwelle nur für den Judge (SD3) | Runner- und Plattform-Drift fallen per Konstruktion weg (S12.0 K1). |
| Zustand | Manifest im Release + `state/last-run.json` im Repo (SD9) | Kein Zustand in Dateien, die nur lokal existieren. |
| Cache | nur Modelle nach SHA, **nie der Katalog** (SD7) | Fork-PR-Workflows können den Cache lesen. |
| Releases | **Pre-Release-Flag aus**, `releases/latest` ist immer das letzte Data-Release; letzte zwei bleiben; Assets flach: `manifest.json`, `NOTICE.md`, `ships.zip`, `<slug>.holo` (SD4); bis zur Veröffentlichung ein **Entwurf** als Ablage, Artefakte nur mit Berichten (SD10) | Die App braucht genau eine URL ohne API; GitHub-Assets können keine Ordner sein; CIG-Material nie in öffentlichen Artefakten. |
| PR-Pfad | `GITHUB_TOKEN` mit Repo-Einstellung „Allow GitHub Actions to create and approve pull requests“ (SD12); Martins Merge ist die Freigabe | Kein PAT, solange zwei Klicks reichen. |
| Lizenz | Code MIT, Daten NOTICE | Maximale Verbreitung des Codes, Rückziehbarkeit der Daten. |

## Projektstruktur (Ist nach T12.2)

```
sc-cargoplan-shipdata/
├── CLAUDE.md · TASKS.md · TOOLS.md · README.md · LICENSE · NOTICE.md · SECURITY.md
├── .python-version · .nvmrc       # Pins für setup-python / setup-node (SD8)
├── .github/workflows/
│   └── ship-data.yml              # Monatslauf + Dispatch (T12.2)
├── tools/
│   ├── run.py                     # Einstieg: fetch · previous · diff · build · verify · release · draft · gate · publish · pr · heartbeat · pins
│   ├── pins.json                  # appTag, runner, pwsh (SD8)
│   ├── shipdata/                  # Python-Paket: fetch, diff, rules, manifest, release, chain, stages, importer, compare, log,
│   │                              #   workflow (previous, draft, publish, pr, heartbeat), gate + sheet (Render-Gate), github (gh/git)
│   │   └── hauling/               # H1: source, templates, positions, check, diff, stage (run.py hauling, hauling-pr)
│   ├── hauling-aliases.json       # Vertragsname → Starmap-uuid oder drop (H1, K1, V6); Lücke → PR data/hauling-aliases
│   ├── holo_mesh.py · simplify.mjs                # Holo-Kette, byte-gleich zu holo-v3 (docs/provenance.md)
│   ├── import-motherlode.ps1 · ShipJson.ps1   # Racks + Anker (aus dem App-Repo gezogen, T12.1)
│   ├── local-wsl.sh               # WSL Ubuntu 24.04 mit den Pins: setup · test · run
│   ├── requirements.txt · requirements-dev.txt · package.json · package-lock.json
├── overrides.json                 # Schiffe, die auf einem alten Stand bleiben (Grid ohne Transform)
├── pytest.ini
├── state/last-run.json            # Lebenszeichen + Zusammenfassung des letzten Laufs (SD9, schreibt heartbeat)
├── state/pending.json             # nur auf dem PR-Branch: Entwurf + Manifest-SHA, den der Merge veröffentlicht
├── tests/                         # pytest: Regeln, Diff, Manifest, Vergleich; Fixtures klein und synthetisch
└── docs/
    ├── decisions.md               # SD1…, nummeriert; App-Entscheidungen bleiben in sc-cargoplan/docs/decisions.md
    ├── plans/                     # ein Plan je Task, bleibt als Geschichte
    ├── provenance.md              # Herkunft + SHA-256 der übernommenen Dateien
    └── manifest-format.md
```

Cache (`cache/`), Modelle (`*.glb`), Arbeitsordner, Bilder, PDFs und Kataloge sind gitignort.

## Befehle

```powershell
python -I tools/run.py fetch [--saved <dir>] [--catalog-only]   # Katalog per API (einmal) oder aus gespeicherten Antworten; Modelle nach Hash
python -I tools/run.py diff --previous <release-dir>            # gegen letztes Release (Manifest + ships.zip, ohne Holos): neu / geändert / verschwunden, Reihenfolge gegen orderKeys, Modelle separat
python -I tools/run.py build [--ship <id>] [--all]              # Flatten → Cull → Leiter → Export → Umriss → Anker
python -I tools/run.py verify                                   # Regeln + Manifest + Hashes; Exit 2 = PR-Pfad
python -I tools/run.py release --dry-run                        # Assets packen und zeigen (manifest.json, NOTICE.md, ships.zip, <slug>.holo), nichts hochladen
python -I tools/run.py release --seed --app <dir> --holo <dir> --catalog <raw-dir>  # erstes Release aus App + Holo-Release, orderKeys aus dem Katalog der App-Daten
python -I tools/run.py previous                                 # letztes Release (nach Version, E1) laden und prüfen; Name dieses Laufs
python -I tools/run.py draft [--folder <dir>]                   # Entwurfs-Release anlegen, manifest.json zuletzt, Assets prüfen
python -I tools/run.py gate --app <checkout> --old <dir> --new <dir>  # Render-Gate lokal (Windows); im Workflow --old-tag/--new-tag
python -I tools/run.py publish (--tag T | --pending state/pending.json)  # Entwurf prüfen, veröffentlichen, Hygiene, Prune
python -I tools/run.py pr --tag T --dry-run                     # PR-Text nach out/pr-body.md (ohne --dry-run: Branch + PR)
python -I tools/run.py hauling [--saved <dir>] [--previous <dir>]  # Hauling-Templates + Positionen nach work/hauling/ (H1); Fehlschlag = status failed, Exit 0
python -I tools/run.py hauling-pr --dry-run                     # Text des Alias-PR bzw. Issues nach out/ (ohne --dry-run: PR oder Issue)
pytest                                                          # alle Tests (lokal: tools/local-wsl.sh test)
gh workflow run ship-data.yml -f dry-run=true    # Dispatch ohne Release (nur zum Lesen des Logs, Martin klickt)
gh run view --log                                # Log des letzten Laufs
```

Jeder Unterbefehl endet mit drei Zeilen auf dem Bildschirm und in `$GITHUB_STEP_SUMMARY`: **geprüft / gefunden / zu tun**. Logdateien sind Beilage, nie die einzige Quelle.

## Anti-Patterns

| # | Stichwort | Regel |
|---|---|---|
| A1 | **Grep-first** | Vor jeder neuen Funktion, Datei, Regel: `Grep` nach Name und Zweck in diesem Repo **und** in `..\sc-ship-outlines`. Treffer ⇒ Ist-Zustand melden und stoppen. |
| A3 | Confident Hallucination | Actions-Syntax, `gh`-Flags, numpy/cv2/meshoptimizer-APIs **gegen aktuelle Doku prüfen**, Quelle als Kommentar. |
| A4 | YAGNI | Kleinste lauffähige Version zuerst. Keine Abstraktion „für später“, kein Plugin-System für Quellen. |
| A5 | Sycophancy | Jede Architekturentscheidung mit mindestens einem Gegenargument. |
| A6 | Defensiv nur an Grenzen | Grenzen: API-Antwort, Seite, Modell-Datei, Release-Assets, Env. Innen validierte Datenklassen. |
| A7 | Plan-Mode-Stopp | **Jeder** Task: erst Plan, dann wörtliche „Freigabe“. |
| A8 | Stille Annahmen | Fragen statt raten. |
| A11 | **Fremdquelle mit Exit-Plan** | Motherlode ist Fremdquelle ohne Vertrag: letzter Stand bleibt gültig, kein Lauf darf einen gültigen Stand zerstören. |
| A15 | **Handschritt im Lauf** | Ein Schritt, der Martin braucht (Datei kopieren, Befehl tippen, Wert eintragen), ist ein Befund gegen die Pipeline, kein Arbeitsauftrag. Ausnahmen: Dispatch, Approve, Merge, Secrets. |
| A16 | **Stumme Stufe** | Eine Stufe ohne „geprüft / gefunden / zu tun“ ist nicht fertig. Exit 0 mit Fehlern im Log ist ein Fehler. |
| A17 | **CIG-Material im Git** | Kataloge, Modelle, Bilder, Holos, PDFs nie committen, nie in öffentliche Artefakte – nur Cache und Release-Asset. Vor jedem Commit `git status` auf Binärdateien prüfen. |

## NIEMALS

- `except: pass` oder `except Exception` ohne Log und Re-raise
- die Motherlode-API mehr als einmal pro Lauf rufen; Retry-Schleifen gegen Sciirofs Server
- Zustand in Dateien, die nur lokal existieren (Zähler, Hashes, „zuletzt gesehen“) – gehört ins Manifest oder nach `state/`
- Pfade mit Backslash, `.venv\Scripts`, `powershell` statt `pwsh` – die Kette läuft auf Linux
- ein Release ohne grünes Gate; ein Gate, das Martin „am Bild prüfen“ lässt
- `print` ohne Zusammenfassungszeile; `TODO` ohne Issue-Nummer
- Secrets in Logs, Artefakten oder Step-Summaries

## IMMER

- Python mit `-I`, Typannotationen, `pathlib`, `subprocess.run(check=True)`
- Externe APIs gegen aktuelle Doku verifiziert (A3)
- Entscheidungen mit Alternativen in `docs/decisions.md` (SD-Nummern), je 5–10 Zeilen: Kontext, Entscheidung, Gegenargument, Konsequenz
- Jede Regel aus der Tabelle hat einen Test, der einmal provoziert rot war

## Kommunikation mit Martin

- Deutsch, prägnant, Markdown mit fetten Schlüsselbegriffen, Trade-offs statt nur Lösungen
- Lage in einfachen Worten zuerst (wo stehen wir, warum), dann genau **ein** nächster Schritt – keine Kaskaden aus Teilschritten
- Niemals ungefragt Stack-Wechsel vorschlagen (anderer Runner, anderer CI-Dienst, andere Sprache)

## Definition of Done (jeder Task)

1. Akzeptanzkriterien aus `TASKS.md` erfüllt und einzeln vorgeführt – bei Workflows mit Link auf den Lauf.
2. Unmittelbar vor der Fertig-Meldung `pytest tests` komplett und die Zusammenfassung wörtlich zitiert; bei Workflow-Tasks zusätzlich `gh run view` des letzten Laufs.
3. Zahlen in `TASKS.md` (Laufzeit, Größen, Abweichungen), nicht nur „läuft“.
4. Martin hat jede neue Datei einmal erklärt bekommen (Zweck, Kernidee).
5. Task in `TASKS.md` auf `[x]`, Commit mit Task-Prefix, englische Message, kein `Co-Authored-By`.
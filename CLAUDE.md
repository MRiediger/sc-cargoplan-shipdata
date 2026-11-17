# SC-CargoPlan Ship Data

Datenpipeline für [SC-CargoPlan](https://github.com/MRiediger/sc-cargoplan): Frachtgitter, Umrisse und Hologramm-Meshes aller Star-Citizen-Schiffe, monatlich von GitHub Actions gebaut und als Data-Release `ships-YYYY.MM[.N]` veröffentlicht. Die App holt sich den Stand selbst.
**Ziel: läuft ohne Martin.** Ein Lauf endet mit nichts, einem Release oder einem PR – nie mit einer Aufgabe für einen Menschen.

## Wer hier arbeitet

Martin, 20+ Jahre IT (PowerShell, M365, Power Platform, Netzwerk). Python ist Lernfeld, PowerShell-Hintergrund hilft. Will den Code verstehen, nicht nur ausführen.

## Rollen (verbindlich)

- **Claude Code** plant und baut. Ein Task pro Session.
- **Claude.ai** reviewt jeden Plan im Master-Chat „SC-CargoPlan | Phase 12“: Freigabe oder `korrektur-<Task>.md` im Repo-Ordner.
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
  2  Diff gegen das letzte Data-Release: neu / geändert / verschwunden
  3  kein Unterschied → kein Release; Lebenszeichen-Commit `state/last-run.json`
  4  Racks, Holos (nur geänderte Modelle), Umrisse, Anker – ein Lauf
  5  Regressions-Gate (windows-latest): Checkout sc-cargoplan auf gepinntem Tag,
     alter und neuer Datenstand im selben Job gerendert (ShipPictureTests),
     nur geänderte Schiffe dürfen abweichen
  6  grün → Data-Release ships-YYYY.MM (ships/, outlines.json, Holos, manifest.json, NOTICE)
     Regel feuert → PR mit Befund + Kontaktabzug; Martins Merge = Freigabe → Release
App: liest …/releases/latest/download/manifest.json, lädt ships/ + outlines.json + manifest.json,
     Holos lazy pro Schiff aus dem Manifest. release.yml der App zieht beim Build die Baseline ins ZIP.
```

**Regeln als Code** (jede mit Test):

| Fall | Regel |
|---|---|
| Judge-Fail (z. B. Hausdorff) | nur bei Verschlechterung: neu gebautes Holo `passed=false` und im letzten Release `passed=true`, neu oder mit neuem Modell → kein Auto-Release, PR mit Metriken und Bild; > 110 % Budget immer. Mit `passed=false` veröffentlichte Schiffe (holo-v3: 22, Kontaktabzug) feuern bei gleichem Modell nicht (T12.1, P9) |
| Schiff aus dem Katalog verschwunden | behalten, letzte Daten + Holo bleiben, `missingSince` im Manifest; nach 3 Läufen Backlog-Zeile |
| Grid ohne Transform | Schiff bleibt auf seinem Stand – Eintrag in `overrides.json`, Hinweis |
| überlappende Grids | nicht schreiben → PR |
| Doppel-Modell nach Fetch | der Fetch räumt alte Hashes selbst weg |
| neues Schiff | `modelKey` aus der Map, Anker aus dem Modell – kein Rack-Mitte-Fallback |
| Lauf ohne Änderung | kein Release, aber Lebenszeichen-Commit (GitHub schaltet Cron nach 60 Tagen Repo-Stille ab) |
| Motherlode weg | letzter Datenstand bleibt gültig (A11-Exit-Plan) |

## Domänenfakten

- **Quelle:** Motherlode (Sciirof, cryon.rocks). Katalog per API mit Key; Modell-URLs stehen nicht in der API, sondern auf der Seite `cryon.rocks/ops/cargo` (RSC-Stream, ohne Key); Modelle liegen in einem öffentlichen Supabase-Bucket. Bis Sciirof einen Modell-Endpunkt liefert, bleibt der Seiten-Scraper – mit klarem Fehler und PR, sobald die Seite sich ändert. **Die API einmal pro Lauf rufen, nie in Schleife.** Sciirofs Freigabe für den Monatslauf steht aus.
- **Schiffs-JSON:** Format in `sc-cargoplan/docs/ship-format.md`, `schemaVersion` aktuell 6 (`ShipLoader.SupportedSchemaVersion`; 4 und 5 liest die App noch) (Racks mit `origin`, `grid`, `stackAxis`, optional `rotation`; `modelKey`, `holoOrigin`, `outlineOrigin`). Koordinaten x Bug+, y Backbord+, z oben+, 1 Zelle = 1 SCU = 1,25 m. **Schema-Bump nur zusammen mit einem App-Release.**
- **Umriss:** `outlines.json`, Meter, Ursprung unabhängig vom Rack-Nullpunkt, Zuordnung per `modelKey` (App-D90, D94).
- **Holo:** Format SCH2 (`sc-cargoplan/docs/holo-format.md`), aus dem Motherlode-Modell: Flatten → Cull → Leiter 20k/30k/40k (meshoptimizer) → Export. CIG-Material: nie im Repo, nur Cache und Release-Asset, mit NOTICE; `holo: null` im Manifest ist der Kill-Switch.
- **Anker:** heute in `sc-cargoplan/tools/import-motherlode.ps1`; zieht nach T12.1 hierher.
- **Manifest** (`manifest.json` im Release): `dataVersion`, `schemaVersion`, `builtFrom {motherlode, appTag}`, `files {pfad: sha256}`, `holo {baseUrl, hashes} | null`, `ships {id: {source, missingSince}}`. Zähler und Herkunft je Schiff stehen **hier**, nicht in Extradateien.
- **Lizenz:** Code MIT (`LICENSE`), Daten und Holos unter eigener `NOTICE.md` (CIG-Material, nicht MIT). Katalog, Modelle, Bilder, Erecs PDF nie committen.

## Technische Entscheidungen

| Was | Entscheidung | Warum |
|---|---|---|
| Laufumgebung | **GitHub Actions**, `ubuntu-24.04` für die Kette (gepinnt: Python 3.14.5 gibt es für 26.04 = `ubuntu-latest` nicht, S12.0), `windows-latest` nur fürs Render-Gate | Kein eigener Server; Windows nur, wo WPF rendert. Kein Pin fürs Gate nötig: beide Stände entstehen im selben Job (S12.0 K1). |
| Kette | **Python** (numpy, opencv-python-headless) + **Node** (meshoptimizer WASM) + **pwsh** für Anker/Import, ein Einstieg `run.py` mit Unterbefehlen `fetch · diff · build · verify · release` | Bestehender, bewährter Code aus `sc-ship-outlines`; kein Blender, keine GPU, kein Display. |
| Pins | alles in `TOOLS.md`, Versionen exakt; `setup-python`/`setup-node` lesen daraus | Lokal = CI nur mit denselben Versionen; Abweichung ist ein Befund. |
| Gate | **beide Stände im selben Job rendern**, Hash-exakt (`ShipPictureTests`), Schwelle nur für den Judge | Runner- und Plattform-Drift fallen per Konstruktion weg (S12.0 K1). |
| Zustand | Manifest im Release + `state/last-run.json` im Repo | Kein Zustand in Dateien, die nur lokal existieren. |
| Releases | **Pre-Release-Flag aus**, `releases/latest` ist immer das letzte Data-Release; letzte zwei bleiben | Die App braucht genau eine URL ohne API. |
| PR-Pfad | `GITHUB_TOKEN`; CI auf dem PR startet erst nach Martins „Approve workflows to run“ | Kein PAT, solange zwei Klicks reichen. |
| Lizenz | Code MIT, Daten NOTICE | Maximale Verbreitung des Codes, Rückziehbarkeit der Daten. |

## Projektstruktur (Soll)

```
sc-cargoplan-shipdata/
├── CLAUDE.md · TASKS.md · TOOLS.md · README.md · LICENSE · NOTICE.md · SECURITY.md
├── .github/workflows/
│   ├── spike.yml                  # S12.0, wird nach T12.2 gelöscht
│   └── ship-data.yml              # Monatslauf + Dispatch
├── tools/
│   ├── run.py                     # Einstieg: fetch · diff · build · verify · release
│   ├── shipdata/                  # Python-Paket: fetch, diff, rules, manifest, holo_mesh, outline, compare
│   ├── simplify.mjs               # meshoptimizer-Leiter
│   ├── import-motherlode.ps1 · ShipJson.ps1   # Racks + Anker (aus dem App-Repo gezogen, T12.1)
│   ├── requirements.txt · package.json · package-lock.json
├── overrides.json                 # Schiffe, die auf einem alten Stand bleiben (Grid ohne Transform)
├── state/last-run.json            # Lebenszeichen + Zusammenfassung des letzten Laufs
├── tests/                         # pytest: Regeln, Diff, Manifest, Vergleich; Fixtures klein und synthetisch
└── docs/
    ├── decisions.md               # SD1…, nummeriert; App-Entscheidungen bleiben in sc-cargoplan/docs/decisions.md
    ├── plans/                     # ein Plan je Task, bleibt als Geschichte
    └── manifest-format.md
```

Cache (`cache/`), Modelle (`*.glb`), Arbeitsordner, Bilder, PDFs und Kataloge sind gitignort.

## Befehle

```powershell
python -I tools/run.py fetch --catalog-only      # Katalog per API (einmal), Status + SHA im Log
python -I tools/run.py diff                      # Katalog gegen letztes Release: neu / geändert / verschwunden
python -I tools/run.py build --ship <id>         # ein Schiff: Flatten → Leiter → Export → Umriss → Anker
python -I tools/run.py verify                    # Regeln + Manifest + Hashes gegen den Arbeitsstand
python -I tools/run.py release --dry-run         # Release-Inhalt zeigen, nichts hochladen
pytest tests                                     # alle Tests
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
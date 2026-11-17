# TASKS – SC-CargoPlan Ship Data

Regeln: **ein Task pro Session**, Reihenfolge einhalten. Jeder Task hat eine „Warum“-Zeile und prüfbare Akzeptanzkriterien. Jeder Task beginnt mit einem Plan in `docs/plans/` und stoppt bis zur Freigabe aus dem Master-Chat. Erledigt → `[x]`.

Session-Start-Prompt für Claude Code:
> Lies CLAUDE.md und TASKS.md. Wir machen Task **Tx.y**. Fass den Task zusammen, schreib den Plan nach `docs/plans/`, committe, pushe, stopp.

Einstieg der App-Seite: `sc-cargoplan/TASKS.md`, Abschnitt „Phase 12“. Tasks mit Präfix **App:** laufen dort, in diesem Repo steht nur die Schnittstelle.

---

## Phase 12 – Ship data channel (gestartet 16.11.2026)

**Zielbild, Regeln, Manifest:** siehe CLAUDE.md. **Zwei Repos:** dieses baut und veröffentlicht, `sc-cargoplan` liest (App) und zieht die Baseline beim Build (`release.yml`).

**Vorbereitung (Martin, erledigt 17.11.):** Repo öffentlich und leer angelegt, Secret `MOTHERLODE_API_KEY`, Actions „Read and write“ + „create and approve pull requests“. Parallel: Anfrage an Sciirof (Modell-Endpunkt, Erlaubnis Monatslauf, Cyclone, 135c-Transform) – Antwort ausstehend.

### [ ] S12.0 Spike – ein Schiff end-to-end auf Actions (Plan freigegeben 17.11.2026, kein Prod-Code)

**Warum:** Fünf Fragen ändern das Design; sie werden gemessen, bevor T12.1 etwas Dauerhaftes baut.
**Plan:** `docs/plans/S12.0-spike.md`. **Schiff:** ORIG 100i (Fallback Avenger Titan, dann Nomad, aus demselben Katalog). **Branch:** `main`, Workflow `spike.yml` (`workflow_dispatch`), Spike-Code unter `spike/`, wird nach T12.2 gelöscht.

**Fragen:**
1. Kette auf `ubuntu-latest`: Katalog (API, einmal) → Modell → Flatten → Leiter → Export → Umriss → Anker. Laufzeit, Pins, Cache-Größe.
2. Scraper vom Runner: Seite und Modell-URLs erreichbar (Status, Header, Rate-Limit)? Probe nur HEAD, ein GET fürs Spike-Modell.
3. Gate-Job `windows-latest`: Cross-Repo-Checkout `sc-cargoplan@v0.5.1`, `ShipPictureTests` headless. Rendert WPF? Checkout + Test in einem Job?
4. Schwelle: Bildabstand „gleich“ vs. „anders“ (Pixelanteil, Delta > 8, SSIM) über drei Paarklassen.
5. Manifest: welche Felder hat der Spike gebraucht, welche nicht?

**Präzisierung in der Planphase, ratifiziert durch Freigabe (`korrektur-S12.0.md`):**
1. **K1:** gate-b rendert **beide Stände im selben Job** – Run B0 (unverändert v0.5.1 + holo-v3) vor dem Datei-Tausch, Run B mit BASELINE=`b0`; zusätzlich B gegen `a1` (VM↔VM). Sind alle Nicht-100i-Bilder B0↔B hash-gleich, ist das Produktions-Gate Hash-exakt ohne gespeicherte Baseline; die Schwelle bleibt dem Judge.
2. **E1:** `actions/cache` ist für Fork-PR-Workflows lesbar – Befund für T12.2 (Katalog nicht in den Cache oder Fork-Workflows aus).
3. **E2:** Step-Summary weist aus: „1 API call, 1 page GET, n HEAD, 1 model GET“.
4. **E3:** `ships/` und `outlines/` kommen in `ShipPictureTests` aus `bin` ohne Override – als Designfrage (Env-Override im App-Repo vs. Tausch im Checkout) in „Das ändert sich“.
5. Plan auf Englisch (Martins Wunsch), TASKS.md Deutsch.

**Akzeptanz:** Dispatch-Lauf mit allen drei Jobs (grün oder rot mit erklärtem Befund), `compare.py` lokal gelaufen, Abschnitt „S12.0 Befund“ hier mit allen fünf Antworten **als Zahlen** (Sekunden je Stufe, Versionen vs. Pins, Bytes, Hash-Gleichheit n/N, Schwelle mit Lücke, Manifest-Felder gebraucht/überflüssig) und Liste „Das ändert sich am Phasenplan“. Ein zweiter Dispatch zeigt den Cache-Treffer und ruft die API nicht erneut. Martin kann erklären, warum beide Stände im selben Job gerendert werden.

**S12.0 Befund (17.11.2026):** drei Dispatch-Läufe; Lauf 3 [44090875270](https://github.com/MRiediger/sc-cargoplan-shipdata/actions/runs/44090875270) grün (chain 2:38 min, gate-a 8:07, gate-b 9:42). Lauf 1 rot: `ubuntu-latest` ist 26.04, dort gibt es Python 3.14.5 nicht (erst ab 3.14.6). Lauf 2 rot: die Modelle aller Kandidaten waren neu exportiert, der Probe-Code brach ab statt zu messen. Danach Kette als ein Skript (`spike/chain-job.sh`), vor Lauf 3 lokal in WSL Ubuntu 24.04 mit denselben Pins getestet (`spike/local-wsl.sh`). API-Rufe über alle drei Läufe: **1** (Lauf 2); Lauf 3 kam aus dem Cache („0 API, 0 page GET, 101 HEAD, 2 model GET“).

1. **Kette auf Ubuntu – läuft, byte-gleich zu holo-v3.**
   - Runner `ubuntu-24.04` (Image ubuntu24 20261111.370.1), nicht `ubuntu-latest` (s. o.).
   - Versionen = Pins: Python 3.14.5, numpy 2.5.3, opencv-python-headless 5.0.0.93, Node 24.16.0, meshoptimizer 1.3.0; pwsh 7.6.10 vom Image.
   - Setup: setup-python 10 s, setup-node 5 s, pip 5,0 s, npm 0,5 s.
   - 100i (altes Modell `da8168ea3720`), Sekunden je Stufe: Flatten 0,2 · Cull 22,7 · Ref 0,1 · Leiter (1 Stufe, 20 k) 0,1 · Export 3,4 · Umriss 0,2 = **26,7 s**; `fetch-motherlode.ps1` offline 3,9 s; Import 2,8 + 2,4 s; `outlines-v2` 0,2 s. Hochrechnung alle 101 Modelle: lokal (Windows) 59 Schiffe in 2 353 s, Ø 40 s, max 79 s (Ironclad Assault) → **≈ 65–70 min** in einem Job; Cull dominiert.
   - `orig-100i.holo` **byte-gleich** (93 794 B, `f05c9c4f…`), PP-Metriken gleich dem Manifest, `ship-outlines.json` **byte-gleich**. Zusätzlich lokal: `chain.sh` unter Windows (DRAK Cutter) byte-gleich zu `holo-work-ml` – die Bash-Kette ersetzt `decimate.ps1`/`run-all.ps1` ohne Abweichung.
   - Schiffs-JSON **nicht byte-gleich, nur in `source`**: pwsh 7 macht beim `ConvertFrom-Json` aus `updatedAt` ein DateTime → `11/12/2026 20:50:33` statt `2026-11-12T20:50:33.036Z`. Lokal (Archiv 16.11.): 104 Dateien umgeschrieben, 0 über `source` hinaus. Runner (Katalog 17.11.): 99 umgeschrieben, 98 nur `source`, 1 echte Datenänderung (`f7c_hornet_mk_ii`, Rack 1 Zelle verschoben). `ConvertFrom-Json -DateKind String` behebt es in pwsh 7.6.10 (geprüft), existiert aber nicht in Windows PowerShell 5.1.
   - Cache: Katalog-Rohdaten 180 KB (API 72,5 KB + Seite 106,6 KB), Katalog 217,5 KB; alle 101 Modelle **52,0 MB** (größtes 1,52 MB); Arbeitsordner 100i 0,72 MB, lokal `holo-work-ml` 101 Schiffe 370 MB.
   - **Re-Export ohne Build-Wechsel:** Katalog 17.11. (`updatedAt` 16.11. 11:36, Build weiter 4.10.3-LIVE.13165946) – alle 3 geprüften Kandidaten mit neuem Modell-Hash. 100i neu (`f982f2636804`, 85 160 statt 89 036 B): Holo 6 693 statt 6 699 Dreiecke (93 662 B), Umriss gleich, 8 Bilder des 100i anders.
   - **Katalog 17.11.:** 101 statt 105 Schiffe. Abwesend: 600i Executive Edition, Carrack w/ C8X, Carrack Expedition w/ C8X, Cyclone, MOLE Carbon, MOLE Talus, Mustang Alpha Vindicator, Valkyrie Liberator Edition. Neu: `hyun` (32 SCU, ohne `-Create` nicht geschrieben). Import Exit 1.
2. **Scraper vom Runner – kein Block, kein Rate-Limit.**
   - API: HTTP 200 in 0,58 s, 72 542 B, Vercel (`x-vercel-cache: BYPASS`), keine Rate-Limit-Header.
   - Seite `/ops/cargo`: HTTP 200 in 0,63 s, 106 589 B, `"ships"`-Array gefunden, Vercel, keine Rate-Limit-Header.
   - Modell-Bucket (Supabase hinter Cloudflare): 101 HEAD → **101 × 200**, p50 264 ms, max 711 ms (Lauf 2: 207/1 475 ms); `CF-Cache-Status: DYNAMIC`, `Cache-Control: private, no-cache`; kein 403/429. 2 Modell-GET je 200 in 1,3/1,5 s.
3. **Gate auf `windows-latest` – rendert, Cross-Repo + zwei Läufe + Tausch in einem Job funktionieren.**
   - Image win25-vs2026 20261103.298.1, SDK 10.0.404; 1 427 Bilder je Lauf.
   - Dauer: Build 34–62 s, A1 (ohne Baseline, alle PNG) 206 s, B0 271 s, B (mit Baseline) 139 s, Tausch + Rebuild 3,4 s (bin-Kopie geprüft); setup-dotnet 30 s, setup-python 46 s (nur für `csvdiff.py`).
   - **B0↔B (K1, selbe VM, alter gegen neuen Stand): 1 414 / 1 414 ohne 100i gleich, Placement 108 / 108**; der 100i selbst ebenfalls gleich (0 abweichende Bilder) → 1 427 / 1 427.
   - VM↔VM A1↔B0: 1 427 / 1 427, Placement 109 / 109. Lokal (Martins Windows 11) ↔ Runner A1: **1 427 / 1 427**.
   - Artifact aller PNG: 105,8 MB, Upload 14 s.
4. **Schwelle – fürs Gate 0 (hash-exakt); SSIM ungeeignet.**
   - Methode (`spike/compare.py`, lokal): Anteil abweichender Pixel (wie `ViewPictures.Difference`), Anteil mit Kanal-Δ > 8, SSIM (Grau, Gauß 11 × 11, σ 1,5).
   - „Gleich“ (drei Klassen: lokal↔Runner, VM↔VM, selbe VM alt↔neu ohne Änderung): **Abstand 0**, alle hash-gleich.
   - „Anders“, holo-v2↔v3 (96 Paare, 12 Schiffe): Pixelanteil min **8,3 · 10⁻⁵** (≈ 10 Pixel), Median 1,2 · 10⁻³, max 0,24; SSIM min 0,845, max **0,999998**.
   - „Anders“, Re-Export 100i (8 Paare, lokal gerendert): Pixelanteil 2,9 · 10⁻⁴ … 3,0 · 10⁻³, Δ > 8 1,7 · 10⁻⁴ … 3,5 · 10⁻⁴, SSIM 0,99953 … 0,999985.
   - **Lücke: 0 gegen 8,3 · 10⁻⁵.** Gate = Hash-Vergleich; jede Abweichung ist „anders“. SSIM trennt erst in der 6. Nachkommastelle. Für den Judge („wie stark?“) taugt der Pixelanteil.
5. **Manifest – gebraucht / fehlt / überflüssig.**
   - Gebraucht und im Entwurf: `appTag` (Gate-Checkout), `ships.<id>.source` und `missingSince` (8 Schiffe abwesend, 135c/F7C/600i Exec ohne Modell-Anker).
   - **Fehlt:** `ships.<id>.model {className, sha256}` – Wahl des Modells, Cache-Schlüssel, Erkennung des Re-Exports; `builtFrom.motherlode` als vollständiger Build **plus** Katalog-`updatedAt` (der Re-Export kam ohne Build-Wechsel); `builtFrom.tools` (Byte-Gleichheit hängt an den Pins); `holo.formatVersion` (die App prüft 2); je Holo `bytes` **und** `sha256` (die App prüft beides).
   - **Korrektur:** `schemaVersion` der Schiffs-JSON ist **6**, nicht 4 (`ShipLoader.SupportedSchemaVersion`).
   - Nicht gebraucht: Runner-`ImageVersion` (Hashes sind maschinenübergreifend gleich, Baseline entsteht im selben Job); eine Bild-Schwelle; Katalog-SHA (wechselt mit jedem Abruf: 16.11. `84cb4a7d…`, 17.11. `d4b285d1…`, taugt nicht als Änderungssignal). `holo.baseUrl` nicht geprüft (App-Seite, T12.4).

**Das ändert sich am Phasenplan:**
1. **Gate:** hash-exakt, beide Stände im selben Job, keine gespeicherte Baseline, kein Toleranzmodus. Das Phasen-Gate „Umrisse und Holos per Bildvergleich mit Schwelle“ wird **„byte-gleich“** – Ubuntu erzeugt Holo und Umriss bitgleich zu Windows. T12.1-Akzeptanz „unter der S12.0-Schwelle“ → „byte-gleich zu holo-v3“.
2. **Runner-Pin:** `ubuntu-24.04` statt `ubuntu-latest`, oder Python-Pin auf ≥ 3.14.6 (dann neu gegen holo-v3 messen). Entscheidung in T12.0; `CLAUDE.md` nennt heute `ubuntu-latest`.
3. **Änderungserkennung nach Modell-SHA, nicht nach Build:** Motherlode exportiert ohne Build-Wechsel neu, und das Holo ändert sich dann wirklich. Ein Re-Export aller Modelle heißt ≈ 65–70 min Kette → T12.2 plant Laufzeit (ggf. Matrix). Der Judge braucht eine Regel für kleine Änderungen (Pixelanteil 10⁻⁴ … 10⁻³): Release oder PR.
4. **Import-Datum:** beim Umzug nach T12.1 `updatedAt` als String übernehmen (`-DateKind String` unter pwsh 7, oder Python). Bis dahin erzeugt jeder Linux-Import 99+ Scheinänderungen.
5. **Erster echter Lauf trifft sofort die Regeln** „verschwunden“ (8 Schiffe) und „neues Schiff“ (`hyun`) sowie eine Rack-Änderung (F7C). Frage an Sciirof: Sind die Varianten absichtlich entfernt?
6. **Anker-Umzug machbar:** `import-motherlode.ps1` läuft unter pwsh auf Linux unverändert bis aufs Datum; `decimate.ps1`/`run-all.ps1` entfallen.
7. **E1:** `actions/cache` ist für Fork-PR-Workflows lesbar → den Katalog in T12.2 nicht cachen, oder Fork-Workflows abschalten.
8. **E3:** Der Tausch im Checkout funktioniert (3,4 s inkl. Rebuild), hängt aber an `CopyToOutputDirectory` → Env-Override in `ShipPictureTests` (T12.5) bleibt vorzuziehen.
9. **Gate-Laufzeit ≈ 10 min** pro Job mit zwei Bildläufen; `setup-python` auf Windows (46 s) in T12.2 weglassen.
10. **Lokaler Test vor dem Runner:** `spike/local-wsl.sh` fand die Datumsabweichung vor dem Runner-Lauf. Muster für T12.1: `run.py` erst in WSL Ubuntu 24.04, dann im Workflow.

### [ ] T12.0 Doku

**Warum:** Zwei Repos brauchen einen gemeinsamen Vertrag, bevor Code entsteht; die Spike-Befunde müssen in den Plan.
- `docs/decisions.md` hier: SD1 „Zwei Repos“ (Kontext, Gegenargument: zwei Arbeitsordner, Cross-Repo-Gate), SD2 Manifest-Format, SD3 Gate-Verfahren aus S12.0, SD4 Release-Reihe `ships-YYYY.MM[.N]`, Pre-Release aus, letzte zwei bleiben
- `docs/manifest-format.md` (Felder aus S12.0 Frage 5, `schemaVersion`-Vertrag, `holo: null`)
- `TOOLS.md` bereinigt, Pins aus dem Spike bestätigt
- **App:** D-Eintrag (nächste freie Nummer) „Ship data channel“ mit Zielbild, Verweis auf SD1–SD4; Phase-12-Abschnitt in `sc-cargoplan/TASKS.md` mit T12.3–T12.6; Kollision „P12 Look“ auflösen
- Spike-Befunde in diesen Task-Schnitt einarbeiten (Reihenfolge, Gates, Anker-Umzug)

**Akzeptanz:** Freigabe aus dem Master-Chat; beide Repos zeigen dieselbe Task-Nummerierung und denselben Manifest-Vertrag.

### [ ] T12.1 Pipeline – `run.py fetch · diff · build · verify · release`

**Warum:** Vier Skripte in zwei Repos werden ein Einstieg mit Regeln als Code; das ist die Hälfte des v0.5.1-Handlaufs.
- Portierung aus `sc-ship-outlines` (Motherlode-Kette, nicht `legacy/`) und `sc-cargoplan/tools/import-motherlode.ps1` + `ShipJson.ps1` (Anker); Windows-Annahmen raus (`decimate.ps1`, `run-all.ps1` entfallen); vor dem Kopieren Secrets-Scan
- `fetch`: Katalog einmal per API, Modelle nach SHA, alte Hashes aufräumen (Regel „Doppel-Modell“)
- `diff`: gegen das Manifest des letzten Releases: neu / geändert / verschwunden
- `build`: nur geänderte Modelle; Umriss, Anker; `-Create`-Fix (`modelKey` aus der Map)
- `verify`: Regeln aus der Tabelle (Judge, verschwunden → `missingSince`, Transform → `overrides.json`, Überlappung → Stopp), Manifest-Schreiber, Hashes
- `release`: Asset-Liste, NOTICE, `--dry-run`
- Jede Stufe: geprüft / gefunden / zu tun; `pytest` für jede Regel, einmal provoziert rot
- `LICENSE` (MIT), `NOTICE.md` (Daten), README

**Akzeptanz:** Lokal ein voller Lauf gegen den Katalog 4.10.3: `ships/` **byteidentisch** zu `sc-cargoplan@main`, Umrisse und Holos **unter der S12.0-Schwelle** gegen holo-v3; `verify` meldet Cyclone als `missingSince` und 135c aus `overrides.json`; Tests grün. Martin kann die fünf Unterbefehle und ihre Übergaben nennen.

### [ ] T12.2 Workflow `ship-data.yml`

**Warum:** Der Lauf ohne Martin. Alles, was heute Zuruf ist, steht danach im YAML oder in `run.py`.
- cron `23 4 1 * *` + `workflow_dispatch` (Input `dry-run`), `permissions: contents: write, pull-requests: write`
- Cache nach Modell-SHA (Katalog nicht im Cache, S12.0 E1), Secret nur im Fetch-Step
- Diff → kein Unterschied: Lebenszeichen-Commit `state/last-run.json`, Ende
- Gate-Job `windows-latest`: Checkout `sc-cargoplan` auf gepinntem Tag (in `TOOLS.md`), beide Stände im selben Job (S12.0 K1)
- Release-Pfad: `gh release create ships-YYYY.MM[.N]`, Assets, Hygiene (letzte zwei bleiben)
- PR-Pfad: Branch `data/YYYY.MM`, Befund als PR-Text, Kontaktabzug als Artefakt; nach Merge Release aus dem Merge-Commit
- `spike.yml` und `spike/` löschen

**Akzeptanz:** Dispatch ohne Änderung: grün, „nothing changed“, ein Commit in `state/`, kein Release. Dispatch mit provozierter Regel (Test-Override): PR mit Befund und Artefakt, kein Release. Dispatch mit provozierter Änderung an einem Schiff: Release `ships-2026.11-test` mit vollständigem Manifest, danach gelöscht. Martin hat drei Knöpfe gedrückt und keinen Befehl getippt.

### [ ] T12.3 App: Datenkanal (im App-Repo)

**Warum:** Ohne Leser ist das Release wertlos.
- Manifest-Check nach dem Velopack-Check (eine URL `…/releases/latest/download/manifest.json`), `schemaVersion`-Prüfung (unbekannt → „Ship data needs app update“)
- Notice-Zeile mit Update/Skip, Download nur `ships/` + `outlines.json` + `manifest.json`, atomarer Tausch unter `%LocalAppData%\SC-CargoPlan\ships\<version>\`, Reload ohne Neustart
- Plan-Verträglichkeit: geänderter Rack-Satz → „re-plan recommended“
- Settings „Ship data“ (`shipData.checkOnStartup`, `skippedVersion`), CLI `ships --version`
- Netzzugriff 3 → eigener D-Eintrag (CLAUDE.md der App)

**Akzeptanz:** Gate am Aufzug, SC im Vordergrund: Update einspielen, Galaxy erscheint, Holo lädt, Plan bleibt.

### [ ] T12.4 App: Holo aus dem Manifest (im App-Repo)

**Warum:** `HoloRelease.Tag` ist die letzte Konstante, die ein App-Release pro Datenänderung erzwingt.
- Ort und Hashes aus dem Manifest, `holo: null` → Umriss-Fallback, gelöschtes Release → Baseline-Holo
- Cache-Wechsel nach D95-Muster, Migration für v0.5.x-Caches

**Akzeptanz:** Bildvergleich gegen holo-v3 unter der Schwelle; Holo-Download aus `ships-*` statt `holo-v3`.

### [ ] T12.5 App: Baseline aus dem Release (im App-Repo)

**Warum:** Eine Quelle für Schiffsdaten; `ships/` als Quelltext im App-Repo ist der zweite Pfad, der v0.5.1 teuer machte.
- `release.yml` lädt das aktuelle `ships-*`-Release ins ZIP, Tag im Manifest; `ci.yml` gegen eine feste Baseline
- `ships/`, `outlines/`, `tools/import-motherlode.ps1`, `ShipJson.ps1` raus; `ShipPictureTests` liest Daten per Env-Override (S12.0 E3)
- NOTICE und README anpassen

**Akzeptanz:** Publish-Build lokal startet offline mit der Baseline; `git ls-files ships/` ist leer.

### [ ] T12.6 Release

**Warum:** Erst ein echtes Data-Release, dann die App, die es liest, dann der erste Monatslauf.
- Erstes Data-Release `ships-2026.11` per Knopf (= Stand 4.10.3 / holo-v3)
- **App:** v0.6.0 mit dieser Baseline, Wiki (Installation, Ships), README beider Repos, Notes
- `sc-ship-outlines` archivieren; `holo-v3` im App-Repo bleibt bis v0.5.x ausgelaufen ist
- Danach: erster echter Monatslauf per Knopf

**Akzeptanz:** Netz-Gate, SC im Vordergrund: v0.5.1 → v0.6.0 per Velopack, dann Data-Update im Overlay. Ab hier Branch + `--no-ff` für jede Änderung an diesem Repo.

---

## Lehren

Regeln aus Fehlern, die durchgerutscht sind. Gelten für jeden Task. Übernommen aus `sc-cargoplan`, soweit sie hier treffen.

- **Vor jedem Push `gh run list -L 3`.** Rote Läufe erst klären, dann pushen.
- **Tests vor der Implementierung heißt: erst rot sehen.**
- **Mess- und Gate-Befehle selbst einmal laufen lassen, bevor Martin sie bekommt.** Hier: jeden Workflow einmal per Dispatch selbst lesen, bevor er als fertig gilt.
- **Fremd-Framework zuerst als Spike mit Gates am echten Layout** (S11.0). Hier: S12.0 vor jedem Prod-Code.
- **Bei fremden CLIs heißt „leer“ oft „nicht gesetzt“.** Gilt für `gh`, `actions/cache`, `setup-python`.
- **Ein Skript für lokal und CI.** `run.py` ist der einzige Einstieg; `ship-data.yml` ruft nur Unterbefehle.
- **Handlauf ist ein Befund.** Anlass v0.5.1: ein halber Tag für drei Schiffe. Jeder Schritt, der einen Menschen braucht, bekommt eine Zeile hier, bis er weg ist.
- **Kein Startprompt ohne Regeln.** Anlass 17.11.: Die erste CC-Session in diesem Repo lief ohne CLAUDE.md und TASKS.md und hat sich ihre Regeln selbst gegeben. Jedes neue Repo bekommt beide Dateien **vor** der ersten Session.
- **Keine Logik in YAML-Schritten.** Anlass 17.11. (S12.0): zwei rote Läufe – ein ungepinntes Runner-Image und Inline-Code, der vor dem Runner nie gelaufen war. Workflow-Schritte rufen Skripte; die Skripte laufen vorher lokal in WSL Ubuntu 24.04 mit denselben Pins.

---

## Backlog (nur bei Bedarf)

Kein Plan, sondern Reaktion: wird erst zum Task, wenn der Anlass eintritt.

- **Sciirof liefert einen Modell-Endpunkt** → Scraper raus, `fetch` liest URLs aus der API (SD-Eintrag).
- **Sciirof lehnt den Monatslauf ab** → Cadence auf Dispatch-only, Martin drückt den Knopf; Zielbild bleibt.
- **Seite `cryon.rocks/ops/cargo` ändert sich** → Pipeline meldet PR „model URLs unavailable“, letzter Stand bleibt (A11).
- **Ein Schiff > 3 Läufe `missingSince`** → Zeile hier, Entscheidung Martin: behalten oder aus dem Manifest nehmen.
- **PAT für den PR-Pfad**, falls „Approve workflows to run“ bei jedem PR stört.
- **Holo-Kill-Switch** (CIG oder Sciirof sagt Stopp): `holo: null` im nächsten Release, Assets der letzten zwei Releases löschen.
- **Legenden-Warnzeilen** aus v0.5.1 – App-Thema, nicht hier (Verweis).
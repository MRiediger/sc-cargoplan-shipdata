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
# H1 Hauling-Job – Plan

Repo: `sc-cargoplan-shipdata` (`..\sc-cargoplan-shipdata`), Branch **`feat/h1-hauling`** ab `main` `49c0250` (Repo ist produktiv → Branch + `--no-ff`, CLAUDE.md).
**Ablauf dieser Session:** Plan (mit Freigabe-Abschnitt) 1:1 nach `docs/plans/H1-hauling.md`, Commit `H1: plan` (ohne `Co-Authored-By`), `gh run list -L 3`, Push des Branches, dann Umsetzung Block für Block.

## Freigabe (Master-Chat, 21.11.2026)

**Freigabe H1 mit K1–K3, E1.** R1: V1, V2, V3, V4, V6, V8 wie vorgeschlagen; V5 → K2, V7 → K3, L1 → K1. R2 ja. R3 ja. R4 ja. R5 ja (194 / 201). R6 ja.
- **K1 (ersetzt L1):** `positions[].name` = **Starmap-Name**, eindeutig je System; neues optionales Feld **`positions[].contractNames[]`** = alle Vertragsformen aus der Alias-Tabelle; **Pools tragen den aufgelösten Starmap-Namen**. Mehrere Vertragsnamen auf eine `uuid` → eine Position mit mehreren `contractNames`. Grund: Der Scan liest die Objective-Zeile; in Stanton ist das der Starmap-Name (110/110), für Pyro unbekannt → beide Formen vorhalten.
- **K2 (V5):** Loader-Regel nur `len(legs) ≥ 1`. Die Formel `min(stops × Waren, 4)` ist ein Changelog-Hinweis der Pipeline, keine Loader-Regel.
- **K3 (V7):** `name` eindeutig **je System** statt je Datei (Gateways bleiben in beiden Systemen). Kollision im System → Hinweis, der erste gewinnt.
- **E1:** `hauling-pr` feuert auf **jedes** `status: failed`, nicht nur auf Alias-Lücken. Lücke → Alias-Vorschlag auf `data/hauling-aliases`; sonst Fehlerbericht ohne Dateiänderung (Issue, weil ein PR ohne Diff nicht geht). Grund: „Vorgänger weitertragen“ darf nicht monatelang still bleiben.
- Die Addenda für `hauling-data-format.md` (V1–V4, V6, V8, K1–K3, Star im Positions-Filter) kommen per App-Session als Doku-Commit; **H1 baut die Verify-Tests gegen diese Fassung**. Der Befund „74 systemweite Stellar-Pools leer, Hubs in keinem Pool“ bleibt als Zeile für T13.3 in den Befunden.

## Auftrag in einem Absatz

Der Monatslauf `ship-data.yml` bekommt einen Hauling-Teil: Er holt die Hauling-Templates und die Starmap-Positionen, normalisiert sie nach dem App-Vertrag `sc-cargoplan/docs/hauling-data-format.md` (Schema 1) zu `hauling-templates.json` und `positions.json`, prüft sie (die Loader-Checks der App als Tests), diffed gegen das letzte Release (Changelog) und legt beide als flache Assets ins Data-Release, beschrieben im Manifest-Abschnitt `hauling`. **K2 absolut:** ein gescheiterter Hauling-Teil blockiert nie das Schiffsrelease. Ein Hauling-Diff allein löst ein Release aus. Unaufgelöste Ortsnamen gehen als PR an die Alias-Tabelle. Entscheidung **SD14**, Addendum SD2, `manifest-format.md` wortgleich zum Vertrag. Übergabepunkt: ein Data-Release mit `hauling` für App-T13.3.

## Kontext: was die Erkundung ergeben hat

**Pipeline (Ist, `49c0250`):**
- Datenfluss zwischen Jobs nur über das Entwurfs-Release (SD10); Artefakte tragen nur Berichte, nie CIG-Material.
- `stages.diff_stage` setzt `changed`; ohne Änderung fallen build/verify/draft/gate/publish weg (`stages.py:152`, `workflow.outcome` `workflow.py:310`).
- `build_stage` mit 0 geänderten Modellen baut nichts, behält alle Umrisse, läuft nur den Import (`stages.py:192-228`); `verify_stage` kopiert Holos des Vorgängers byte-gleich und schreibt das Manifest (`stages.py:313-362`).
- **Zwei Blocker für neue Assets:** `workflow.expected_assets`/`draft_problems` (`workflow.py:65-91`) lehnen jedes nicht gelistete Asset ab; `manifest.data_files` (`manifest.py:24-27`) zöge Dateien im Stage-Wurzelordner in `files` und `ships.zip`.
- `manifest.REQUIRED` (`manifest.py:12`): `hauling` muss beim Lesen optional bleiben (`ships-2026.11.1` hat keins).
- `previous_stage` lädt **alle** Assets des Vorgängers (`workflow.py:124-153`) → Weitertragen ist eine Kopie.
- `tests/test_workflow.py`: `secrets.` genau einmal; jede `run:`-Zeile beginnt mit `python -I tools/run.py …`; Artefaktpfade ohne `raw`, `ships`, `stage`, `cache` …; jeder Job eigene `permissions:`.
- HTTP nur stdlib `urllib`; 171 Tests (`171 passed in 53.74s`, T12.6b). Kein „hauling“ im Repo.

**S-H0 (Spike, 21.11., nur gelesen):** `StarCitizenWiki/scunpacked-data`, `master` = `f182b7f` (13.11.2026, Message „4.10.3-LIVE.13165946“).
- `contracts/` = 5.166 Dateien `<uuid>.json`, 235 MB; **1.843 / 1.843** UUIDs von Martins Dump vorhanden, 0 fehlen.
- Feldvergleich über alle 1.843: `debug_name`, `mission_type`, `reward_min/max`, `not_for_release`, **`mission_tokens` identisch**; `hauling_orders` identisch mit einer Regel der API (roh `MaxScu = 0` → API `max_scu = MinScu`, `min_scu = null`); Titel = `DisplayTitle`; `released` = `!NotForRelease` ohne Ausnahme.
- Rohfelder: `UUID, DebugName, DisplayTitle, NotForRelease, WorkInProgress, MissionGiver, MissionType.Name, FixedReward.Amount, HaulingOrders[].{Name, MinScu, MaxScu, MaxContainerSize}, MissionTokens` (zusätzlich Tokens `ReputationRank`, `CargoGradeToken`). `entry_type` taugt nicht als Filter (released Templates sind auch `legacy`).
- Kein Build-Feld je Datei; Build nur aus der Commit-Message.
- `starmap_positions.json` im **selben Commit** (465.827 B, 1.804 Einträge): Everus → HUR-L1 **1,289 Gm**, Everus → Baijini **22,882 Gm**.
- Repo-Tarball gestreamt ≈ 28 s lokal (1,54 GB entpackt, nichts auf Platte).
- Wiki-API: keine Rate-Limit-Header, **kein Zeitstempel je Mission** (Liste nur `version`, Detail nur `meta.processed_at` = Verarbeitungszeit).

**Dump-Analyse (Martins Dump, 4.10.3):**
- **89 reproduziert** (Covalex released, Stellar, Geo ∈ {Stanton, Stanton1}, Rang ≤ Senior: 68 + **21** Stanton1).
- **208 nicht** über den Vertragsfilter: `RedWind_Pyro_*` released = **194**; 208 = Auftraggeber „Red Wind Linehaul“ = 194 + 7 `HaulCargo_*_Interstellar` + 7 `Redwind_*`.
- Ortsnamen in Pools: 176 verschieden, **110 exakt** in der Starmap, **66 nicht** (10 Pyro-Langformen, 3 Umbenennungen, 9 „Ort in Parent“, 10 „<Körper> Derelict Outpost“, 2 mehrdeutig, 7 nicht in der Starmap, 4 Oberflächen/Höhlen, 21 Platzhaltertexte wie „Lobby“). Stellar-Scope allein: nur die 10 Pyro-Langformen + Müll aus 3 kaputten Covalex-Templates.
- Gateways heißen in zwei Systemen gleich (Pyro/Stanton/Nyx Gateway); „Derelict Outpost“ 19 × (Pyro, hidden), „Asteroid Mining Base“ 97 × (Nyx).
- **Alle 74 systemweiten Covalex-Stellar-Templates (`Stanton`) haben einen leeren Drop-off-Pool; die vier LEO-Hubs stehen in keinem Stellar-Pool** → Befund für T13.3 (nicht H1).

## Vertragsbefunde – brauchen ein Addendum über den Reviewer (App-Seite ändere ich nicht)

Die echten Daten widersprechen `hauling-data-format.md` an acht Stellen. Vorschlag jeweils **fett**:

| # | Befund (Zahl) | Vertrag heute | Vorschlag |
|---|---|---|---|
| V1 | Quelle wird Rohrepo statt API | `source.api` Pflicht im Templates-Kopf | **Templates-Kopf wie Positionen: `source.repository`, `source.commit`, `source.gameBuild`, `source.fetchedAt`** (Loader prüft `source` nicht, App unberührt) |
| V2 | Rang **Trainee**: 259 Covalex + 40 Red Wind | Enum ohne `trainee` | **`trainee` als erster Rang** |
| V3 | Größenwörter **„Extra Small“** und **„Bulk“** | `xs`, `small`, `medium`, `large`; unbekanntes Wort stoppt | **„Extra Small“ → `xs`; `bulk` als neuer Wert nach `large`** (Titel sagt Bulk, der Scan liest den Titel) |
| V4 | 22 `HaulCargo_*` gehören nicht Covalex (8 Dead Saints, 7 Ling, 7 Red Wind) | Auftraggeber aus dem Präfix | **`contractor` aus `MissionGiver`, Namensschema nur zum Zerlegen**; andere Auftraggeber raus |
| V5 | Leg-Anzahl ≠ Stopps: AToB nur 252/333 mit 1 Leg; SingleToMulti2 2 oder 4; `Mixed_` = n × Waren, Deckel 4 | Loader: `aToB` 1 Leg, `singleToMulti` = `stops` | **Prüfung auf `len(legs) == min(stops × verschiedene Waren, 4)`, falls sie in H1 für 100 % der Templates hält; sonst nur `len(legs) ≥ 1`**. Sonst lehnt der Loader die ganze Datei ab |
| V6 | Platzhalter, Höhlen, generische Namen (≈ 25 der 66) haben keine Position | Pool-Name ohne Position stoppt den Job | **Alias-Eintrag `drop` mit Grund: Name fällt aus dem Pool, Zahl im Changelog**. Sonst stoppt der Job jeden Monat |
| V7 | gleiche Gateway-Namen in zwei Systemen | `name` eindeutig in der Datei | **Eindeutig bleibt; bei Kollision gewinnt der Eintrag, den ein Pool auflöst, andere fallen mit Hinweis weg** (Nyx hat kein Board) |
| V8 | `min_scu null` / `max_container_size -1` (nur Planetary, Interstellar, „Hauling“; nie Stellar); Formen ohne Zahl (`SingleToMulti`, `MultiToSingle`) | `1 ≤ minScu ≤ maxScu`, Kiste ∈ Menge, `stops` aus der Form | **Template mit nicht ausdrückbarem Leg oder Form fällt mit gezähltem Grund weg, nichts geschätzt** |

**Lesart zur Bestätigung (L1):** `positions[].name` = Name **wie im Vertrag** („as contracts show it“). Die Alias-Tabelle bildet Vertragsname → Starmap-Eintrag ab; die Pools bleiben roh (nur V6-Drops). Folge: `Checkmate at the L4 Lagrange of Pyro II` ist der Positionsname, nicht `Checkmate`; mehrere Vertragsnamen können eine Starmap-`uuid` teilen (vier Lorville-Orte). Der Startprompt formuliert „Name aus `mission_tokens` → `name` in der Starmap“; das passt zu beiden Lesarten. Die Vertragslesart passt zum B1-Abgleich der App: der Scan zeigt den Vertragsnamen.

## Entscheidungen zu Abschnitt 3 des Auftrags (SD14), je mit Gegenargument

1. **Quelle (S-H0): Rohrepo statt API.** Ein Tarball-GET von `codeload.github.com/StarCitizenWiki/scunpacked-data/tar.gz/<sha>`, gestreamt mit stdlib `tarfile` + `urllib`, gefiltert auf `contracts/*.json` und `starmap_positions.json`; SHA und Build aus `gh api repos/StarCitizenWiki/scunpacked-data/commits/master` (`github.gh_json`). Beide Dateien kommen aus einem Commit, die Laufzeit sinkt von ≈ 12 min auf ≈ 1 min, die Wiki-API bekommt keine 1.862 Aufrufe.
   - *Gegenargument:* Das Rohformat (PascalCase, Dumper-intern) ist kein veröffentlichter API-Vertrag und kann sich mit einer Dumper-Version ändern. Die `MaxScu`-Regel der API müssen wir nachbauen. Der Download (≈ 1,5 GB entpackt) ist viel größer als das Nutzsignal. Das Wiki erbittet den Credit „api.star-citizen.wiki“; der Credit nennt dann zusätzlich das Repo.
   - **Kein API-Fallback gebaut (A4)**, Backlog-Zeile mit Anlass „scunpacked-data hängt einen Build hinter der API oder verschwindet“. Exit-Plan A11 bleibt D119 (Scans, UEX).
2. **K2-Variante: Vorgänger weitertragen**, `null` nur, wenn der Vorgänger keine Hauling-Daten hat (erster Lauf). *Gegenargument:* Ein veralteter Stand ist stiller als ein fehlender. Gegenmittel: Hinweis in Summary, `last-run.json`, Release-Notes und PR („carried from ships-…“).
3. **Release-Auslöser: ein Hauling-Diff allein löst ein Release aus**, über den bestehenden Pfad: `changed = Schiffe geändert ODER Hauling geändert`. `build` baut dann 0 Modelle, `verify` trägt alle Schiffe und Holos byte-gleich, das Gate rendert unveränderte Schiffe (grün, ≈ 11 min Windows). Hauling-„geändert“ heißt: Inhalt von `templates[]` bzw. `positions[]` anders; Stempel (`dataVersion`, `source.*`) werden nie verglichen (Regel C aus T12.1). *Gegenargument:* 11 min Gate und ein neues Release für Schiffe, die sich nicht geändert haben; Schiffs-JSON bekommen ggf. ein neues `source`, wenn sich der Motherlode-Katalog-Stempel geändert hat.
4. **Alias-Tabelle `tools/hauling-aliases.json`:** Vertragsname → `{"uuid": "<starmap uuid>", "starmap": "<Name zum Lesen>"}` oder `{"drop": "<Grund>"}` (V6). Die Abbildung geht über die `uuid`, weil eine Umbenennung in der Starmap sonst als Lücke erschiene; `starmap` dient der Kontrolle (abweichend → Hinweis „renamed“). Ohne Alias wird exakt per Name im System des Templates aufgelöst (System `null` → eindeutig über alle drei Systeme); mehrdeutig oder unbekannt → Lücke. **K1:** Der Pool trägt danach den Starmap-Namen (dedupliziert, sortiert); die Vertragsform landet in `contractNames[]` der Position.
   - Erstbefüllung aus den Rohdaten des Pins; Zahlen je Kategorie in TASKS.md.
   - Vermutlich nicht auflösbar ohne Martin: Rayari (5 Kandidaten), Magnus Gateway, Ita Derelict Outpost, 7 Orte ohne Starmap-Eintrag (Riker Memorial Spaceport usw.). Vorschlag: **`drop` mit Grund**, außer Martin nennt das Ziel.
   - *Gegenargument:* Eine handgepflegte Tabelle im Repo widerspricht „läuft ohne Martin“. Sie wächst aber nur mit neuen Orten, und jede Lücke kommt als PR.
5. **Positions-Filter:** `system ∈ {stanton, pyro, nyx}` und `type ∈ {Manmade, Manmade_VisibleOnInteraction, Planet, Star}` und `hidden = false`; dazu jeder Ort, den ein Pool auflöst, beliebiger Typ, auch `hidden`. Eine Position je `uuid` (K1); Name eindeutig je System, bei Kollision gewinnt der erste in Starmap-Reihenfolge, mit Hinweis (K3). `parent` = Positionsname der `parent_uuid`, wenn in der Datei, sonst `null`; `hidden`/`qt_valid` nicht in der Datei.
   - Erwartung aus der Zählung: 52 Stanton, 20 Pyro, 19 Nyx (5 hidden Nyx-Manmade raus) + Pool-Orte.
   - *Gegenargument:* `Star` steht nicht im Vertragstext („stations and planets“), nur im Startprompt. Er dient als Systemmitte für die Karte (T13.7), der Loader ignoriert den Typ.
6. **„verschoben“-Schwelle: 1 km** (euklidisch). Diff-Schlüssel ist die `uuid` (K1: eine Position je `uuid`): neu, weg, umbenannt (anderer `name`), verschoben (> 1 km), `contractNames` geändert. Dazu der K2-Hinweis: Templates, deren Leg-Anzahl von `min(stops × Waren, 4)` abweicht, als Zahl im Changelog. In H1 gemessen: Verschiebungen zwischen dem 4.10.2- und dem 4.10.3-Commit der Starmap, als Zahl in TASKS.md. *Gegenargument:* 1 km ist in Gm unsichtbar. Der Changelog soll aber jede echte Änderung nennen, und JSON-Rundung liegt weit unter 1 m.
7. **`updated_at` (Abschnitt 3.4): entfällt.** Kein Zeitstempel je Mission in Liste oder Detail; mit dem Rohrepo dauert ein voller Lauf ≈ 1 min. SD7 gilt: keine Antwort im Cache, jeder Lauf holt neu.
8. **`gameBuild`** = Regex `\d+\.\d+\.\d+-[A-Z]+\.\d+` auf die erste Zeile der Commit-Message. Kein Treffer → erste Zeile als Wert, mit Hinweis. Weicht der Build vom Motherlode-Build ab → nur Hinweis.
9. **Ein Teilschritt im Job `chain`, kein eigener Job** (Präzisierung). Ein paralleler Job müsste die zwei CIG-Dateien als Artefakt übergeben; Artefakte sind öffentlich und tragen laut SD10 nur Berichte. Der Entwurf entsteht ohnehin in `chain`, und ≈ 1 min Laufzeit gewinnt durch Parallelität nichts.
   - Schritt `python -I tools/run.py hauling` nach `previous`, vor `diff`, mit **`continue-on-error: true`**: Selbst ein Bug färbt nur den Schritt rot, die Schiffskette läuft weiter. `verify` liest `work/hauling.json`; fehlt die Datei oder steht dort `failed`, wird weitergetragen bzw. `null` geschrieben.
   - *Gegenargument:* Der Startprompt nennt einen eigenen Job. Fällt `fetch` von Motherlode aus, kommt auch kein Hauling-Update (Schiffe zuerst, wie heute).
10. **Ein Unterbefehl `run.py hauling` statt fünf** (Präzisierung), intern fünf Stufen mit je eigener Zeile geprüft / gefunden / zu tun: `hauling-fetch`, `hauling-templates`, `hauling-positions`, `hauling-verify`, `hauling-diff`. K2 liegt damit an einer Stelle: Quellfehler, Lücke oder roter Verify ergeben `status: failed` und Exit 0. Lokal mit `--saved <tarball>`. *Gegenargument:* Im Actions-UI ist es ein Schritt statt fünf; die Summary zeigt trotzdem alle fünf.
11. **E1: Job `hauling-pr` feuert auf jedes `failed` (auch ein abgestürzter Schritt ohne `work/hauling.json`).** Alias-Lücke → PR wie unten; jeder andere Fehler → Issue „Hauling job failed“ mit Fehlerbericht (vorhandenes offenes Issue wird ergänzt statt dupliziert; `issues: write`). Im Dry-Run nur der Text nach `out/`.
    **Lücken-PR, kein Halt des Schiffsreleases.** Der bestehende PR-Pfad (SD11) hält den Entwurf bis zum Merge; das widerspräche K2. Stattdessen:
   - `hauling-pr` (needs `chain`, `if: needs.chain.outputs.haulingPr == 'true'`, `contents` + `pull-requests: write`) schreibt `tools/hauling-aliases.json` mit Vorschlägen auf den Branch `data/hauling-aliases`, nutzt `github.gh`/`git` und das Muster von `pr_stage`/`close_superseded`.
   - PR-Text: unaufgelöste Namen, Kandidat (eindeutig / mehrdeutig / keiner), betroffene Templates.
   - Merge = Tabelle erweitert; die Daten kommen mit dem nächsten Lauf (Martin klickt Dispatch oder wartet auf den 1.).
   - Übergabe per Artefakt `reports-hauling` (`work/hauling.json` + Vorschlag; nur Namen, kein Inhalt aus `contracts/`).
   - *Gegenargument:* ein zweiter PR-Typ neben dem Daten-PR. Er bleibt aber klein und gibt nichts frei.

## Ablauf nach der Freigabe (je Block ein Commit `H1: …`, englische Message, kein `Co-Authored-By`)

1. **Doku:** SD14 (Kontext, Quellen + Abholweg, K2-Variante, Auslöser, Alias-Tabelle, Positions-Filter, Schwelle, Gegenargument: CIG-Material wie Holos, Drittquelle zwischen Spiel und uns, Monatstakt); Addendum SD2; Abschnitt `hauling` in `docs/manifest-format.md` wortgleich zum Vertrag (inkl. V-Addenda, sobald der Reviewer sie entschieden hat); `NOTICE.md`-Absatz (CIG; octfx/ScDataDumper; StarCitizenWiki/scunpacked-data; api.star-citizen.wiki als Herkunft der Normalisierungsregeln).
2. **Tests rot** (pytest, synthetisch, klein, `tests/test_hauling_*.py`; Verify-Tests gegen die Vertragsfassung mit den Addenda der App-Session, vorher prüfen, ob der Doku-Commit da ist; sonst die übrigen Blöcke zuerst): beide Namensschemata → Modell (inkl. `AtoB`/`AToB`, `Mixed_`, `RuinToStation_RegionX`); `MaxScu`-Regel; Filter (released, TEMPLATE, Auftraggeber); Ausschlussgründe gezählt; Alias Treffer / Lücke / `drop` / umbenannt; Positions-Filter (hidden, Typ, Kollision V7, kein Doppel per `uuid`); jede Verify-Regel einmal provoziert rot; Manifest-Abschnitt (optional beim Lesen, `expected_assets`, nicht in `files`/ZIP); Diff (neu/weg/Reward/verschoben/umbenannt, Stempel ignoriert); K2 (Quelle down, Lücke, Verify rot → Vorgänger bzw. `null`, `changed` nur aus Schiffen, Schiffsrelease unberührt); Workflow-Regeln (`continue-on-error` am Hauling-Schritt, `hauling-pr` mit eigenen `permissions`, `heartbeat.needs`).
3. **Paket `tools/shipdata/hauling/`:** `source.py` (Commit + Tarball, eine GET-Folge, User-Agent `sc-cargoplan-shipdata (+https://github.com/MRiediger/sc-cargoplan-shipdata)`), `templates.py`, `positions.py`, `check.py` (Loader-Checks + Pipeline-Regeln), `diff.py`, `stage.py`. Dazu `run.py hauling` und `hauling-pr`; `stages.diff_stage` (`changed`), `verify_stage` (Abschnitt + Kopie), `manifest.build/read/check`, `release.pack`, `workflow.expected_assets`/`draft_stage` (Changelog in den Release-Notes)/`outcome`/`summary_line`/`JOBS`; `previous_stage` prüft die Hauling-Dateien des Vorgängers (Länge, SHA, Loader-Checks → Hinweis).
4. **`tools/hauling-aliases.json`** erstbefüllt; Zahlen je Kategorie.
5. **Workflow** `ship-data.yml`: Schritt `hauling`, Job `hauling-pr`, `heartbeat.needs`, Artefakt `reports-hauling`.
6. **Lokal in WSL** (`tools/local-wsl.sh`): `run.py hauling` gegen den Pin, **Datenprobe** (Skript im Scratchpad, nicht committet, A17): Everus/Senior 89 / Stanton1 21; Red Wind nach Vertragsfilter (erwartet 194, mit V4 + 7); Template-Menge aus dem Rohrepo = Menge aus Martins Dump nach demselben Filter (n/n, Abweichungen erklärt); Positionen mit 4 Hubs, 18 L-Stationen, Ruin Station, Checkmate, Orbituary (per `uuid`); Everus → HUR-L1 1,3 Gm, → Baijini 22,9 Gm. Laufzeit, Dateigrößen, Templates je Contractor × missionType, Ausschlüsse je Grund, Positionen je System × Typ → TASKS.md.
7. **Dispatch** (Martin klickt) auf `feat/h1-hauling` mit `dry-run=true`: Summary zeigt fünf Hauling-Zeilen, `release --dry-run` listet beide Assets. Zweiter Dry-Run mit einer provozierten Alias-Lücke (temporärer Commit, danach revertiert): Hauling `failed`, Schiffskette grün, Assets ohne neue Hauling-Dateien, `hauling-pr` schreibt im Dry-Run nur `out/hauling-pr-body.md` (die echte PR-Anlage deckt der FakeGitHub-Test ab, wie bei T12.2).
8. Abnahme Martin → `git merge --no-ff feat/h1-hauling`, `gh run list -L 3`, Push durch CC; dann **echter Dispatch** → `ships-2026.11.2` mit Abschnitt `hauling` (Übergabe an T13.3); Loader-Checks auf dem veröffentlichten Release per `run.py previous` des nächsten Laufs bzw. lokal mit den Release-Dateien.
9. **TASKS.md** (neuer Abschnitt „Phase 13 (App) – Hauling-Daten“, H1 mit Warum / Akzeptanz / Zahlen / Präzisierungen, `[x]` nach Abnahme); **CLAUDE.md** (Ansatz-Block um den Hauling-Schritt, Regeltabelle um K2 und Alias-Lücke, Rollen: Master-Chat für Phase 13, Projektstruktur, Befehle, Quelle in Domänenfakten); Backlog: Zeile „`NOTICE.md` in `files`“ bleibt mit neuem Anlass (die Reader von v0.6/v0.7 lassen in `files` nur `outlines.json`/`ships/**` zu); API-Fallback-Zeile.

## Rückfragen an den Reviewer (Vorschlag jeweils fett) – beantwortet, siehe Freigabe

- **R1** V1–V8 und L1: je **Vorschlag wie in der Tabelle**. Die Addenda gehören ins App-Dokument (App-Session); H1 baut erst danach.
- **R2** Rohrepo statt API, kein Fallback: **ja**.
- **R3** Teilschritt in `chain` statt eigenem Job (SD10): **ja**.
- **R4** Lücken-PR als eigener Job, der das Schiffsrelease nicht hält, statt Stopp-Befund im Daten-PR: **ja**.
- **R5** Akzeptanzzahl Red Wind: **194 (Vertragsfilter), mit V4 201**, statt 208.
- **R6** Akzeptanz „provozierter Fehler ergibt PR“: **Dry-Run zeigt den PR-Text, echte PR-Anlage per Test**; Alternative: ein echter Lauf mit Lücke auf `main` (erzeugt ein Release mit weitergetragenen Daten und einen echten PR).

## Nicht in H1

Lesen in der App (T13.3), `hub-profiles.json` (entfällt, D119), Distanzmatrix (rechnet die App), Planetary-Sichtbarkeit, Pyro-Fraktionsgate, Dead Saints/Ling Family, Cache von Quellantworten (SD7), API-Fallback (Backlog), leere Stellar-Drop-off-Pools (Befund für T13.3).

## Dateien

- **Neu:** `docs/plans/H1-hauling.md`, `tools/shipdata/hauling/{__init__,source,templates,positions,check,diff,stage}.py`, `tools/hauling-aliases.json`, `tests/test_hauling_{templates,positions,check,diff,stage}.py`
- **Geändert:** `tools/run.py`, `tools/shipdata/{stages,manifest,release,workflow}.py`, `.github/workflows/ship-data.yml`, `tests/test_{workflow,manifest,workflow_stages,heartbeat_pr}.py`, `docs/decisions.md`, `docs/manifest-format.md`, `NOTICE.md`, `TASKS.md`, `CLAUDE.md`, `README.md` (Credit, Lauf)
- **Wiederverwendet:** `log.Reporter.say/num/output`, `github.gh/gh_json/git`, `manifest.sha256`, Muster aus `workflow.pr_stage`/`close_superseded`, `FakeGitHub`, `conftest.write_json`
- Keine neue Abhängigkeit (stdlib `tarfile`, `urllib`, `hashlib`, `json`).

## Verifikation / DoD

- `pytest tests` komplett in WSL (`tools/local-wsl.sh test`), Zusammenfassung wörtlich; jede neue Regel einmal provoziert rot.
- Lokaler `run.py hauling` gegen den Pin + Datenprobe mit Zahlen in TASKS.md.
- Dry-Run-Läufe (normal + provozierte Lücke) verlinkt, `gh run view`; echter Lauf → Data-Release mit `hauling`, beide Assets, Manifest-Längen und SHAs stimmen, Loader-Checks grün.
- `git status` vor jedem Commit ohne Binär- und CIG-Dateien (A17); Dump und Tarball nie im Repo.

# TASKS – SC-CargoPlan Ship Data

Regeln: **ein Task pro Session**, Reihenfolge einhalten. Jeder Task hat eine „Warum“-Zeile und prüfbare Akzeptanzkriterien. Jeder Task beginnt mit einem Plan in `docs/plans/` und stoppt bis zur Freigabe aus dem Master-Chat. Erledigt → `[x]`.

Session-Start-Prompt für Claude Code:
> Lies CLAUDE.md und TASKS.md. Wir machen Task **Tx.y**. Fass den Task zusammen, schreib den Plan nach `docs/plans/`, committe, pushe, stopp.

Einstieg der App-Seite: `sc-cargoplan/TASKS.md`, Abschnitt „Phase 12“. Tasks mit Präfix **App:** laufen dort, in diesem Repo steht nur die Schnittstelle.

---

## Phase 12 – Ship data channel (gestartet 16.11.2026, abgeschlossen <Datum der Abnahme T12.6b>)

**Zielbild, Regeln, Manifest:** siehe CLAUDE.md. **Zwei Repos:** dieses baut und veröffentlicht, `sc-cargoplan` liest (App) und zieht die Baseline beim Build (`release.yml`).

**Vorbereitung (Martin, erledigt 17.11.):** Repo öffentlich und leer angelegt, Secret `MOTHERLODE_API_KEY`, Actions „Read and write“ + „create and approve pull requests“. Parallel: Anfrage an Sciirof (Modell-Endpunkt, Erlaubnis Monatslauf, Cyclone, 135c-Transform) – Antwort ausstehend.

### [x] S12.0 Spike – ein Schiff end-to-end auf Actions (Plan freigegeben 17.11.2026, kein Prod-Code, abgenommen 17.11.2026)

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
4. **Import-Datum – in S12.0 behoben (Nachtrag 1).** Der Fix wandert mit dem Import nach T12.1.
5. **Erster echter Lauf trifft sofort die Regeln** „verschwunden“ und „neues Schiff“ (`hyun`) sowie eine Rack-Änderung (F7C). Die Verschwundenen sind Varianten (Nachtrag 3): Die Regel braucht den Fall „Variante ohne eigenen Katalogeintrag“. Frage an Sciirof: Sind die Varianten absichtlich zusammengelegt?
6. **Anker-Umzug machbar:** `import-motherlode.ps1` läuft unter pwsh auf Linux unverändert bis aufs Datum; `decimate.ps1`/`run-all.ps1` entfallen.
7. **E1:** `actions/cache` ist für Fork-PR-Workflows lesbar → den Katalog in T12.2 nicht cachen, oder Fork-Workflows abschalten.
8. **E3:** Der Tausch im Checkout funktioniert (3,4 s inkl. Rebuild), hängt aber an `CopyToOutputDirectory` → Env-Override in `ShipPictureTests` (T12.5) bleibt vorzuziehen.
9. **Gate-Laufzeit ≈ 10 min** pro Job mit zwei Bildläufen; `setup-python` auf Windows (46 s) in T12.2 weglassen.
10. **Lokaler Test vor dem Runner:** `spike/local-wsl.sh` fand die Datumsabweichung vor dem Runner-Lauf. Muster für T12.1: `run.py` erst in WSL Ubuntu 24.04, dann im Workflow.
11. **„Verschwunden“ heißt nie löschen; Stopp-Schwelle.** Regel in T12.1: Ein verschwundenes Schiff bleibt mit seinem letzten Stand und `missingSince`. Eine Variante, deren Basis-`className` noch im Katalog steht, bekommt die Daten der Basis. Bei mehr als **3** neu verschwundenen Schiffen ohne Basis hält der Lauf an und geht in den PR-Pfad. Ein Wert, der am 17.11. nicht gefeuert hätte (0 ohne Basis), einen Massenabgang aber stoppt; die Zahl ist zu bestätigen.

**Nachtrag Review (17.11.2026):**
1. **`source`-Datum – behoben, gemessen.** Der vorgeschlagene Fix `ToString("o")` reicht nicht: Er schreibt 7 Nachkommastellen (`2026-11-12T20:50:33.0360000Z`), die API und die Dateien von v0.5.1 haben 3 (`…33.036Z`).

   | Variante | pwsh 7.6.10 | Windows PowerShell 5.1 |
   |---|---|---|
   | wie bisher | 104 / 108 anders | 0 / 108 |
   | `ToString("o")` | 104 / 108 | 0 / 108 |
   | `ConvertFrom-Json -DateKind String` | **0 / 108** | **0 / 108** |

   Der Import liest `updatedAt` als String, wenn `ConvertFrom-Json` den Parameter kennt (pwsh ≥ 7.5); 5.1 lässt Strings ohnehin unverändert. `spike/chain-job.sh` patcht die ausgecheckte Kopie. Lokal in WSL (Archiv 16.11.): `100i.json` **byte-gleich**, Import schreibt **0** Dateien um – die ganze Ubuntu-Kette (Holo, Umriss, Schiffs-JSON) ist damit byte-gleich zu v0.5.1/holo-v3.
2. **Gewollte Render-Änderungen brauchen keinen Freigabepfad im Daten-Gate.** Das Gate rendert alten und neuen Datenstand mit **derselben** gepinnten App-Version (K1). Ändert sich der Renderer (neuer App-Tag im Pin), rendern beide Seiten mit dem neuen Renderer und bleiben gleich, solange die Daten gleich sind. Der Pin-Bump ist ein gewöhnlicher Commit. Renderer-Regressionen prüft das App-Repo mit seinem eigenen `ShipPictureTests`-Ablauf (D90). Was hier rot wird, sind gewollte **Daten**-Änderungen an vielen Schiffen (z. B. neue Holo-Parameter): Das ist der vorhandene PR-Pfad („Regel feuert → PR, Martins Merge = Freigabe“) mit dem Diff-Bericht als PR-Text. Ein Input `render-change=true` wäre ein Schalter, der das Gate umgeht, und wird nicht gebaut.
3. **Verschwunden: 6 neu, alle Varianten.** Gegenüber dem Archiv vom 16.11. fehlen am 17.11. MOLE Carbon/Talus (`ARGO_MOLE`), Carrack w/C8X und Carrack Expedition w/C8X (`ANVL_Carrack`, `ANVL_Carrack_Expedition`), Mustang Alpha Vindicator (`CNOU_Mustang_Alpha`) und Valkyrie Liberator Edition (`ANVL_Valkyrie`). Jede teilt ihre `className` mit dem Basisschiff, das noch im Katalog steht. Cyclone und 600i Executive fehlten schon am 16.11.; der F7C Hornet Mk II ist zurück. Keine Umbenennung erkennbar; `hyun` (32 SCU) lässt sich ohne den Katalog vom 17.11. (nur im Actions-Cache) keiner `className` zuordnen → im ersten T12.1-Lauf prüfen. Regel siehe Punkt 11 oben.
4. **`CLAUDE.md` korrigiert:** `ubuntu-24.04` für die Kette, `schemaVersion` 6.

**Lauf 4 (17.11., nach `bafb244`, [44101340566](https://github.com/MRiediger/sc-cargoplan-shipdata/actions/runs/44101340566), chain grün):**
- Anfragen: „0 API, 0 page GET, 101 HEAD, 2 model GET“ (Katalog aus dem Cache).
- **Der Datums-Fix wirkt.** `source` steht jetzt im ISO-Format wie die API (`2026-11-16T11:36:30.299Z`).
- **99 Dateien unterscheiden sich in `source`**, weil der Katalog vom 17.11. ein anderes `updatedAt` hat (16.11. statt 12.11.). Das ist eine echte Quelländerung, keine Formatfrage. Über `source` hinaus geändert: nur `f7c_hornet_mk_ii`.
- Holo, PP-Metriken und `ship-outlines.json` weiter byte-gleich zu holo-v3.

- [x] Abnahme Martin (17.11.2026), Review im Master-Chat

### [x] T12.0 Doku (Plan freigegeben 18.11.2026 mit Korrektur K1, `docs/plans/T12.0-doku.md`, abgenommen 18.11.2026)

**Warum:** Zwei Repos brauchen einen gemeinsamen Vertrag, bevor Code entsteht; die Befunde aus S12.0, T12.1 und dem T12.1-Review müssen in den Plan.
- `docs/decisions.md` hier: **SD1–SD9** (zwei Repos, Manifest, Gate, Release-Reihe + Asset-Layout, Judge, verschwunden/Variante/wieder da, Cache und Fork-PRs, Pins, Lebenszeichen)
- `docs/manifest-format.md` ratifiziert (SD2): `orderKeys`, `assets`, Holos flach, `holo.baseUrl` gestrichen
- `CLAUDE.md`: Regeltabelle auf SD5/SD6, Manifest, Asset-Layout, Pins, Projektstruktur
- `TOOLS.md` als Abschrift der Pins (K1); T12.1b neu; T12.2 ergänzt
- **App:** D111 „Ship data channel“, Phase 12 in `sc-cargoplan/TASKS.md` mit T12.3–T12.6, „P12 Look“ → `K6.4-P12 Look`, Zeile „Netz“ mit Zugriff 3 ab v0.6.0 – Branch `docs/p12-channel`

**Entscheidungen aus dem T12.1-Review (Martin, 18.11.):**
- **D1** Judge-Regel: Verschlechterung heißt Metrik, nicht Flag → SD5 (ersetzt P9)
- **D2** Grid-Reihenfolge: OrderKeys ins Manifest, `--previous-catalog` entfällt → SD2
- **D3** Asset-Layout: `manifest.json` + `NOTICE.md` flach, `ships.zip`, `<slug>.holo` → SD4
- **E1** Wiederauftauchen ist eine Regel → SD6

**Präzisierung in der Planphase, ratifiziert durch Freigabe (18.11.):**
1. **K1 – Pins maschinenlesbar, `TOOLS.md` bleibt Doku.** Mein Entwurf ließ `run.py` den App-Tag aus einer Markdown-Zeile lesen. Stattdessen `.python-version`, `.nvmrc` (gelesen von `setup-python`/`setup-node`), `tools/pins.json` (`appTag`, `runner`, `pwsh`); `run.py` und `tools/local-wsl.sh` lesen daraus; `tests/test_versions.py` prüft Tabelle gegen Quellen.
2. `pwsh` steht zusätzlich in `pins.json` – sonst wäre `local-wsl.sh` seine einzige Quelle. Auf dem Runner kommt pwsh vom Image und wird nur gemessen.
3. Der Test „Runner im YAML = `pins.json`“ kommt mit T12.2; vorher gibt es kein YAML.
4. **F1:** `HAUSDORFF_TOLERANCE = 0.0025`, vorläufig, gemessen in T12.1b. **F2:** `K6.4-P12 Look`, nur dieses Vorkommen. **F3:** zusätzlich verfehlte Metrik bei `passed=false` → PR (Fall 5 in SD5).
5. D111 auf Englisch, weil die App-`decisions.md` durchgehend Englisch ist.
6. Die Korrektur steht im Plan, nicht in einer eigenen Datei.
7. **Lesart von SD5 Fall 4:** „kein vergleichbarer Vorgänger“ gilt unabhängig von `passed` – jedes neue Schiff und jeder Quellwechsel geht einmal in den PR (so geht die F7C in den PR, wie D1 verlangt). **Bestätigt** (Martin, 18.11., Abnahme).

**Akzeptanz:** Freigabe aus dem Master-Chat; beide Repos zeigen dieselbe Task-Nummerierung und denselben Manifest-Vertrag.

**T12.0 Befund (18.11.2026):** 0 API-Rufe, 0 Workflow-Läufe.
- **Doku geprüft (A3):** GitHub „About releases“: bis zu **1 000** Assets je Release, je unter 2 GiB, keine Grenze für die Gesamtgröße – ein Limit gibt es also, D3 braucht 104. GitHub „Events that trigger workflows“: Cron in öffentlichen Repos nach 60 Tagen ohne Aktivität abgeschaltet (SD9, wörtlich zitiert). `setup-python` `python-version-file`, `setup-node` `node-version-file` (`.nvmrc`).
- **Zahlen für SD5:** 22 Holos `passed=false`, alle verfehlen nur Hausdorff (0,0058 … 0,0931, Schwelle 0,005); 79 bestehen (max 0,0049). Judge-Silhouette 512 px → ein Pixel ≈ 0,002 der Länge.
- **Pins (K1):** 5 Tests in `test_versions.py`; vorher rot (5 failed, `pins.json` fehlt); provoziert rot mit `.nvmrc` 24.16.1 (2 failed), `appTag` v0.5.0 (1 failed), hart kodiertem Python in `local-wsl.sh` (1 failed); zurückgesetzt grün.
- **pytest komplett** (WSL, Pins): `69 passed in 19.44s` (65 aus T12.1 + 4 neue Pin-Tests; `test_tool_versions_match_the_pins` liest jetzt die Quellen statt Konstanten).

- [x] Abnahme Martin (18.11.2026), Review im Master-Chat; Fall 4 bestätigt. App: `docs/p12-channel` gemerged als PR #27 (`61624c5`, `--no-ff`).

### [x] T12.1 Pipeline – `run.py fetch · diff · build · verify · release` (Plan freigegeben 17.11.2026 mit Auflagen A–D, `docs/plans/T12.1-pipeline.md`)

**Warum:** Vier Skripte in zwei Repos werden ein Einstieg mit Regeln als Code; das ist die Hälfte des v0.5.1-Handlaufs.
- Portierung aus `sc-ship-outlines` (Motherlode-Kette, nicht `legacy/`) und `sc-cargoplan/tools/import-motherlode.ps1` + `ShipJson.ps1` (Anker); Windows-Annahmen raus (`decimate.ps1`, `run-all.ps1` entfallen); vor dem Kopieren Secrets-Scan
- `fetch`: Katalog einmal per API, Modelle nach SHA, alte Hashes aufräumen (Regel „Doppel-Modell“)
- `diff`: gegen das Manifest des letzten Releases: neu / geändert / verschwunden
- `build`: nur geänderte Modelle; Umriss, Anker; `-Create`-Fix (`modelKey` aus der Map)
- `verify`: Regeln aus der Tabelle (Judge, verschwunden → `missingSince`, Transform → `overrides.json`, Überlappung → Stopp), Manifest-Schreiber, Hashes
- `release`: Asset-Liste, NOTICE, `--dry-run`
- Jede Stufe: geprüft / gefunden / zu tun; `pytest` für jede Regel, einmal provoziert rot
- `LICENSE` (MIT), `NOTICE.md` (Daten), README

**Regeln aus S12.0:**
- **`diff`:** Schiffs-JSON ohne `source` vergleichen (Hash über den Inhalt abzüglich des Feldes). `source` wird beim Schreiben aus `builtFrom.motherlode` (Build + `updatedAt`) gesetzt und nie verglichen. Anlass: Lauf 4 – ein neues `updatedAt` ändert `source` in 99 Dateien.
- **`verify`, Varianten:** Die Daten des Basisschiffs werden nur übernommen, wenn die Rack-Daten der Variante im letzten Manifest hash-gleich zum Basisschiff waren. Sonst gilt `missingSince` wie für jedes andere Schiff.
- **`verify`, Stopp:** Mehr als **3** neu Verschwundene ohne Basisschiff → PR-Pfad. Die Zahl ist zu bestätigen.

**Aus dem Spike übernommen:**

| Datei | Herkunft | Ziel | Grund |
|---|---|---|---|
| `holo_mesh.py`, `simplify.mjs`, `package.json`, `package-lock.json`, `requirements.txt` | `sc-ship-outlines` `25b4031`, unverändert | `tools/`, **byte-gleich**; SHA-256 in `docs/provenance.md` | S12.0: byte-gleiche Holos auf Ubuntu. Kein Reformat, kein Rename, bis ein eigener Task mit Messung das verlangt |
| `chain.sh` | Spike | Logik der `build`-Stufe | Reihenfolge, Argumente, Abbruch an der ersten Leiterstufe ohne Fails – reproduziert `decimate.ps1` byte-gleich |
| `chain-job.sh` | Spike | Orchestrierung von `run.py` | Stufenfolge, Stopp-Regeln, „geprüft / gefunden / zu tun“ |
| `probe.py` | Spike | `fetch` | HEAD-Burst, Modell-SHA als Cache-Schlüssel, Kandidatenwahl |
| `fetch-motherlode.ps1` | `sc-ship-outlines` | `fetch` in Python | ein API-Ruf, Retry-After, User-Agent 1:1; pwsh bleibt nur für den Anker (`import-motherlode.ps1`, mit Datums-Fix aus S12.0) |
| `compare_built.py` | Spike | `verify` | Byte-Gleichheit von Holo, Umriss und JSON gegen das letzte Manifest |
| `compare.py` | Spike | Judge in `verify` | Pixelanteil; SSIM streichen (Befund 4) |
| `csvdiff.py`, `pictures.sh`, `swap.sh` | Spike | `tools/gate/` für T12.2 | `swap.sh` entfällt mit T12.5 (Env-Override) |
| `say.sh` | Spike | Python-Logger | Muster „checked / found / to do“ + `numbers.tsv` |
| `local-wsl.sh` | Spike | `tools/local-wsl.sh`, ruft `run.py` | Test in WSL Ubuntu 24.04 vor jedem Workflow-Lauf |
| `SOURCE.md` | Spike | `docs/provenance.md` | Herkunft und SHA-256 der übernommenen Dateien |

Regel: `spike/` wird erst gelöscht, wenn `run.py build` den 100i byte-gleich zu den Referenzen liefert: `orig-100i.holo` = holo-v3-Asset (`f05c9c4f…`), Umriss-Eintrag = `outlines/ship-outlines.json` von v0.5.1, `ships/100i.json` = v0.5.1 (mit dem Archiv vom 16.11.).

**Präzisierung, zur Ratifizierung mit der Freigabe des T12.1-Plans** (Abweichungen vom Auftrag vom 17.11.):
1. *SHA „in die Datei“* → nach `docs/provenance.md`. Ein SHA in der Datei ändert die Datei und damit ihren SHA; `package.json` kennt keine Kommentare.
2. *Referenz „`built/` aus Lauf 3“* → holo-v3-Asset und v0.5.1. Artifacts verfallen nach 7 Tagen (`retention-days: 7`, Lauf 3 am 24.11.); die Referenzen sind dauerhaft.
3. *Katalog nach `tests/fixtures/`* → nicht committen (A17: Kataloge nie ins Git, Repo öffentlich; Fixtures klein und synthetisch). Sichern lokal und gitignored in `cache/`. Der Actions-Cache lässt sich nicht direkt herunterladen, und ein Artifact wäre öffentlich (ebenfalls A17). Den Weg klärt die T12.1-Session als erste Handlung.
4. *„0 neu, hyun erst mit dem Katalog, der ihn enthält“* → der Katalog vom 17.11. **enthält** `hyun` (Import-Log Lauf 3: `new hyun 1 grids, 32 SCU`). Erwartet also 1 neu.

**Akzeptanz:**
- Lokal ein voller Lauf gegen den Katalog 4.10.3: `ships/` **byteidentisch** zu `sc-cargoplan@main`, Umrisse und Holos **byte-gleich** zu holo-v3 (S12.0: Schwelle 0); `verify` meldet Cyclone als `missingSince` und 135c aus `overrides.json`; Tests grün.
- **Erste Handlung der Session:** den Katalog vom 17.11. (Actions-Cache `spike-catalog-v1`, Lauf 3/4) sichern, bevor der Cache verfällt (7 Tage ohne Zugriff). Wo und wie: siehe Präzisierung 3.
- `diff` Katalog 17.11. gegen den Stand aus dem Archiv 16.11. (= v0.5.1): Schiffs-JSON ohne `source` **1 geändert** (F7C), **1 neu** (`hyun`), **6 verschwunden** (Varianten mit Basisschiff); geänderte Modell-SHAs (Re-Export) separat gezählt.
- Martin kann die fünf Unterbefehle und ihre Übergaben nennen.

**Präzisierungen in der Planphase, ratifiziert durch Freigabe** (Details in `docs/plans/T12.1-pipeline.md`):

5. **P4 `release --seed`:** baut den ersten Release-Ordner aus `sc-cargoplan@v0.5.1` und holo-v3, ohne Katalog. `builtFrom.motherlode` kommt aus den `source`-Zeilen (Auflage D). Dieser Ordner ist zugleich das erste Release `ships-2026.11` für T12.6.
6. **P5 `build --all`:** baut jedes Modell, auch unveränderte. Nötig für die Byte-Akzeptanz und für spätere Pin-Bumps.
7. **P6 Import angepasst, nicht byte-gleich übernommen:**
   - Datums-Fix;
   - `-KeyMap`: `modelKey` kommt aus dem letzten Release; nur eine nie gesehene `className` bekommt einen abgeleiteten Key;
   - kein Anker in der Rack-Mitte;
   - `-Report` als JSON.

   Die 29 Alt-Keys bleiben (`docs/provenance.md`).
8. **P7 `overrides.json`** bedeutet hier „Schiff bleibt auf seinem Stand“. Die Budget-Pins aus `sc-ship-outlines` werden nicht portiert.
9. **P8:** Die 19 C#-Tests des Imports bleiben bis T12.5 im App-Repo.
10. **P9 Judge nur bei Verschlechterung** (Martin, 17.11.):
    - PR, wenn ein neu gebautes Holo `passed=false` hat und das Schiff vorher `passed=true` hatte, neu ist oder ein neues Modell bekam;
    - über 110 % Budget immer.

    CLAUDE.md ist angepasst.
11. **Auflagen der Freigabe:**
    - **A:** 404 → `model unavailable`, kein Abbruch;
    - **B:** alte Modell-Hashes räumt erst ein veröffentlichtes Release weg;
    - **C:** Stempel (`source`, `generatedAt`, `dataVersion`) werden nie verglichen;
    - **D:** siehe Punkt 5.
12. Neue Abhängigkeit: **pytest 9.2.0** (`tools/requirements-dev.txt`, Begründung in `TOOLS.md`).
13. `spike/` und `spike.yml` wurden am Ende von T12.1 gelöscht statt in T12.2 (Martin, 17.11.). Die Gate-Skripte liegen unverändert in `tools/gate/`.

**T12.1 Befund (17.11.2026)**

Gemessen in WSL Ubuntu 24.04 mit den Pins: Python 3.14.5, numpy 2.5.3, opencv-python-headless 5.0.0.93, Node 24.16.0, meshoptimizer 1.3.0, pwsh 7.6.10, pytest 9.2.0.
- Anfragen in der ganzen Session: **0 API-Rufe, 0 Seiten-GET, 81 Modell-GET**.
- Commits: `785df66` (Plan) bis `660c917` (Akzeptanz).

1. **Katalog vom 17.11. gesichert (erste Handlung).**
   - Lauf [44106694039](https://github.com/MRiediger/sc-cargoplan-shipdata/actions/runs/44106694039) (10 s) hat `spike-catalog-v1` wiederhergestellt und verschlüsselt hochgeladen (`openssl cms`).
   - Klartext 7 Dateien, 179 997 B; Chiffrat 195 272 B.
   - Lokal entschlüsselt: alle 7 SHA-256 gleich dem Log, Secrets-Scan 0 Treffer. Artifact und Workflow sind gelöscht.
   - Der Katalog liegt nur in `cache/catalogs/2026-11-17/raw/`, das Archiv vom 16.11. in `cache/catalogs/2026-11-16/raw/`.
2. **`hyun` = `GAMA_Hyun`:** 1 Grid mit 32 SCU und Transform, eigenes Modell. Martin: neues Schiff, `modelKey` `gama-hyun`.
3. **Tests: 65 grün.**
   - Jede der 14 Regeln wurde einmal provoziert: Fehler eingebaut, Test rot, Fehler zurückgenommen, Test grün.
   - Die 14 Regeln:
     - Schwelle > 3;
     - Variante nur bei gleichen Racks;
     - `missingSince` bleibt;
     - Überlappung;
     - Judge;
     - `source`-Stempel nicht verglichen;
     - Umriss-Stempel nicht verglichen;
     - 404 bricht nicht ab;
     - fetch löscht nie;
     - Prune behält den aktuellen Hash;
     - Seed behält `passed`;
     - Import-Datum;
     - kein Rack-Mitte-Anker;
     - Key aus der Map.
   - **Zwei Tests waren zu schwach** (404-Fall; Key gleich der Ableitung). Das fiel erst bei der Provokation auf; beide sind nachgeschärft.
   - Die 7 Import-Tests waren vorher gegen das v0.5.1-Skript alle rot.
4. **Seed:** 108 Schiffsdateien, 101 Holos, Stand `4.10.3-LIVE.13165946 / 2026-11-12T20:50:33.036Z`. 4 Schiffe haben eine andere Quelle: 135c, 600i Executive und F7C stammen von Fleetyards, Cyclone von 4.10.2.
5. **`fetch` mit dem Archiv vom 16.11.:**
   - 105 Schiffe, 99 Modell-URLs.
   - 18 Modelle aus dem lokalen Archiv (Hash geprüft), **81 GET, 0 × 404**, 71 s.
   - Modell-Cache 51 MB.
6. **`build --ship 100i`:** 20 s.
   - `orig-100i.holo` ist **byte-gleich** zu holo-v3 (93 794 B, `f05c9c4f…`).
   - `outlines.json` und alle 108 Schiffsdateien sind byte-gleich zu v0.5.1.
7. **Voller Lauf `build --all`:**
   - Laufzeit: 97 Modelle in **3 636 s** (Median 36 s, min 17 s, max 82 s für die Liberator). Der Cull braucht 2 626 s, also **72 %**.
   - Budgets: 56 × 20k, 10 × 30k, 31 × 40k. `work/holo` belegt 365 MB.
   - **Byte-Gleichheit:**
     - `ships/` **109 / 109 byte-gleich** zu `sc-cargoplan@main` (= v0.5.1, inklusive `source`);
     - `outlines.json` **byte-gleich** (152 534 B);
     - Holos **101 / 101 byte-gleich** zu holo-v3 (97 gebaut, 4 übernommen);
     - alle alten Modelle verfügbar: „byte-gleich 97 / 97, 0 Modelle nicht mehr verfügbar“.
   - **`verify`:** 110 / 110 Dateien gleich dem Seed, **0 Stopps**, 26 Hinweise:
     - 135c aus `overrides.json`;
     - `missingSince 2026-11-17` für Cyclone, 600i Executive und F7C (3 neu ohne Basis, also nicht > 3);
     - 22 × Judge „fails hausdorff, as published“. P9 wirkt, weil der Seed `passed=false` mitträgt.
   - **Centaurus:** wird aus `RSI_Constellation_Mk5_Centaurus` gebaut, liegt unter 40k und ist eine der 22. Keine 110-%-Meldung, daher keine Backlog-Zeile. Meine Aussage in der Planphase („holo-v1, nicht gebaut“) war falsch.
   - `release --dry-run`: 213 Dateien, 33 259 967 B.
8. **`diff` 17.11. gegen den Stand des 16.11.-Laufs** (mit `--previous-catalog`, Grid-Reihenfolge geprüft):
   - **1 geändert** (`f7c_hornet_mk_ii`), **1 neu** (`hyun`; angelegt, Anker nach dem Bau), 99 gleich (nur `source` neu).
   - 8 fehlen:
     - **6 Varianten sind neu verschwunden, alle mit Basis.** Ihre Racks waren im Manifest hash-gleich zur Basis: Carrack ×2, MOLE ×2, Mustang Alpha, Valkyrie (→ `follows`).
     - 2 fehlten schon vorher (Cyclone, 600i Executive); ihr `missingSince` bleibt.
     - 0 neu ohne Basis → kein Stopp.
   - Modelle:
     - **96 neu exportiert**;
     - 2 neu (`GAMA_Hyun`, `ANVL_Hornet_F7C_Mk2`);
     - 1 ohne URL (Cyclone);
     - 2 ungenutzt (das Variantenmodell der Carrack Expedition und das der 135c).
9. **Nebenbefunde:**
   - `builtFrom.tools.opencv` nannte die Modulversion 5.0.0 statt des Pins 5.0.0.93. Behoben, dazu ein Test gegen die Pins.
   - Während der Session wechselte der WSL-Standardbenutzer von `root` auf `artiniediger`. Die Werkzeuge liegen unter `/root/s12tools`; der Aufruf läuft daher mit `wsl -u root`.
   - Danach verweigerte Git das Repo wegen „dubious ownership“. `local-wsl.sh` vertraut dem Repo jetzt nur für seine eigenen Prozesse (`GIT_CONFIG_COUNT`).

**Das ändert sich an T12.2:**
1. **Der erste echte Lauf geht in den PR-Pfad.**
   - Der Katalog vom 17.11. hat 96 Modelle neu exportiert. Alle 22 `passed=false`-Schiffe bekommen dadurch ein neues Modell → Judge nach P9 „new model“ → Stopp.
   - Dazu die F7C: Ihr neues Motherlode-Modell ersetzt das Fleetyards-Holo (holo-v1).
   - Der PR-Text muss je Schiff den Judge-Befund mit Kontaktabzug enthalten. Sonst ist der Merge kein Urteil.
2. **Laufzeit:**
   - Die Kette braucht lokal ≈ 97 Modelle × 36 s ≈ 61 min, der Cull davon 72 %. Nötig ist ein Job-Timeout ≥ 90 min oder eine Matrix.
   - Der Modell-Cache hält bis zum Release beide Sätze (Auflage B): ≈ 2 × 51 MB.
3. **Release-Assets sind flach:**
   - `ships/` und `holo/` sind Ordner im Release-Ordner; GitHub-Assets können keine Ordner sein.
   - Das Asset-Layout (z. B. `ships.zip` + `<slug>.holo`) wird mit T12.3 festgelegt; die Pfade in `manifest.json` folgen.
   - `diff --previous` braucht den entpackten Vorgänger: `gh release download` und Entpacken gehören in einen `run.py`-Schritt, nicht ins YAML.
4. **Die Prüfung der Grid-Reihenfolge braucht den Vorgängerkatalog** (`--previous-catalog`). Der darf weder ins Release noch in den Cache (A17, E1).
   - Option a: `OrderKey`s je Schiff ins Manifest (abgeleitete Werte wie die Rack-Origins).
   - Option b: Prüfung ohne Vorgänger.

   Ohne Entscheidung prüft der Monatslauf die Reihenfolge nicht.
5. **Die Exit-Codes sind der Vertrag:**
   - `verify` mit Exit 2 → PR-Pfad. `work/verify.json` ist der Befund, `work/overrides-proposed.json` kommt als Commit in den PR.
   - `diff.json` mit `nothingChanged` → Lebenszeichen-Commit statt Release.
   - `release` ohne `--dry-run` endet noch mit einem klaren Fehler „T12.2“. Dort kommen `gh release create` und danach `fetch.prune_models` hin.
6. **`state/last-run.json`** schreibt noch niemand; das kommt mit dem Workflow.
7. **Der App-Tag fürs Gate** steht als `APP_TAG` in `run.py` und gehört als Pin nach `TOOLS.md`.
8. **Gate-Skripte:** Sie liegen unverändert in `tools/gate/` (`say.sh`, `pictures.sh`, `swap.sh`, `csvdiff.py`). `spike.yml` ist gelöscht; der Gate-Job wird neu geschrieben.
9. **`pytest`** läuft im Ketten-Job vor `fetch` (65 Tests, ≈ 20 s, braucht pwsh).

### [x] T12.1b Nachträge – Review-Entscheidungen als Code (Plan freigegeben 18.11.2026 mit F1 = (a) und E1, `docs/plans/T12.1b-nachtraege.md`)

**Warum:** D1, D2, D3 und E1 aus dem T12.1-Review (SD2, SD4, SD5, SD6) ändern Regeln und Release-Layout. T12.2 baut den Workflow auf dieses Layout, also kommt der Code vorher.
- **Judge nach SD5** in `rules.py`: fünf PR-Fälle (true → false, > 110 % Budget, Hausdorff schlechter um mehr als `HAUSDORFF_TOLERANCE = 0.0025`, kein vergleichbarer Vorgänger, zusätzlich verfehlte Metrik), sonst Hinweis; ein Test je Fall
- **Wieder da (E1, SD6):** Schiff wieder im Katalog → `missingSince` und `follows` `null`; Test
- **OrderKeys (D2, SD2):** `manifest.py` schreibt und liest `ships.<id>.orderKeys`, `diff.py` vergleicht die Grid-Reihenfolge gegen das Manifest; `--previous-catalog` raus aus `run.py`, `stages.py` und der Import-Übergabe. Offen: der Seed (`release --seed`) hat keinen Katalog – `orderKeys` dort `null` mit Hinweis („order not compared for this ship“), oder aus dem Archiv vom 16.11. (= v0.5.1)? Entscheidung im T12.1b-Plan.
- **Release-Layout (D3, SD4):** `release` schreibt `manifest.json`, `NOTICE.md`, `ships.zip` (`ships/**` + `outlines.json`) und `<slug>.holo` flach, Manifest mit `assets` und flachem `holo.ships.<slug>.file`; `diff --previous` liest Manifest + `ships.zip`
- **Toleranz messen:** die 22 Schiffe mit `passed=false` mit den Modellen vom 17.11. bauen (lokal, WSL), Δ Hausdorff je Schiff hier eintragen, SD5 per Addendum bestätigen oder korrigieren

**Akzeptanz:** `release --dry-run` zeigt das Layout (heute 104 Assets); `diff` gegen den Dry-Run-Ordner liefert weiter **1 geändert / 1 neu / 6 verschwunden**; jede neue Regel einmal provoziert rot; Toleranz gemessen und in SD5; `pytest tests` grün.

**Plan:** `docs/plans/T12.1b-nachtraege.md`, freigegeben 18.11.2026 mit **F1 = (a)** (`fails` je Holo ins Manifest) und Korrektur **E1** (Judge-Befund als Felder in `verify.json`, Text nur fürs Log). **Entscheidung Martin (18.11.):** Seed-`orderKeys` aus dem Archiv vom 16.11. (`release --seed --catalog`).

**Präzisierung in der Planphase, ratifiziert durch Freigabe:**
1. **P1** „`diff.py` vergleicht die Grid-Reihenfolge“ → `diff.py` liefert die Vorgänger-Keys aus dem Manifest, der **Import** vergleicht (`-PreviousOrder`): Bei geänderter Reihenfolge darf die Datei gar nicht erst geschrieben werden.
2. **P2** Seed-Keys über den echten Import gegen das Archiv (eine `OrderKey`-Implementierung); `--catalog` ist beim Seed Pflicht; würde das Archiv eine Datei umschreiben, stoppt der Seed.
3. **P3/F1** `holo.ships.<slug>.fails` als Pflichtfeld (SD2-Addendum).
4. **P4** Hausdorff = Maximum der drei Ansichten. **P5** vergleichbar = gleiche `className` (Re-Export ja, Quellwechsel nein).
5. **P6** Holos flach schon in der Stage, `ships.zip` deterministisch. **P7** `verify` braucht alle Holos des Vorgängers, `diff` nur Manifest + ZIP.
6. **P8** „Wieder da“ explizit (`rules.back` + Hinweis): vorher galt die Regel nur, weil niemand die Felder setzte – ein Test wäre nie rot gewesen.

**T12.1b Befund (18.11.2026)**

Gemessen in WSL Ubuntu 24.04 mit den Pins (`wsl -u root`). Anfragen der Session: **0 API-Rufe, 0 Seiten-GET, 22 Modell-GET** (nur Toleranz-Messung). Commits: `b2cac0a` (Plan), `28bdad8` (Judge), `6af3dff` (wieder da), `e1ba722` (OrderKeys), `c2d72a8` (Layout).

1. **Tests: 69 → 86 grün** (Abschluss: `86 passed in 79.16s (0:01:19)`). Je Block erst rot (Judge 12, wieder da 2, OrderKeys 6, Layout 13 Tests rot), dann grün. **24 Provokationen**, jede mit Fehler rein → rot → raus → grün (Skript im Scratchpad, stellt die Datei immer wieder her):
   - SD5 (9): Fall 1 entfernt · `BUDGET_SLACK` 1,2 · Fall 3 entfernt · Absolutwert statt Δ (3 rot) · Toleranz 0,002 · Fall 4 nur bei `passed=false` (2 rot) · „vergleichbar = Vorgänger existiert“ · Fall 5 entfernt · P9 zurück (2 rot). Jeder Fall-Test wurde allein rot, weil je Fixture genau ein Fall feuern kann.
   - F1 (3): Seed leitet nichts ab · Seed prüft `passed` nicht · Manifest liest Einträge ohne `fails`.
   - SD6 (2): `back` findet nichts · `verify` übernimmt den Vorgängerzustand aller Schiffe.
   - OrderKeys (5): Vergleich im Import aus · Import feuert bei jedem Vorgänger · Seed nimmt keine Keys · Seed stoppt nicht · Manifest prüft den Typ nicht.
   - Layout (5): ein Asset zu viel · ZIP mit Dateizeit · `diff` liest `previous/ships` (3 rot) · `unpack` ohne Manifest-Prüfung · `unpack` ohne Pfadprüfung.
   - **Ein Test war zu schwach:** „ZIP mit Dateizeit“ blieb grün – `touch()` ändert die Zeit um Sekundenbruchteile, ZIP speichert 2-Sekunden-Schritte. Nachgeschärft (`os.utime` auf 2001), danach rot.
2. **F1 – `fails` ableitbar:** `holo_mesh.judge` auf die holo-v3-Metriken (Sliver-Grenze 0,1563 aus `chain.py`, `error` ohne Länge = nicht verfehlt) ergibt **97 / 97** dieselben `fails` wie die `PP.json` des byte-gleichen T12.1-Laufs; bei allen 101 Einträgen passt `passed` zur Ableitung.
3. **PowerShell-Falle:** Der neue Parameter `$PreviousOrder` und die alte Hashtable `$previousOrder` waren **dieselbe Variable** (Namen ohne Groß/Klein) → 13 rote Tests mit „Cannot find path 'System.Collections.Hashtable'“. Hashtable heißt jetzt `$orderBefore`.
4. **Akzeptanz Seed** (`release --seed … --catalog cache/catalogs/2026-11-16/raw`): 108 Schiffsdateien, 101 Holos, **104 Assets**; `orderKeys` für **104** Schiffe, `null` für genau **4** (135c, 600i Executive, Cyclone, F7C); Import gegen das Archiv: 104 `same`, 1 `kept`, 3 nicht im Archiv, **0 Umschreibungen**.
5. **Akzeptanz Lauf 16.11. gegen den Seed** (`fetch` → `diff` → `build` → `verify` → `release --dry-run`): 0 Modell-GET (99 im Cache); Reihenfolge für **104** Schiffe verglichen, **0** vertauscht; 0 Modelle gebaut; `verify` **0 Stopps**, 4 Hinweise (135c aus `overrides.json`, `missingSince` für 600i Executive, Cyclone, F7C); Dateien gleich dem Seed **109 / 110** – die eine ist `outlines.json`, nur Stempel `dataVersion` (holo-v3 → ships-2026.11, Auflage C).
   **Dry-Run-Assets:** `manifest.json`, `NOTICE.md`, `ships.zip`, **101 × `.holo`** = **104 Assets, 33 112 743 B** (T12.1: 213 Dateien, 33 259 967 B).
6. **Akzeptanz `diff` 17.11. gegen den Dry-Run**, Ordner nur mit `manifest.json` + `ships.zip` (keine Holos): **1 geändert** (`f7c_hornet_mk_ii`), **1 neu** (`hyun`), **6 neu verschwunden** (Carrack ×2, MOLE ×2, Mustang Alpha Vindicator, Valkyrie Liberator; alle mit Basis); 2 fehlten schon (600i Executive, Cyclone), `diff` listet sie unter „gone“ mit (8 gesamt, wie in T12.1). Reihenfolge für **98** Schiffe verglichen, **0** vertauscht, nicht verglichen: F7C (Seed ohne Keys). Modelle: 96 neu exportiert, 2 neu, 1 ohne URL, 2 ungenutzt – wie T12.1.
7. **Toleranz-Messung (SD5):** 22 Schiffe mit `passed=false` (holo-v3), gebaut aus den Modellen vom 17.11., beurteilt mit dem neuen Judge gegen ihren holo-v3-Eintrag. **22 Modell-GET**, alle 200, **22 669 504 B in 16,5 s** (0,2 s Abstand, kein Retry, 0 nicht verfügbar). Bau **1 985 s** (parallel zu Tests, max 137 s Perseus/Polaris-Klasse). Skript nur gemessen, nicht committet (Spike-Regel); Ergebnisse unter `cache/runs/tolerance-17.11/`.

| Slug | Modell alt → neu | H alt | H neu | Δ | Budget | Dreiecke alt → neu | passed | fails neu | SD5 |
|---|---|---|---|---|---|---|---|---|---|
| aegs-hammerhead | `5a90679688b0` → `91954cc6bc44` | 0,0062 | 0,0062 | ±0,0000 | 40k → 40k | 39353 → 39444 | False | hausdorff | Hinweis |
| aegs-idris-m | `65e6cd1109ea` → `122e5124061f` | 0,0124 | 0,0124 | ±0,0000 | 40k → 40k | 39888 → 39355 | False | hausdorff | Hinweis |
| aegs-idris-p | `0874173d26fd` → `f8705f922b12` | 0,0124 | 0,0124 | ±0,0000 | 40k → 40k | 39840 → 39840 | False | hausdorff | Hinweis |
| aegs-tiburon | `b0574f9dca34` → `b731cc759048` | 0,0062 | 0,0062 | ±0,0000 | 40k → 40k | 39361 → 39371 | False | hausdorff | Hinweis |
| anvl-liberator | `df77df4465c9` → `9196013aacd8` | 0,0087 | 0,0087 | ±0,0000 | 40k → 40k | 38843 → 38844 | False | hausdorff | Hinweis |
| argo-raft | `373c0254d538` → `9865519953b3` | 0,0062 | 0,0062 | ±0,0000 | 40k → 40k | 39972 → 39987 | False | hausdorff | Hinweis |
| argo-srv | `2ab95478ddbe` → `922183b24a7f` | 0,0227 | 0,0227 | ±0,0000 | 40k → 40k | 39930 → 39942 | False | hausdorff | Hinweis |
| drak-corsair | `8b4df664aa11` → `14156e847240` | 0,0931 | 0,0339 | -0,0592 | 40k → 40k | 39923 → 39535 | False | hausdorff | Hinweis |
| drak-ironclad | `77bdd849b56b` → `ec799f603403` | 0,0062 | 0,0062 | ±0,0000 | 40k → 40k | 39758 → 39158 | False | hausdorff | Hinweis |
| drak-ironclad-assault | `598e3ef88b95` → `f75f38fdf222` | 0,0095 | 0,0095 | ±0,0000 | 40k → 40k | 38716 → 39004 | False | hausdorff | Hinweis |
| misc-starfarer | `76bf9600c71c` → `2c37ad19075f` | 0,0132 | 0,0029 | -0,0103 | 40k → 40k | 39330 → 39379 | True |  | – |
| misc-starfarer-gemini | `18e9ee0cffb1` → `a4dfa841f945` | 0,0112 | 0,0112 | ±0,0000 | 40k → 40k | 39277 → 39317 | False | hausdorff | Hinweis |
| misc-starlancer-max | `b4b6a79cd2ec` → `2e590003d496` | 0,0058 | 0,0058 | ±0,0000 | 40k → 40k | 38491 → 38491 | False | hausdorff | Hinweis |
| misc-starlancer-tac | `3b3d9182b2ec` → `ce679bd3ad0f` | 0,0062 | 0,0062 | ±0,0000 | 40k → 40k | 39098 → 39098 | False | hausdorff | Hinweis |
| rsi-apollo-medivac | `4f82c1751faf` → `045e38bcb039` | 0,0219 | 0,0219 | ±0,0000 | 40k → 40k | 39707 → 39707 | False | hausdorff | Hinweis |
| rsi-apollo-triage | `5def315d117d` → `c3df0e3dff02` | 0,0219 | 0,0219 | ±0,0000 | 40k → 40k | 39694 → 39694 | False | hausdorff | Hinweis |
| rsi-constellation-mk-iv-aquila | `9ec8e8365962` → `eab21dedf6e3` | 0,0103 | 0,0103 | ±0,0000 | 40k → 40k | 39676 → 39680 | False | hausdorff | Hinweis |
| rsi-constellation-mk-iv-phoenix | `00d242da8b3c` → `fd754a8fb055` | 0,0132 | 0,0132 | ±0,0000 | 40k → 40k | 39468 → 39532 | False | hausdorff | Hinweis |
| rsi-constellation-mk-v-centaurus | `150cf97828c6` → `a3b6c93a833c` | 0,0074 | 0,0074 | ±0,0000 | 40k → 40k | 39374 → 39380 | False | hausdorff | Hinweis |
| rsi-hermes | `7fcd5b56ed47` → `67bf1e6ee65c` | 0,0219 | 0,0219 | ±0,0000 | 40k → 40k | 39554 → 39554 | False | hausdorff | Hinweis |
| rsi-perseus | `da0d2cb45b00` → `0133bd612a97` | 0,0440 | 0,0440 | ±0,0000 | 40k → 40k | 38706 → 38716 | False | hausdorff | Hinweis |
| rsi-polaris | `418c3593ed5d` → `5e604daaed36` | 0,0112 | 0,0112 | ±0,0000 | 40k → 40k | 39414 → 39419 | False | hausdorff | Hinweis |

   - **Δ Hausdorff: 20 × exakt 0, 2 × besser** (Corsair −0,0592; Starfarer −0,0103 – sie **besteht jetzt**). min −0,0592, Median 0, **max 0**; **0** über 0,0025, **0 Stopps**, 21 Hinweise (alle „fails hausdorff, comparable“), 1 ohne Befund (Starfarer).
   - Budget bei allen 22 gleich (40k), Dreiecke ±600. Fall 5 feuert nicht: niemand verfehlt neu eine zweite Metrik.
   - **Warum exakt 0:** Der Judge misst die Silhouette in 512-px-Rastern; ein Re-Export verschiebt Kanten unterhalb eines Pixels, Hausdorff springt nur in Pixelschritten (≈ 0,002). Das Rauschen eines Re-Exports ist **0 Pixel**, nicht „knapp unter einem“.
   - **Urteil (vorab festgelegt: feuert bei keinem → bestätigt):** **0,0025 bestätigt**, SD5-Addendum. Erst eine Verschlechterung um ≥ 2 Judge-Pixel (≈ 0,004) stoppt; eine um 1 Pixel (≈ 0,002) bleibt Hinweis.
   - Grenze: die 79 bestehenden Holos nicht gebaut (Fall 1 zeigt erst der erste echte Lauf).

**Das ändert sich an T12.2:**
1. **Upload-Reihenfolge:** Release als Entwurf anlegen, Holos + `ships.zip` + `NOTICE.md` hochladen, **`manifest.json` zuletzt**, dann veröffentlichen – `latest/download/manifest.json` zeigt nie auf ein halbes Release (`gh release create --draft` / `upload` / `edit --draft=false`, in T12.2 gegen die Doku prüfen).
2. **Vorgänger laden:** `diff` braucht nur `manifest.json` + `ships.zip`, aber **`verify` braucht alle Holo-Assets** des Vorgängers (die unveränderten gehen byte-gleich ins neue Release; fehlt eins, bricht `verify` mit klarer Meldung ab). Also `gh release download` aller Assets (≈ 33 MB).
3. **„Nothing changed“ ist heute unerreichbar:** `diff` zählt Schiffe, die schon im Vorgänger `missingSince` hatten (600i Executive, Cyclone), jeden Lauf wieder als „gone“ → `nothingChanged` bleibt `false`, der Lebenszeichen-Pfad (SD9) käme nie. Fix zu Beginn von T12.2: nur **neu** Verschwundene zählen (im Vorgänger ohne `missingSince`/`follows`), mit Test.
4. Kein `--previous-catalog` mehr; `release --seed` braucht `--catalog`.
5. **PR-Text aus `verify.json`:** `findings[].data` trägt `cases`, Modell, `passed`, `fails`, Hausdorff (alt, neu, Δ, Toleranz), Dreiecke, Budget (E1); `detail` ist nur Log.
6. **Erster echter Lauf:** Stopps durch F7C (Fall 4, Quellwechsel Fleetyards → Motherlode) und `hyun` (Fall 4, neu); die 22 `passed=false` stoppen **nicht** (Befund 7: 21 Hinweise, Starfarer besteht jetzt). Ob ein Re-Export eines der 79 bestehenden Holos kippen lässt (Fall 1), zeigt erst dieser Lauf.
7. **T12.6:** Der Seed braucht das lokale Archiv vom 16.11. (A17, SD7) – das erste Release wird lokal in WSL gebaut (`cache/runs/seed` ist schon die Upload-Menge); der Upload-Weg muss das berücksichtigen.
8. **`ships.zip` reproduzierbar:** gleicher Inhalt → gleiche Bytes bei gleichen Pins (zlib); über Plattformen hinweg nicht zugesagt, der Vertrag sind die Hashes in `files`.

- [x] Abnahme Martin (18.11.2026), Review im Master-Chat.

### [x] T12.2 Workflow `ship-data.yml` (Plan freigegeben 18.11.2026 mit E1–E3, `docs/plans/T12.2-workflow.md`)

**Warum:** Der Lauf ohne Martin. Alles, was heute Zuruf ist, steht danach im YAML oder in `run.py`.
- cron `23 4 1 * *` + `workflow_dispatch` (Input `dry-run`), `permissions: contents: write, pull-requests: write`
- Cache nach Modell-SHA (Katalog nicht im Cache, S12.0 E1), Secret nur im Fetch-Step
- Diff → kein Unterschied: Lebenszeichen-Commit `state/last-run.json`, Ende
- Gate-Job `windows-latest`: Checkout `sc-cargoplan` auf gepinntem Tag (`appTag` in `tools/pins.json`, SD8), beide Stände im selben Job (S12.0 K1)
- Release-Pfad: `gh release create ships-YYYY.MM[.N]`, Assets, Hygiene (letzte zwei bleiben)
- PR-Pfad: Branch `data/YYYY.MM`, Befund als PR-Text, Kontaktabzug als Artefakt; nach Merge Release aus dem Merge-Commit
- ~~`spike.yml` und `spike/` löschen~~ – in T12.1 erledigt (Präzisierung 13); Gate-Skripte aus `tools/gate/`

**Aus T12.1 und T12.0 (SD3–SD9):**
- **Laufzeit:** Kette lokal ≈ 97 Modelle × 36 s ≈ 61 min (Cull 72 %) → Job-Timeout **≥ 90 min** oder Matrix; Modell-Cache bis zum Release ≈ 2 × 51 MB
- **Exit-Code-Vertrag:** `verify` Exit 2 → PR-Pfad (`work/verify.json` ist der Befund, `work/overrides-proposed.json` kommt als Commit in den PR); `diff.json` mit `nothingChanged` → Lebenszeichen statt Release; `release` ohne `--dry-run` macht `gh release create` mit dem D3-Layout, danach `fetch.prune_models`
- **PR-Text je Schiff** mit Judge-Befund (welcher SD5-Fall, Metriken alt/neu) und Kontaktabzug; sonst ist der Merge kein Urteil
- **`gh release download`** des Vorgängers (Manifest + `ships.zip`) und Entpacken als `run.py`-Schritt, nicht im YAML
- **Pins (SD8):** `setup-python` mit `python-version-file: .python-version`, `setup-node` mit `node-version-file: .nvmrc`; `runs-on` steht im YAML und in `tools/pins.json`, ein Test vergleicht beide; der Gate-Checkout nimmt `appTag` aus `pins.json` über `run.py`
- **`state/last-run.json`** schreibt der Workflow in jedem Lauf (SD9)
- **`pytest`** läuft im Ketten-Job vor `fetch`

~~**Akzeptanz:** Dispatch ohne Änderung … Release `ships-2026.11-test` …~~ ersetzt durch D1 (P2 unten).

**Entscheidungen aus der T12.1b-Abnahme (Martin, 18.11.):** **D1** Akzeptanz mit echten Läufen: Seed-Release `ships-2026.11` (aus T12.6 vorgezogen) → Dispatch 1 (PR-Pfad: F7C und `hyun` SD5 Fall 4) → Merge (Release `ships-2026.11.1`) → Dispatch 2 („nothing changed“). **D2** `nothingChanged` zuerst reparieren, Test zuerst. **D3** Cron ab dem ersten Commit aktiv, kein Schalter im YAML. **Nachtrag Master-Chat:** OpenAPI bestätigt kein Modell-Endpunkt; Transform-Konvention und „per release“ als Zitat nach `provenance.md`; Grid-Befunde im PR-Text mit Hinweis auf Motherlode-Meldung.

**Präzisierung in der Planphase, ratifiziert durch Freigabe** (Details im Plan):
1. **P1 Draft-Release statt Artefakt** (Martin, 18.11.): Daten und Kontaktabzug liegen im Entwurfs-Release (nur mit Schreibrecht sichtbar), nicht in öffentlichen Artefakten (A17); Artefakte nur für Berichte ohne CIG-Material. → SD10.
2. **P2** Akzeptanz nach D1 statt provozierter Fälle.
3. **P3** Gate rot = roter Lauf, kein PR (sonst Release ohne grünes Gate). → SD11.
4. **P4** `nothingChanged` zählt zusätzlich „wieder da“, geänderte Reihenfolge und Import-Stopps als Änderung.
5. **P5** `tools/gate/*.sh` + `csvdiff.py` werden `run.py gate` (Python, mit Tests); Kontaktabzug aus `sc-ship-outlines/motherlode_sheet.py` portiert.
6. **P6** Merge → Release über `push` auf `state/pending.json` (Entwurf nur bei gleichem Manifest-SHA); „Approve workflows to run“ entfällt voraussichtlich, weil `ship-data.yml` keinen `pull_request`-Trigger hat.
7. **P7** `verify --ci`: Exit 2 → Output `path=pr`, Exit 0; Stufen schreiben `$GITHUB_OUTPUT` selbst.
8. **P8** Modell-Prune im `publish`-Job (Cache wiederherstellen → prunen → neu speichern).
9. **P9** `dry-run` = Kette bis `verify` + `release --dry-run`, kein Entwurf, kein Commit.
10. **P10** Seed-Upload über `run.py draft` + `publish`, lokal.
11. **E1** `previous` wählt den Vorgänger nach Version, nicht über `isLatest`. **E2** Backlog-Zeile `ci.yml`. **E3** SD8-Addendum Dependabot.

**Akzeptanz (D1):** Seed-Release `ships-2026.11` (104 Assets, `latest/download/manifest.json` = Seed-Manifest); Dispatch 1 → PR mit Befund je Stopp und Kontaktabzug am Entwurf; Merge → Release `ships-2026.11.1` aus dem Merge-Commit, zwei Releases bleiben; Dispatch 2 → „nothing changed“, Commit in `state/`, kein Release. Martin: zwei Dispatches, ein Merge, kein Befehl.

**T12.2 Befund**

1. **Block 1 – `nothingChanged` (D2, P4).** `diff.split_gone` trennt neu Verschwundene von Schiffen, die im Vorgänger schon `missingSince`/`follows` hatten (`diff.json` `ships.gone` / `ships.stillGone`); `verify` gibt `rules.missing` beide Listen. `diff.nothing_changed` zählt zusätzlich `back`, geänderte Reihenfolge und Import-Stopps (`handcheck`, `kept` ohne `overrides.json`-Eintrag). Tests erst rot (**11 failed**), dann grün; ein bestehender Pipeline-Test prüfte das alte Verhalten und erwartet jetzt `stillGone` + `nothingChanged`. **5 Provokationen**, je rot: alte Zählung (3 rot) · `back` raus · Import-Stopps raus · Reihenfolge raus · `verify` ohne `stillGone` (Datum ginge verloren). Suite: `97 passed in 102.50s`.
2. **Block 2 – Version und Hygiene.** `shipdata/workflow.py` (reine Funktionen: `version_key`, `next_version`, `pick_previous` nach Version statt `isLatest` (E1), `to_delete` behält die letzten zwei veröffentlichten, `stale_drafts`), `shipdata/github.py` (`gh`, `gh_json`, `git` – die einzige Stelle mit `subprocess` für GitHub). 11 Tests, vorher rot (Modul fehlt). **4 Provokationen**, je rot: Version als Text sortiert (5 rot) · Vorgänger über `isLatest` (1) · drei behalten (1) · Entwürfe als veröffentlicht gezählt (3).
3. **Block 3/4 – `previous`, `draft`, `publish`** (`shipdata/workflow.py`, `run.py`).
   - **`previous`** lädt alle Assets der höchsten veröffentlichten Version (E1), prüft `ships.zip` und jedes Holo gegen das Manifest und schreibt `work/previous.json` mit dem Namen des eigenen Releases.
   - **Präzisierung P11 (Umsetzung):** Der Release-Name muss **vor** `build` feststehen, weil das Manifest ihn als `dataVersion` trägt und die App daraus die Holo-URL baut. Deshalb wählt `previous` den Namen, `build` nimmt ihn als Default, und `draft` nimmt den Tag aus dem Manifest. `draft` verweigert einen schon veröffentlichten Namen.
   - **`draft`:** Alte Entwürfe löschen → Entwurf anlegen → Holos, `ships.zip`, `NOTICE.md` hochladen → **`manifest.json` zuletzt** → Assets gegen das Manifest prüfen.
   - **`publish`:** Entwurf prüfen (Name, `state = uploaded`, Größe, `digest` – `gh release view --json assets` liefert `digest: sha256:…`, an holo-v3 des App-Repos geprüft) → bei `--pending` Manifest-SHA gleich `state/pending.json` → Kontaktabzug löschen → `--draft=false --latest --target` → Hygiene → Modell-Prune (Auflage B).
   - `release.publish` (Platzhalter „T12.2“) ist gelöscht.
   - **Martins Fall (18.11.):** Ein Entwurf mit weniger Assets als sein Manifest (Upload im vorherigen Lauf abgebrochen) und ein Entwurf ohne `manifest.json` stoppen **vor** `--draft=false`; der Test prüft, dass weder `edit` noch `delete` noch `delete-asset` lief und der Entwurf Entwurf bleibt.
   - Tests mit einem GitHub im Speicher (`FakeGitHub`: list, create, upload, view, download, edit, delete, delete-asset). 10 Tests vorher rot. **8 Provokationen**, je rot: Vollständigkeitsprüfung raus (Martins Fall + Digest, 2 rot) · Manifest mit den anderen hochgeladen · `pending`-SHA nicht verglichen · unfertiger Upload gilt als hochgeladen · veröffentlicht vor dem Löschen des Kontaktabzugs · `previous` ohne Holo-Prüfung · alte Entwürfe bleiben · Hygiene löscht nichts.
   - Suite: `118 passed in 103.77s`.
4. **Block 5/6 – `heartbeat` und `pr`** (`shipdata/workflow.py`, `run.py`, `log.py`).
   - **`outcome`** liest die Ergebnisse und Outputs aller Jobs (`toJSON(needs)`) → `nothing | release | pr | gate-red | error` (SD11). Ein Gate-Job, der rot endet, bevor er Bilder verglichen hat, heißt `error`, nicht `gate-red`.
   - **`summary_line`**, z. B. „Release ships-2026.11.1: 1 ship changed, 1 new, 96 holos refreshed“, „PR #12: 2 findings“, „nothing changed“, „error in fetch: SourceError: …“ (Stufe aus der Fehlerzeile von `run.py`). *holos refreshed* = neu gebaut und nicht byte-gleich.
   - **`heartbeat`** schreibt `state/last-run.json` (Datum, Lauf, Ergebnis, Zeile, Zahlen, die drei Zeilen jeder Stufe aller Jobs – `Reporter.say` schreibt sie dafür zusätzlich nach `out/say-<job>.jsonl`), committet als `github-actions[bot]`, einmal `pull --rebase`, Push auf `main`. Nach einem Merge: `state/pending.json` im selben Commit entfernt, die Zahlen kommen aus ihr.
   - **`pr`:** Branch `data/YYYY.MM`, Commit `state/pending.json` (Tag, Manifest-SHA des Entwurfs, Lauf, Zahlen) und – nur bei Vorschlag – `overrides.json`; PR anlegen oder Text aktualisieren; ältere offene `data/*`-PRs schließen („superseded“), ebenso nach einem direkten `publish`. `--dry-run` schreibt nur `out/pr-body.md`.
   - **PR-Text nur aus Feldern:** je Stopp eine Zeile mit SD5-Fall, Modell, `passed`, `fails`, Hausdorff alt → neu (Δ, Toleranz), Dreiecke / Budget; Gate (gleich / anders / unerwartet); Änderungen; Hinweise eingeklappt. **Grid-Befunde** (`order`, `overlap`, `handcheck`, `no-transform`) unter den Stopps bekommen den Satz, dass Motherlode Meldungen falscher Grids erbittet (Nachtrag Master-Chat).
   - 25 Tests vorher rot. **8 Provokationen**, je rot: Grid-Hinweis bei jedem Stopp · `pending.json` bleibt nach dem Merge · rotes Gate als `error` · unveränderter Lauf nicht erkannt · vorgeschlagene Overrides nicht committet · „refreshed“ = gebaut · eigener PR als überholt geschlossen · Stufenzeilen nicht mitgeschrieben (2 rot).
   - Suite: `143 passed in 95.26s`.
5. **Block 7 – Gate in Python** (`shipdata/gate.py`, `shipdata/sheet.py`; `tools/gate/` gelöscht, P5).
   - Ablauf: beide Releases gegen ihr Manifest prüfen → alter Stand in den App-Checkout → `bin/**/ships` und Umriss leeren → `dotnet build` → Bin-Kopie gegen den Stand prüfen → `ShipPictureTests` ohne Baseline → neuer Stand genauso → `ShipPictureTests` mit Baseline und erwarteten Schiffen → `gate.json` → Kontaktabzug an den Entwurf.
   - **Erwartete Schiffe ohne Stempel:** Schiffsdatei ohne `source` (`diff.content_hash`), Holo-SHA oder Umriss-Eintrag anders, oder neu; Holo/Umriss gilt für alle Schiffe des `modelKey`. Byte-Hashes aus `files` wären falsch: ein neues `updatedAt` macht ~99 Dateien „anders“, das Gate prüfte nichts.
   - **Rotes Gate zeigbar (Martin, 18.11.):** Der Kontaktabzug geht auch bei unerwarteten Abweichungen an den Entwurf, die unerwarteten Schiffe zuerst (Markierung `UNEXPECTED`), dann die Stopps, dann der Rest; erst danach Exit 1. Test: Upload lief, kein `edit`, kein PR-Aufruf, Entwurf bleibt Entwurf.
   - **Kontaktabzug** portiert aus `sc-ship-outlines/motherlode_sheet.py` (`077b8189…`): je Schiff eine Zeile Standard alt | neu, oben alt | neu, 6 Schiffe je Blatt, 1 920 px breit.
   - 9 Tests (Modul fehlte → rot). **8 Provokationen**, je rot: Kontaktabzug nur bei grünem Gate (Martins Fall) · erwartet nach Bytes (Stempel zählen) · Holo nur fürs eigene Schiff (3 rot) · Unerwartete nicht zuerst (2) · Bin nicht geprüft · fehlende Bilder nicht gezählt · neues Bild ohne Rückgriff aufs alte · Bin-Kopie nicht geleert (2). Bei der letzten blieb der Test zuerst grün, weil die Attrappe mit leerem `bin` startete: nachgeschärft (veraltete Datei in `bin`, wie bei einem schon gebauten Checkout).
   - **Lokaler Gate-Lauf** (Windows 11, SDK 10.0.404, App-Klon `v0.5.1` = `da48270` unter `cache/app-checkout`, Python 3.14.5 / numpy 2.5.3 / opencv 5.0.0.93): Seed `ships-2026.11` gegen den Dry-Run des Laufs vom 16.11. (`out/release`, gleiche Daten, nur Stempel anders). **0 Schiffe erwartet, 1 427 / 1 427 Bilder gleich, 0 anders, 0 fehlend, Platzierung 0 / 109 anders, grün.** Zeiten: Build 19,7 s + 2,5 s, Bildlauf alt 324,2 s, neu 170,1 s, gesamt **520 s**.
   - **Lokal ↔ Runner (Martins Hinweis, 18.11.):** Die Bild-Hashes des alten Laufs gegen S12.0-Lauf 3 A1 auf `windows-latest` (Artefakt `a1-csv`, nur Hashes, gleicher Stand v0.5.1 + holo-v3): **1 427 / 1 427 gleich, Platzierung 109 / 109 gleich.** Gleichheit ist damit gemessen, nicht nur erwartet.
6. **Block 8 – `ship-data.yml`.**
   - Jobs: `chain` (ubuntu-24.04, 150 min) → `gate` (windows-latest, 60 min, nur mit Entwurf) → `publish` oder `pr` (nur nach grünem Gate) · `publish-merged` (Push auf `state/pending.json`) · `heartbeat` (`always()`, nicht bei Dry-Run).
   - `permissions: {}` oben, je Job das Nötige; `persist-credentials: false` überall, wo nichts gepusht wird; `GH_TOKEN` nur in Steps mit `gh`.
   - Cache `models-<run>-<attempt>`, `restore-keys: models-`, nach `publish` geprunt unter `…-published`.
   - Artefakte `reports-<job>` nur mit Berichten. Der Gate-Job lädt `pictures.csv`/`values.csv` beider Läufe mit hoch, damit sich lokal ↔ Runner jederzeit vergleichen lässt (wie oben gegen S12.0).
   - Neu in `run.py`: `pins` (Outputs `appTag`, `runner`) und `verify --ci` (P7: Exit 2 → 0 mit `path=pr`); `diff` schreibt `changed`.
   - **Doku geprüft (A3, 18.11.):** `upload-artifact` README – „the least common ancestor of all the search paths will be used as the root directory“ (die Suchpfade zählen, nicht die gefundenen Dateien; `work/` und `out/` bleiben); `if-no-files-found: ignore`. `download-artifact` README – `pattern`, `merge-multiple`. Was bei keinem Treffer passiert, sagt sie nicht: im `heartbeat` deshalb `continue-on-error`. Die Actions-Pins stehen in `TOOLS.md`.
   - **`tests/test_workflow.py`** (7 Tests, zeilenweise, ohne YAML-Paket): Runner = `pins.json` · Secret genau einmal im Step `fetch` · jeder `run:` nur `run.py`/pytest/pip/npm, ohne Shell-Operatoren · Artefakte ohne Katalog/Schiffe/Holos/Bilder · Actions in `TOOLS.md` · Cron, `permissions: {}`, Timeout ≥ 90 · `publish`/`pr` nur nach grünem Gate. Dazu 5 Tests für `pins`/`--ci` und der Output `changed` im Ende-zu-Ende-Test.
   - **Provokationen:** 12, je rot. **Zwei blieben zuerst grün** und haben den Test geschärft:
     - (1) Ein `\1` hat den Weg PowerShell → WSL nicht überlebt und den Job gelöscht statt `runs-on` zu ändern – keine echte Provokation; neu über ein Python-Skript mit Argumentliste.
     - (2) `verify || [ $? -eq 2 ]` begann mit einem erlaubten Präfix, und ein `- run:` am Schrittanfang wurde nicht gelesen – Testlücke. Jetzt sind Shell-Operatoren verboten und `- run:` wird gelesen.
   - Suite: `164 passed in 107.98s`.
   - Nach dem Push: `gh workflow list` → „ship data“ **active**, 0 Läufe (ein Syntaxfehler hätte einen roten Lauf erzeugt). Cron ab jetzt aktiv (D3), nächster Termin 1.12., 04:23 UTC.
7. **Block 9 – Doku.**
   - `docs/decisions.md`: **SD10** (Entwurfs-Release als Ablage), **SD11** (Ergebnis eines Laufs: nichts / Release / PR / rot), **SD8-Addendum Dependabot** (E3; Vorschlag: keine automatischen Version-Updates, Sicherheitswarnungen an – zur Bestätigung).
   - `docs/provenance.md`: Motherlode-OpenAPI wörtlich (Quelle `cryon.rocks/developers`, gelesen 18.11. im Master-Chat), was daraus folgt; Ports `gate.py`, `sheet.py`; `tools/gate/` als entfernt.
   - `CLAUDE.md`: Diagramm (Entwurf, `publish-merged`, Gate rot, heartbeat), Domänenfakt „kein Modell-Endpunkt“, Releases-Zeile, Projektstruktur, Befehle.
   - `README.md`: Abschnitt „The monthly run“. `TOOLS.md`: Actions-Pins (Block 8).
8. **Block 11 – Seed-Release `ships-2026.11` (D1.1, P10), 18.11. 10:17 UTC.**
   - Frisch gebaut in WSL auf dem gepushten `1c727e6` (`release --seed … --catalog cache/catalogs/2026-11-16/raw`): 108 Schiffsdateien, 101 Holos, `orderKeys` für 104, 104 Assets – wie T12.1b.
   - Gegen den abgenommenen T12.1b-Seed: alle Holos und `ships.zip` **byte-gleich**; im Manifest nur `generatedAt` und `pipelineCommit` anders; `NOTICE.md` anders, weil `6bdfcd6` sie auf das flache Layout umgeschrieben hat (gewollt).
   - Repo-Einstellung gelesen: `immutable-releases` **aus** (die Hygiene kann alte Tags löschen); vorher 0 Releases.
   - Hochgeladen mit demselben Code wie im Workflow: `run.py draft --folder out/seed` (104 Assets, `manifest.json` zuletzt, nach dem Upload per `digest` geprüft, **18 s**), dann `run.py publish --tag ships-2026.11` (zweite Prüfung, `--draft=false --latest`). `--root` auf einen Scratch-Ordner, damit `publish` nicht den lokalen Modell-Cache prunt (die 22 Modelle vom 17.11. werden für Block 10 gebraucht).
   - **Von außen geprüft:** `…/releases/latest/download/manifest.json` HTTP 200, SHA `400d1181…` = lokal; `ships.zip` über `latest` byte-gleich; `orig-100i.holo` über `releases/download/ships-2026.11/` 93 794 B. Release: 104 Assets, **33 112 750 B**, kein Entwurf, kein Pre-Release, `Latest`, Ziel `1c727e6`. https://github.com/MRiediger/sc-cargoplan-shipdata/releases/tag/ships-2026.11
   - `run.py previous` gegen das echte Release: 104 Assets gegen das Manifest geprüft, nächster Name `ships-2026.11.1`.
9. **Block 10 – lokaler Durchlauf als Probe für Dispatch 1** (WSL, Pins; gesicherter Katalog vom 17.11. gegen das veröffentlichte `ships-2026.11`; **0 API-Rufe, 0 Seiten-GET, 77 Modell-GET**).
   - Zeiten: `fetch` 55 s (24 Modelle im Cache, 77 geholt, 0 nicht verfügbar) · `diff` 8 s · `build` **3 615 s** (98 Modelle, 0 fehlgeschlagen) · `verify` 5 s, **Exit 2**.
   - `diff`: 1 geändert (`f7c_hornet_mk_ii`), 1 neu (`hyun`), **8 neu verschwunden**. Gegen den Seed zählen 600i Executive und Cyclone als neu, weil der Seed aus der App kein `missingSince` trägt; ab dem nächsten Lauf sind sie „schon verschwunden“. 2 ohne Basis ≤ 3: kein Stopp. Modelle: 96 Re-Exporte, 2 neu, 1 ohne URL (Cyclone). Reihenfolge für 98 verglichen, 0 vertauscht.
   - `verify`: **2 Stopps, beide SD5 Fall 4** – `anvl-f7c-hornet-mk-ii` (Quellwechsel `fleetyards (holo-v1)` → `ANVL_Hornet_F7C_Mk2`) und `gama-hyun` (neu). **Kein Fall 1: keines der 79 bestehenden Holos kippt** (die offene Frage aus T12.1b). 31 Hinweise: 21 × Judge (Hausdorff wie gemessen, Corsair −0,0592), 6 × Variante folgt der Basis, 2 × `missingSince 2026-11-18`, 135c aus `overrides.json`, F7C ohne Reihenfolge-Vergleich. Holos: 98 gebaut, 11 byte-gleich → **87 erneuert**. Dateien gleich dem Vorgänger 4 / 111 (`source` neu in den übrigen, Auflage C).
   - **F7C:** Das Motherlode-Holo hat **5 743 Dreiecke** (Fleetyards 19 799, Budget 20 000), Hausdorff 0,0000, besteht – ein Fall für den Kontaktabzug.
   - `pr --dry-run`: Text wie geplant. **Befund:** `pr` nahm ein liegengebliebenes `gate.json` der Vormittags-Probe. Im Workflow unmöglich, trotzdem geschlossen (A6): `pr` nimmt `gate.json` nur, wenn `new` dem Tag entspricht, sonst „no gate result for …“. Test rot → grün, Provokation rot.
   - `release --dry-run`: **105 Assets, 32 748 815 B** (102 Holos mit `gama-hyun`).
   - **Lokales Gate, erster Versuch: rot – zu Recht.** 652 Bilder gleich, 788 anders, 91 Schiffe erwartet, **unerwartet: `aurora_mk_ii_ts_module`**. Die App setzt aus `aurora_mk_ii` und `ships/modules/ts_module.json` einen eigenen Eintrag zusammen (`ModuleDto.ConfigurationId`: `<schiff>_<modul>`), gerendert mit dem neuen Holo der Basis. `expected_ids` kannte nur Schiffsdateien. Ein Runner-Lauf wäre an genau dieser Stelle rot geworden. Behoben: Moduleinträge dürfen abweichen, wenn ihre Basis darf oder die Moduldatei (ohne Stempel) sich ändert. 2 Tests rot → grün, 2 Provokationen rot. Zeiten des roten Laufs: Bildlauf alt 188 s, neu 154 s, 16 Kontaktabzug-Blätter.
   - **Lokales Gate, zweiter Versuch: grün.** 92 Schiffe erwartet (mit `aurora_mk_ii_ts_module`), **1 440 Bilder** (1 427 + 13 für `hyun`): 652 gleich, 788 anders, 0 fehlend, Platzierung bei 26 anders, **0 unerwartet**; 351 s (Bildlauf alt 191 s, neu 155 s, Rebuild 1,2 s). 16 Blätter, Blatt 1 1,4 MB: `f7c_hornet_mk_ii [stop]`, `hyun [stop]` (alt: „no picture“), dann 100i, 125a, 300i, 315p … Sichtprüfung CC: F7C alt (Fleetyards) mit Anbauten an den Flügelspitzen, neu (Motherlode) schlanker, Rack 1 in beiden mittig; Re-Exporte mit bloßem Auge gleich.
   - Suite: `167 passed in 56.39s`.
10. **Dispatch 1 – Lauf 44296781671 (18.11., 11:40 UTC): rot im Job `pr`.** https://github.com/MRiediger/sc-cargoplan-shipdata/actions/runs/44296781671
   - `chain` **66 min** grün: 1 API-Ruf, 1 Seiten-GET, **101 Modell-GET** (Cache leer, erster Runner-Lauf), Katalog `4.10.3-LIVE.13165946`, `updatedAt 2026-11-16T11:36:30Z` (wie die Probe). `build` **3 663 s** (98 Modelle, 0 Fehler), `verify` 2 Stopps (F7C, `hyun`, Fall 4), Entwurf `ships-2026.11.1` mit 105 Assets.
   - `gate` **11 min** grün: Build alt 58 s, Bildlauf alt 259 s, neu 220 s; 96 Schiffe erwartet, 1 440 Bilder, 620 gleich, 820 anders, **0 unerwartet**; 16 Kontaktabzug-Blätter am Entwurf (121 Assets, 62 115 171 B).
   - **Lokal ↔ Runner, alter Stand: 1 427 / 1 427 Bilder gleich** (Erwartung von Martin bestätigt: Rendern ist plattformgleich).
   - **`pr` rot:** `gh pr create` scheitert, weil die Repo-Einstellung „Allow GitHub Actions to create and approve pull requests“ aus ist (`can_approve_pull_request_reviews: false`). Branch `data/2026.11` mit `pending.json` war gepusht, PR keiner. → **SD12**, Einstellung klickt Martin.
   - **Befund A16:** `github.gh` warf `CalledProcessError` ohne stderr – das Log sagte „exit status 1“, nicht warum. Jetzt `RuntimeError` mit der Meldung von `gh`/`git`. 2 Tests rot → grün.
   - **Befund YAML:** `reports-pr` und `reports-publish*` hatten nur Suchpfade unter `out/`; `upload-artifact` schneidet den gemeinsamen Vorfahren ab, `say-pr.jsonl` lag nach dem Download im Wurzelordner, und der Heartbeat schrieb „error in job pr: see the log“ statt des Grunds. Meine Lesart der README in Block 8 war richtig, nur der Fall „alle Pfade unter einem Ordner“ fehlte. Jetzt trägt jedes Berichts-Artefakt `tools/pins.json` als Anker. Test rot (5 Artefakte) → grün, Provokation (Anker nur aus `reports-pr` raus) rot.
   - Heartbeat lief korrekt: `state/last-run.json` mit `result: error`, Commit auf `main`.
   - **Befund Determinismus:** Gleiche Modelle (alle `rawSha256` gleich), gleiche Pins, beide Ubuntu 24.04 – und **4 von 98 Holos nicht byte-gleich** zwischen WSL und Runner (600i Explorer/Touring, Apollo Medivac, Hermes; ±6–50 B, Metriken auf 4 Stellen gleich, eine `errorM` 0,1000 → 0,1006). Lokal waren genau diese 4 byte-gleich zu holo-v3 (11 statt 7). Vermutlich Gleitkomma je CPU (SIMD). Wirkung: nur bei geändertem Modell (sonst baut der Lauf nicht) zählen sie als „erneuert“, und die App lädt 4 Holos neu; das Gate erwartet sie über den Holo-SHA. Kein Stopp → Backlog. `outlines.json` unterscheidet sich nur in `generatedAt`.
   - Neue Bilder lokal ↔ Runner: 1 408 / 1 440 gleich, die übrigen gehören zu diesen 4 Schiffen.
   - Suite nach den Fixes: `171 passed in 95.26s`.
11. **Dispatch 1, zweiter Anlauf – Lauf 44317285689 (18.11., 13:47 UTC): grün, PR-Pfad.** Einstellung aus SD12 von Martin eingeschaltet (`can_approve_pull_request_reviews: true`). https://github.com/MRiediger/sc-cargoplan-shipdata/actions/runs/44317285689
   - `chain` **88 min**: 1 API-Ruf, 1 Seiten-GET, **0 Modell-GET** (Cache-Treffer 101/101 aus Lauf 1). `build` **5 167 s** (Lauf 1: 3 663 s, gleiche Arbeit – Runner-Streuung +41 %; Timeout 150 min hält). Gleicher Katalog, gleiche Stopps (F7C, `hyun`, Fall 4), 105 Assets.
   - `gate` **11 min** grün: Build alt 39 s, Bildlauf alt 271 s, neu 228 s; 620 gleich, 820 anders, **0 unerwartet**, 16 Blätter.
   - `pr` 26 s: **PR #1** auf `data/2026.11`, ein Commit, nur `state/pending.json` (Manifest `94129864f3ca`). https://github.com/MRiediger/sc-cargoplan-shipdata/pull/1 – Tabelle mit beiden Stopps und Metriken, Gate-Zeile, 31 Hinweise eingeklappt.
   - `heartbeat`: `state/last-run.json` `result: pr`, Zeile **„PR #1: 2 findings“**; die `pr`-Zeilen sind jetzt im Heartbeat (Anker-Fix wirkt, `reports-pr/out/say-pr.jsonl`).
   - **Runner ↔ Runner:** alle 102 Holos byte-gleich zu Lauf 1, Bilder alt 1 427/1 427 und neu 1 440/1 440 gleich; Manifest-`files` nur in `outlines.json` (`generatedAt`) anders. Die 4 abweichenden Holos aus Befund 10 sind also maschinenabhängig, aber auf dem Runner reproduzierbar.
   - API-Rufe bisher: **2** (Lauf 1, Lauf 2).
12. **Merge PR #1 → `publish-merged`, Lauf 44339569545 (18.11., 15:46 UTC): grün, 1 min 25 s.** https://github.com/MRiediger/sc-cargoplan-shipdata/actions/runs/44339569545
   - Auslöser: Push des Merge-Commits `0a93d32` (`state/pending.json`); nur `publish-merged` und `heartbeat` liefen, die übrigen Jobs übersprungen. Martins Klicks bis hier: Einstellung SD12, Dispatch, Merge – kein „Approve workflows to run“ (P6 bestätigt).
   - `publish`: Entwurf gegen Manifest und `pending.json` geprüft, **16 Kontaktabzüge entfernt**, veröffentlicht als `latest`, Ziel und Tag = Merge-Commit. Hygiene: 2 Releases (`ships-2026.11.1`, `ships-2026.11`), **0 gelöscht**. Prune: 0 alte Hashes, Cache **51 999 876 B** (101 Modelle).
   - **Von außen ohne Anmeldung:** `…/releases/latest/download/manifest.json` HTTP 200, SHA `94129864f3ca` = `pending.json`; `ships.zip` 102 411 B, alle 111 Dateien gegen `files` gleich; `gama-hyun.holo` über `releases/download/ships-2026.11.1/` 268 668 B, SHA gleich. Release: **105 Assets, 32 748 772 B**, kein Entwurf, kein Pre-Release. Manifest: `dataVersion ships-2026.11.1`, `schemaVersion 6`, `pipelineCommit fadc771`, `missingSince 2026-11-18` für 600i Executive und Cyclone, 6 Varianten mit `follows`. https://github.com/MRiediger/sc-cargoplan-shipdata/releases/tag/ships-2026.11.1
   - `heartbeat`: `state/pending.json` entfernt, `result: release`, Zeile **„Release ships-2026.11.1: 1 ship changed, 1 new, 8 gone, 91 holos refreshed“**. Der Bot-Push löste keinen Lauf aus (keine Schleife).
13. **Dispatch 2 – Lauf 44340334581 (18.11., 15:50 UTC): grün, „nothing changed“, 2 min 04 s.** https://github.com/MRiediger/sc-cargoplan-shipdata/actions/runs/44340334581
   - `chain` **91 s**: 1 API-Ruf, 1 Seiten-GET, 0 Modell-GET (101 im Cache); Katalog unverändert (`updatedAt 2026-11-16T11:36:30Z`). `previous`: `ships-2026.11.1` (höchste Version, 105 Assets gegen das Manifest geprüft).
   - `diff`: 0 geändert, 0 neu, **0 neu verschwunden, 8 schon verschwunden** (D2 wirkt: `missingSince`/`follows` aus `.1` zählen nicht mehr), 0 wieder da, 0 Modelle geändert, Reihenfolge für 100 verglichen (F7C jetzt mit `orderKeys`), 0 vertauscht → `changed=false`.
   - `build`, `verify`, Entwurf, `gate`, `publish`, `pr` übersprungen; Releases unverändert (`.1` latest, Seed).
   - `heartbeat`: Commit `db15e0e` „data: heartbeat 2026-11-18 - nothing changed“, `result: nothing`.
   - Suite zum Abschluss: `171 passed in 55.53s` (WSL, Pins).
   - **API-Rufe in T12.2: 3** (Dispatch 1 zweimal, Dispatch 2) – Obergrenze aus D1 eingehalten, keiner aus der Session.

**Akzeptanz (D1) erfüllt:** Seed `ships-2026.11` (Befund 8) · Dispatch 1 → PR #1 mit Befund je Stopp, Kontaktabzug am Entwurf (11) · Merge → `ships-2026.11.1` aus dem Merge-Commit, Hygiene 2 Releases (12) · Dispatch 2 → „nothing changed“, Lebenszeichen, kein Release (13).

**Offen außerhalb dieses Tasks:** SD8-Addendum Dependabot wartet auf Bestätigung im Master-Chat; SD12 (Einstellung an) ist mit Martins Klick ratifiziert.

**Das ändert sich an T12.3–T12.6:**
1. **T12.3 (Datenkanal):** `releases/latest` ist **`ships-2026.11.1`**, ein echter Lauf – nicht der Seed. Die App sieht beim ersten Check sofort ein Update gegenüber v0.5.1: 1 Schiff neu (`hyun`), F7C mit Motherlode-Holo, 8 verschwundene mit `missingSince`/`follows` im Manifest. Die Akzeptanz am Aufzug testet damit einen echten Datensprung, kein Nullupdate. Das Manifest hat 111 Dateien in `files`, `ships.zip` 102 411 B.
2. **T12.4 (Holo aus dem Manifest):** Akzeptanz „Holo-Dateien aus `ships-*` byte-gleich zu holo-v3“ gilt nur für den Seed `ships-2026.11`. In `.1` sind **91 Holos erneuert** (Motherlode-Re-Export). Neu: Holo-Datei byte-gleich zu `holo.ships.<slug>.sha256` des Manifests; der Vergleich mit holo-v3 nur gegen den Seed. Kontaktabzüge (`contact-sheet-*`) stehen nie im veröffentlichten Release (`publish` löscht sie) – die App darf keine Assets außer Manifest, `NOTICE.md`, `ships.zip`, `<slug>.holo` erwarten.
3. **T12.5 (Baseline aus dem Release):** Mit dem Env-Override in `ShipPictureTests` (S12.0 E3) entfallen im Gate Tausch, `bin`-Leeren, Rebuild und Bin-Prüfung (`gate.swap`, `bin_problems`, ein Rebuild) – dann `appTag` in `tools/pins.json` auf das App-Release mit Override heben und `gate.py` vereinfachen. Die erwarteten Moduleinträge (`<schiff>_<modul>`) bleiben. Die App-Baseline wird `.1` (oder neuer), nicht der Seed: Die Bild-Baselines im App-Repo ändern sich für ~96 Schiffe.
4. **T12.6 (Release):** „Erstes Data-Release `ships-2026.11` per Knopf“ und „erster echter Monatslauf per Knopf“ sind erledigt (Seed, Dispatch 1/2). Bleibt: App v0.6.0, Wiki, README beider Repos, `sc-ship-outlines` archivieren. Der Cron läuft seit T12.2 (D3), erster geplanter Lauf **1.12., 04:23 UTC** – **Sciirofs Freigabe für den Monatslauf steht weiter aus** (CLAUDE.md). Mit Branch + `--no-ff` ab T12.6: Branch-Protection mit Pflicht-Review macht SD12 neu prüfenswert, und `ci.yml` (Backlog) wird nötig.

### [x] T12.3 App: Datenkanal (im App-Repo, erledigt 18.11.2026: `9e3c620`…`12a16d2`, D112)

**Warum:** Ohne Leser ist das Release wertlos.
- Manifest-Check nach dem Velopack-Check (eine URL `…/releases/latest/download/manifest.json`), `schemaVersion`-Prüfung (unbekannt → „Ship data needs app update“)
- Notice-Zeile mit Update/Skip, Download nur `manifest.json` + `ships.zip` (`assets.ships`, SD4), Prüfung gegen `files`, atomarer Tausch unter `%LocalAppData%\SC-CargoPlan\ships\<version>\`, Reload ohne Neustart
- Plan-Verträglichkeit: geänderter Rack-Satz → „re-plan recommended“
- Settings „Ship data“ (`shipData.checkOnStartup`, `skippedVersion`), CLI `ships --version`
- Netzzugriff 3 → eigener D-Eintrag (CLAUDE.md der App)

**Akzeptanz:** Gate am Aufzug, SC im Vordergrund: Update einspielen, Galaxy erscheint, Holo lädt, Plan bleibt.

### [x] T12.4 App: Holo aus dem Manifest (im App-Repo, erledigt 18.11.2026: `06170bc`/`a8c4900`, D114)

**Warum:** `HoloRelease.Tag` ist die letzte Konstante, die ein App-Release pro Datenänderung erzwingt.
- Hashes aus dem Manifest, URL `…/releases/download/<dataVersion>/<file>` (kein `baseUrl`, SD2), `holo: null` → Umriss-Fallback, gelöschtes Release → Baseline-Holo
- Cache-Wechsel nach D95-Muster, Migration für v0.5.x-Caches

**Akzeptanz:** Holo-Dateien aus `ships-*` byte-gleich zu holo-v3 (S12.0: Schwelle 0); Holo-Download aus `ships-*` statt `holo-v3`.

### [x] T12.5 App: Baseline aus dem Release (im App-Repo, erledigt 18.11.2026: `46fd06d`/`39c3a50`, D113)

**Warum:** Eine Quelle für Schiffsdaten; `ships/` als Quelltext im App-Repo ist der zweite Pfad, der v0.5.1 teuer machte.
- `release.yml` lädt das aktuelle `ships-*`-Release ins ZIP, Tag im Manifest; `ci.yml` gegen eine feste Baseline
- `ships/`, `outlines/`, `tools/import-motherlode.ps1`, `ShipJson.ps1` raus; `ShipPictureTests` liest Daten per Env-Override (S12.0 E3)
- NOTICE und README anpassen

**Akzeptanz:** Publish-Build lokal startet offline mit der Baseline; `git ls-files ships/` ist leer.

### [x] T12.6 Release (erledigt 19.11.2026; aufgeteilt in T12.6a im App-Repo und T12.6b hier)

**Warum:** Erst ein echtes Data-Release, dann die App, die es liest, dann der erste Monatslauf.
- [x] Erstes Data-Release `ships-2026.11` per Knopf (= Stand 4.10.3 / holo-v3) – Seed, T12.2 Befund 8 (18.11.)
- [x] Erster echter Monatslauf per Knopf – Dispatch 1 → PR #1 → `ships-2026.11.1` (Läufe 44317285689, 44339569545), Dispatch 2 „nothing changed“ (44340334581); T12.2 Befund 11–13
- [x] **App:** v0.6.0 mit der Baseline `ships-2026.11.1`, Wiki, README, Notes – App-T12.6a, Merge `b2dc6d6`, Tag `v0.6.0` (19.11.), Netz-Gate bestanden
- [x] README dieses Repos, `sc-ship-outlines` archivieren → T12.6b (unten); `holo-v3` im App-Repo bleibt bis 31.01.2027 (App-D63-Addendum)

**Akzeptanz:** Netz-Gate, SC im Vordergrund: v0.5.1 → v0.6.0 per Velopack – bestanden (App-T12.6a, 19.11.). Das Data-Update im Overlay entfiel für v0.6.0 (Latest = Baseline, keine Ship-data-Zeile); den Kanal hat das T12.3-Gate belegt. Ab hier Branch + `--no-ff` für jede Änderung an diesem Repo.

### [ ] T12.6b Shipdata-Abschluss (Plan freigegeben 19.11.2026 mit R1–R5, K1, E1, E2, `docs/plans/T12.6b-abschluss.md`, Branch `docs/p12-close`)

**Warum:** Phase 12 ist technisch fertig; offen sind ein README für den 1.12. und den ersten PR, die erledigten Tasks, die Lehren der Phase, ein Backlog mit Anlässen und die Klicks, die nur Martin machen kann. Kein Code, kein Lauf, kein API-Ruf.
- README; T12.3–T12.6 abhaken; Lehren; Backlog konsolidiert (inkl. Sciirofs Antwort vom 18.11.); SD13; SD3-Addendum; `cache/`-Hygiene; Martin-Klicks

**Präzisierung in der Planphase, ratifiziert durch Freigabe:**
1. **R1** SD3-Addendum: 4 Holos CPU-Rundung (Gate erwartet sie über den Holo-SHA) und `appTag` > v0.5.1 braucht den Gate-Umbau (Befund 1).
2. **R2** Keine Schiffsdatei-PRs in diesem Repo (es hat kein `ships/`, jede Datei entsteht monatlich neu); README sagt das. Die Korrektur der App-Doku geht an die App-Doku-Session (Martin-Klick 4).
3. **R3** Sciirof „is totally happy“ mit dem Monatslauf (Antwort 18.11.): CLAUDE.md-Zeile angepasst, Backlog „zieht die Freigabe zurück“.
4. **R4** `NOTICE.md` in `files`: Anlass „nächste Manifest-Formatänderung“; „Legenden-Warnzeilen“ gestrichen (App-Backlog).
5. **R5** „override obsolete“ als Backlog, Anlass „Lauf stoppt wegen Quellwechsel 135c (SD5 Fall 4)“. **K1** Manifest-Zeile 135c gezeigt (Befund 2).
6. **E1** „Gate lokal“ als Anlass an der bestehenden Lehre, keine neue Zeile. **E2** `missingSince` getrennt für Cyclone und 600i EE (Befund 3).
7. Zwei der Lehren aus dem Auftrag standen schon („Katalog-Rettung war Zeremonie“, „Kein Startprompt ohne Regeln“); sie bleiben, kein Duplikat.

**T12.6b Befund (19.11.2026):** 0 API-Rufe, 0 Workflow-Läufe, 0 Modell-GET. Commits `8bb42d5` (Plan), `b1e4d29` (README), `f4467d1` (SD13, SD3), dieser Commit (TASKS, CLAUDE.md).
1. **`appTag` > v0.5.1 braucht den Gate-Umbau.** `gate.py` tauscht die Daten in `app/ships` und `app/outlines/ship-outlines.json` des Checkouts; seit App-v0.6.0 gibt es `ships/` im App-Repo nicht mehr. SD3-Addendum, Backlog „Gate auf `CARGOPLAN_SHIP_DATA`“.
2. **Regel „override obsolete“ fehlt.** `rules.import_findings` liest `overrides.json` nur bei Status `kept`; liefert der Katalog eine Transform, bleibt der Eintrag still stehen. Ein Stopp kommt trotzdem über SD5 Fall 4, nur mit dem Grund „Quellwechsel“ – **K1**, veröffentlichtes Manifest `ships-2026.11.1` (SHA `94129864f3ca`): `ships.135c` `source` „Fleetyards API (CIG ship matrix), export 2026-10-22“, `missingSince null`, `orderKeys null`; `holo.ships.orig-135c.model` **„fleetyards (holo-v1)“** ≠ `ORIG_135c`, also kein vergleichbarer Vorgänger.
3. **E2, Markierung im Manifest:** `600i_executive_edition` `source` Fleetyards, **`missingSince 2026-11-18`**, `follows null`, Holo-`model` „fleetyards (holo-v1)“ – sie zählt als verschwunden, obwohl sie nie ein Motherlode-Modell hatte; die „> 3 Läufe“-Regel träfe sie nach dem 1.02.-Lauf, gemeint ist aber Sciirofs Antwort. `cyclone` `source` Motherlode 4.10.2, `missingSince 2026-11-18`, Holo-`model` `TMBL_Cyclone`.
4. **Schiffsdatei-PRs:** App-CONTRIBUTING, `docs/ship-format.md` (Abschnitt zum PR, Überschrift „The three Fleetyards ships“) und `ship-correction.yml` versprechen einen PR mit JSON-Datei in `ships/` dieses Repos; das gibt es nicht (R2).
5. **SD12** steht in `decisions.md` (unverändert). SD9 steht hinter SD12 – bleibt so (Geschichte).
6. **`cache/`-Hygiene:** `spike/` existiert nicht mehr (damit auch `spike/rescue-cert.pem`); `git ls-files '*.pem'` leer; `git check-ignore -v` → `.gitignore:10:cache/` für `cache/rescue/key.pem` und `cache/app-checkout` – bleiben lokal.
7. **Repo-Einstellungen gelesen** (`gh api`, 19.11.): Shipdata `delete_branch_on_merge: false`, `has_issues: true`; `sc-ship-outlines` `archived: false`, privat. Remote-Branch `data/2026.11` (PR #1, gemergt) liegt noch.
8. **pytest** komplett (WSL, Pins, `tools/local-wsl.sh test`, auf `f4467d1` + TASKS-Entwurf): `============================= 171 passed in 53.74s =============================` – Docs-only, Zahl wie zum Abschluss von T12.2.

**Martin-Klicks:**
1. `sc-ship-outlines` archivieren: Settings → General → Danger Zone → **Archive this repository**.
2. Shipdata-Repo: Settings → General → Pull Requests → **Automatically delete head branches**; danach in PR #1 **Delete branch** für `data/2026.11` (die Einstellung wirkt nicht rückwirkend) und die Backlog-Zeile „`data/*`-Branch löschen“ streichen.
3. **Nachricht an Sciirof** (Entwurf, Englisch):
   > Hi Sciirof, thanks again for being happy with the monthly run – it is live now: the first run on 1 December at 04:23 UTC calls `/cargo-grids` once and builds from it, and the data reach SC-CargoPlan v0.6.0 as a monthly release. Two things I'm looking forward to from your answer: the model URL in the `/cargo-grids` response (could you tell me the field name once it's there? I'll read it next to the page for a month, then drop the page scraper) and the transform for the 135c (the pipeline will stop and ask me when it arrives, so nothing changes silently). The one model I'm still missing is the **600i Executive Edition** – it is the last ship we still take from Fleetyards. And if you prefer wrong-grid reports to reach you in a particular way, tell me and I'll point people there.
4. **App-Doku-Session** (R2): CONTRIBUTING „Correct ship data“, `docs/ship-format.md` (PR-Abschnitt, Überschrift „The three Fleetyards ships“) und `ship-correction.yml` auf „Issue statt Schiffsdatei-PR, wir melden an Motherlode“ ziehen; dazu dort T12.6b abhaken und Phase 12 schließen.

**Akzeptanz:**
- [ ] README beantwortet in zwei Minuten „was passiert am 1.12.“ und „was mache ich, wenn ein PR kommt“ – Martin liest einmal gegen
- [ ] TASKS.md: Phase 12 geschlossen, Backlog mit Anlässen, keine offenen `[ ]` außer Backlog
- [ ] Merge `--no-ff` nach Freigabe, Push durch CC (Shipdata-Regel)

---

## Lehren

Regeln aus Fehlern, die durchgerutscht sind. Gelten für jeden Task. Übernommen aus `sc-cargoplan`, soweit sie hier treffen.

- **Vor jedem Push `gh run list -L 3`.** Rote Läufe erst klären, dann pushen.
- **Tests vor der Implementierung heißt: erst rot sehen.**
- **Mess- und Gate-Befehle selbst einmal laufen lassen, bevor Martin sie bekommt.** Hier: jeden Workflow einmal per Dispatch selbst lesen, bevor er als fertig gilt – und das Gate erst lokal, dann auf dem Runner. Anlass T12.2 Block 10: Der lokale Gate-Lauf war rot an `aurora_mk_ii_ts_module` (Moduleintrag der App, den `expected_ids` nicht kannte); ein Runner-Lauf wäre genau dort rot gewesen.
- **Fremd-Framework zuerst als Spike mit Gates am echten Layout** (S11.0). Hier: S12.0 vor jedem Prod-Code.
- **Bei fremden CLIs heißt „leer“ oft „nicht gesetzt“.** Gilt für `gh`, `actions/cache`, `setup-python`.
- **Ein Skript für lokal und CI.** `run.py` ist der einzige Einstieg; `ship-data.yml` ruft nur Unterbefehle.
- **Handlauf ist ein Befund.** Anlass v0.5.1: ein halber Tag für drei Schiffe. Jeder Schritt, der einen Menschen braucht, bekommt eine Zeile hier, bis er weg ist.
- **Kein Startprompt ohne Regeln.** Anlass 17.11.: Die erste CC-Session in diesem Repo lief ohne CLAUDE.md und TASKS.md und hat sich ihre Regeln selbst gegeben. Jedes neue Repo bekommt beide Dateien **vor** der ersten Session.
- **Jede Regel einmal provozieren, nicht nur rot durch fehlenden Code.** Anlass 17.11. (T12.1): Zwei von 14 Tests blieben grün, obwohl die Regel kaputt war. Beim 404-Test fing die Hash-Prüfung denselben Fall ab; beim Key-Test glich der Alt-Key zufällig der Ableitung.
- **Katalog-Rettung war Zeremonie.** Anlass 17.11. (T12.1): ein eigener Workflow, `openssl cms`-Verschlüsselung und ein Artifact, um einen Katalog aus dem Actions-Cache zu holen. Ein lokaler API-Ruf hätte dasselbe geliefert. Die Regel heißt „API **einmal pro Lauf**“, nicht „nie“: ein lokaler Ruf ist ein Lauf und billiger als jeder Rettungs-Workflow.
- **Keine Logik in YAML-Schritten.** Anlass 17.11. (S12.0): zwei rote Läufe – ein ungepinntes Runner-Image und Inline-Code, der vor dem Runner nie gelaufen war. Workflow-Schritte rufen Skripte; die Skripte laufen vorher lokal in WSL Ubuntu 24.04 mit denselben Pins.
- **Text über Shell-Grenzen als Datei oder Argumentliste, nie als Heredoc.** Anlass T12.2 Block 8: Eine Provokation ging PowerShell → `wsl` → bash, das `\1` überlebte den Weg nicht, und der Ersatz löschte einen Job statt `runs-on` zu ändern – die Provokation war keine. Muster: Python-Skript mit Argumentliste; Commit-Messages per `git commit -F <datei>`.
- **Repo-Einstellungen in der Probe lesen, nicht nur Code.** Anlass T12.2 Dispatch 1: rot in `gh pr create`, weil „Allow GitHub Actions to create and approve pull requests“ aus war (SD12); die lokale Probe hatte nur `immutable-releases` gelesen. Jede Einstellung, auf die ein Job baut, steht im README und wird vor dem ersten Lauf per `gh api` gelesen.
- **Byte-gleich über Maschinen ist kein Gate; hash-gleich im selben Job schon.** Anlass T12.2 Befund 10: gleiche Modelle, gleiche Pins, beide Ubuntu 24.04 – und 4 von 98 Holos zwischen WSL und Runner ±6–50 B anders. Die Bilder des Gates entstehen beide im selben Job und sind dort hash-exakt (SD3, Addendum T12.6b); ein Vergleich gegen eine Datei von einer anderen Maschine wäre an diesen 4 rot geworden.

---

## Backlog (nur bei Bedarf)

Kein Plan, sondern Reaktion: wird erst zum Task, wenn der Anlass eintritt.

Konsolidiert in T12.6b (19.11.2026). Jede Zeile: **was** – Anlass – Herkunft.

**Quelle Motherlode (Sciirof)**
- **Modell-URL aus der `/cargo-grids`-Antwort** (ersetzt „Modell-Endpunkt“): `fetch` liest das Feld, wenn es da ist, sonst die Seite; die Summary zählt „from API / from page“; einen Monat beides, dann Scraper raus (SD-Eintrag). – **Anlass:** das Feld erscheint in der API (Feldname unbekannt, Task erst dann). – Sciirof 18.11.
- **Regel „override obsolete“:** liefert der Katalog eine Transform für ein Schiff aus `overrides.json`, endet der Lauf mit Stopp → PR „override obsolete“, der den Eintrag entfernt; nie still. Test, einmal provoziert rot. Heute fehlt die Regel (`rules.import_findings` liest `overrides.json` nur bei `kept`), der Stopp käme nur über SD5 Fall 4 mit dem Grund „Quellwechsel“. – **Anlass:** ein Lauf stoppt wegen Quellwechsel 135c (SD5 Fall 4; Holo-`model` heute „fleetyards (holo-v1)“, T12.6b Befund 2). – Sciirof 18.11. (135c-Transform angekündigt)
- **600i Executive Edition** (`missingSince 2026-11-18`, Fleetyards-Daten, nie ein Motherlode-Modell): mit Modell läuft sie wie die F7C (SD5 Fall 4 → PR); die „> 3 Läufe“-Regel unten gilt für sie nicht. – **Anlass:** Sciirofs Antwort zum Modell (Nachricht T12.6b, Martin-Klick 3). – T12.6b Befund 3
- **Cyclone** (`missingSince 2026-11-18`, Motherlode 4.10.2): kommt sie zurück, deckt SD6 „wieder da“ es ab, kein Task. – **Anlass:** 3 Läufe ohne sie (nach dem Lauf am 1.02.2027) → Entscheidung Martin wie unten. – Sciirof 18.11.
- **Ein Schiff > 3 Läufe `missingSince`** → Zeile hier, Entscheidung Martin: behalten oder aus dem Manifest nehmen. – **Anlass:** der vierte Lauf ohne das Schiff. – SD6
- **Seite `cryon.rocks/ops/cargo` ändert sich** → Pipeline meldet PR „model URLs unavailable“, letzter Stand bleibt (A11). – **Anlass:** der PR kommt. – S12.0
- **Sciirof zieht die Freigabe des Monatslaufs zurück** (erteilt 18.11.: „totally happy“) → Cron raus, Dispatch-only, Martin drückt den Knopf; Zielbild bleibt. – **Anlass:** seine Nachricht. – T12.6b R3
- **Holo-Kill-Switch** (CIG oder Sciirof sagt Stopp): `holo: null` im nächsten Release, Assets der letzten zwei Releases löschen. – **Anlass:** die Ansage. – SD2

**Gate und Pins**
- **Gate auf `CARGOPLAN_SHIP_DATA`** statt Tausch in `ships/`/`outlines/` des App-Checkouts (S12.0 E3, seit App-v0.6.0 möglich): `gate.swap`, `bin_problems` und ein Rebuild fallen weg, die Moduleinträge bleiben. – **Anlass:** der nächste Gate-Umbau, spätestens jeder `appTag` > v0.5.1 (SD3-Addendum T12.6b). – T12.2 „ändert sich an T12.5“
- **4 Holos CPU-Rundung** (geschärft aus „Holo-Kette CPU-unabhängig byte-gleich“): 4 / 98 Holos weichen zwischen WSL und Runner um ±6–50 B ab, Metriken gleich; erst messen, wo die Kette auseinanderläuft (Flatten, Cull, Export). – **Anlass:** Release-Churn stört (Holos „erneuert“ ohne Modelländerung) oder der Judge kippt auf einer Rundung. – T12.2 Befund 10, SD3-Addendum
- **Matrix/Parallelität der Kette.** Heute `build` 61 min (Lauf 1) bis 86 min (Lauf 2, Runner-Streuung +41 %), Job-Timeout 150 min. – **Anlass:** `build --all` > 100 min. – T12.2 Befund 10/11
- **Werkzeug-Pin-Bump** (Python, Node, numpy, OpenCV, meshoptimizer, Runner): eigener Task mit `build --all` und Messung, nie nebenbei (README „Pins and pin bumps“). – **Anlass:** Sicherheitswarnung (SD8-Addendum) oder `ubuntu-24.04` läuft aus. – SD8
- **WSL-Werkzeuge unter `/root` (fragil).** Der WSL-Standardbenutzer wechselte in T12.1 von `root` auf `artiniediger`; die Werkzeuge liegen unter `/root/s12tools`, `local-wsl.sh` läuft nur mit `wsl -u root` und braucht den `safe.directory`-Umweg. Reaktion: Werkzeuge unter den Standardbenutzer (`SHIPDATA_TOOLS`) neu aufsetzen. – **Anlass:** es hakt wieder. – T12.1

**Format und Vertrag**
- **`NOTICE.md` in `files`** des Manifests (heute nur ZIP-Inhalt; `NOTICE.md` ist Asset ohne Hash im Vertrag). – **Anlass:** die nächste Manifest-Formatänderung (SD2-Addendum). – T12.6b R4
- **Holo-Formatwechsel** = `holo.formatVersion` hochzählen + SD-Eintrag, **kein** `schemaVersion`-Bump (SD13). – **Anlass:** ein neues Holo-Format. – App-T12.4 R1

**Repo und Abläufe**
- **`ci.yml`** – `pytest` auf `pull_request` (und Push), getrennt vom Datenlauf; heute läuft `pytest` nur im Job `chain` von `ship-data.yml`. – **Anlass:** der erste Code-PR. – T12.2 E2
- **Pin-Bump-PR ins App-Repo aus der Pipeline:** nach einem Release öffnet die Pipeline im App-Repo einen PR auf `build/ship-data.json` (braucht ein Token mit Rechten dort). – **Anlass:** der zweite Monat mit Release. – App-T12.5
- **`data/*`-Branch nach dem Merge löschen.** – **Anlass:** entfällt, sobald Martin „Automatically delete head branches“ klickt (T12.6b Martin-Klick 2) → Zeile streichen. – T12.2 PR #1
- **PAT oder GitHub App für den PR-Pfad** statt der Repo-Einstellung aus SD12 (die erlaubt Workflows auch das Approven). – **Anlass:** Branch-Protection mit Pflicht-Review auf `main`. – SD12
# TASKS – SC-CargoPlan Ship Data

Regeln: **ein Task pro Session**, Reihenfolge einhalten. Jeder Task hat eine „Warum“-Zeile und prüfbare Akzeptanzkriterien. Jeder Task beginnt mit einem Plan in `docs/plans/` und stoppt bis zur Freigabe aus dem Master-Chat. Erledigt → `[x]`.

Session-Start-Prompt für Claude Code:
> Lies CLAUDE.md und TASKS.md. Wir machen Task **Tx.y**. Fass den Task zusammen, schreib den Plan nach `docs/plans/`, committe, pushe, stopp.

Einstieg der App-Seite: `sc-cargoplan/TASKS.md`, Abschnitt „Phase 12“. Tasks mit Präfix **App:** laufen dort, in diesem Repo steht nur die Schnittstelle.

---

## Phase 12 – Ship data channel (gestartet 16.11.2026)

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

### [ ] T12.0 Doku

**Warum:** Zwei Repos brauchen einen gemeinsamen Vertrag, bevor Code entsteht; die Spike-Befunde müssen in den Plan.
- `docs/decisions.md` hier: SD1 „Zwei Repos“ (Kontext, Gegenargument: zwei Arbeitsordner, Cross-Repo-Gate), SD2 Manifest-Format, SD3 Gate-Verfahren aus S12.0, SD4 Release-Reihe `ships-YYYY.MM[.N]`, Pre-Release aus, letzte zwei bleiben
- `docs/manifest-format.md` (Felder aus S12.0 Frage 5, `schemaVersion`-Vertrag, `holo: null`). Zusätzlich zu `builtFrom.tools`: **`pipelineCommit`** (Git-SHA der Pipeline). Ohne ihn ist ein Holo nicht reproduzierbar; holo-v3 führt ihn schon (`e6943af`).
- SD-Eintrag **„actions/cache und Fork-PRs“** (S12.0 E1) als eigene Entscheidung: Workflows aus Fork-PRs können den Cache des Default-Branch lesen. Optionen: Katalog nicht cachen, oder Fork-PR-Workflows abschalten. Gegenargument und Konsequenz wie bei SD1–SD4.
- `TOOLS.md` bereinigt, Pins aus dem Spike bestätigt
- **App:** D-Eintrag (nächste freie Nummer) „Ship data channel“ mit Zielbild, Verweis auf SD1–SD4; Phase-12-Abschnitt in `sc-cargoplan/TASKS.md` mit T12.3–T12.6; Kollision „P12 Look“ auflösen
- Spike-Befunde in diesen Task-Schnitt einarbeiten (Reihenfolge, Gates, Anker-Umzug)

**Akzeptanz:** Freigabe aus dem Master-Chat; beide Repos zeigen dieselbe Task-Nummerierung und denselben Manifest-Vertrag.

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

### [ ] T12.2 Workflow `ship-data.yml`

**Warum:** Der Lauf ohne Martin. Alles, was heute Zuruf ist, steht danach im YAML oder in `run.py`.
- cron `23 4 1 * *` + `workflow_dispatch` (Input `dry-run`), `permissions: contents: write, pull-requests: write`
- Cache nach Modell-SHA (Katalog nicht im Cache, S12.0 E1), Secret nur im Fetch-Step
- Diff → kein Unterschied: Lebenszeichen-Commit `state/last-run.json`, Ende
- Gate-Job `windows-latest`: Checkout `sc-cargoplan` auf gepinntem Tag (in `TOOLS.md`), beide Stände im selben Job (S12.0 K1)
- Release-Pfad: `gh release create ships-YYYY.MM[.N]`, Assets, Hygiene (letzte zwei bleiben)
- PR-Pfad: Branch `data/YYYY.MM`, Befund als PR-Text, Kontaktabzug als Artefakt; nach Merge Release aus dem Merge-Commit
- ~~`spike.yml` und `spike/` löschen~~ – in T12.1 erledigt (Präzisierung 13); Gate-Skripte aus `tools/gate/`

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
- **Jede Regel einmal provozieren, nicht nur rot durch fehlenden Code.** Anlass 17.11. (T12.1): Zwei von 14 Tests blieben grün, obwohl die Regel kaputt war. Beim 404-Test fing die Hash-Prüfung denselben Fall ab; beim Key-Test glich der Alt-Key zufällig der Ableitung.
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
# Entscheidungen

Architekturentscheidungen der Schiffsdaten-Pipeline mit ihren Abwägungen, nummeriert in der Reihenfolge, in der sie fielen
(SD1…). Eine Entscheidung ändert sich nur durch einen neuen Eintrag oder ein Addendum. Entscheidungen der App bleiben in
`sc-cargoplan/docs/decisions.md` (D1…); der Datenkanal steht dort als D111.

## SD1 – Zwei Repos: dieses baut und veröffentlicht, `sc-cargoplan` liest

- **Kontext:** v0.5.1 brauchte einen halben Tag Handarbeit für drei neue Schiffe: vier Skripte in zwei Repos (`sc-ship-outlines`, `sc-cargoplan`), Zustand nur in lokalen Dateien, jede Datenänderung ein App-Release.
- **Optionen:** alles im App-Repo (Workflow + Daten-Releases dort); eigenes Daten-Repo; Daten im App-ZIP lassen und nur den Import automatisieren.
- **Entscheidung:** **Eigenes öffentliches Repo `sc-cargoplan-shipdata`.** Es holt, baut, prüft und veröffentlicht die Daten als Release `ships-YYYY.MM[.N]`; die App liest nur das Release (T12.3) und zieht beim Build die Baseline (T12.5). Die Schnittstelle ist `manifest.json` (SD2).
- **Gegenargument:** Zwei Arbeitsordner, zwei TASKS.md, Aufgaben mit Präfix **App:** laufen drüben. Das Gate muss das App-Repo auf einem gepinnten Tag auschecken (Cross-Repo-Gate, SD3), und ein Schema-Bump braucht beide Repos zugleich.
- **Konsequenz:** Im App-Repo wären die monatlichen Daten-Releases Teil des 10er-Fensters von Velopacks `GithubSource` (App-D109, R10) und könnten das letzte App-Release verdrängen; hier stören sie nicht. CIG-Material (Holos) liegt nur in Release-Assets dieses Repos (NOTICE), der Code bleibt MIT. `sc-ship-outlines` wird mit T12.6 archiviert.

## SD2 – Manifest-Format: `manifest.json` ist der Vertrag zwischen Pipeline und App

- **Kontext:** S12.0 Frage 5 hat gemessen, welche Felder ein Lauf braucht: `appTag`, `source`, `missingSince` im Entwurf; es fehlten `model {className, sha256}`, `builtFrom.motherlode` mit `updatedAt` (Re-Export ohne Build-Wechsel), `builtFrom.tools`, `holo.formatVersion`, je Holo `bytes` und `sha256`. T12.1 hat den Entwurf geschrieben (Seed: 108 Schiffe, 101 Holos; `release --dry-run` 213 Dateien, 33 259 967 B).
- **Entscheidung:** **`docs/manifest-format.md` ist ratifiziert.** Zusätzlich zum T12.1-Entwurf: **`ships.<id>.orderKeys`** (D2, 18.11.) – die Grid-Reihenfolge je Schiff als `Größe@x,y,z` in Katalog-Reihenfolge, ein abgeleiteter Wert wie `racksSha256`. Damit prüft `diff` die Reihenfolge gegen das Manifest, `--previous-catalog` entfällt. **`assets {"ships": "ships.zip"}`** (D3, SD4); die Pfade in `files` sind die Pfade im ZIP. **`holo.baseUrl` ist gestrichen:** jedes Release trägt alle Holos, die URL ist `releases/download/<dataVersion>/<file>`; so liest T12.4 sie.
- **Gegenargument:** Ein Manifest, das zugleich Index, Zustand (Zähler, `missingSince`) und Judge-Archiv ist, wird groß und ist schwer von Hand zu lesen; ein Formatfehler trifft alle Leser. OrderKeys im Manifest machen das Manifest zum Gedächtnis der Pipeline – fehlt ein Release, fehlt der Vergleich.
- **Konsequenz:** Kein Zustand in Extradateien (CLAUDE.md, NIEMALS). Der Vorgängerkatalog bleibt draußen (A17, SD7). Schreiber und Leser von `orderKeys` und `assets` baut T12.1b. Ein neues Pflichtfeld ist eine Formatänderung und braucht ein Addendum hier.

## SD3 – Gate: beide Stände im selben Job, hash-exakt, keine Schwelle

- **Kontext:** Das Gate soll zeigen, dass nur die geänderten Schiffe anders aussehen. Ein Vergleich gegen eine gespeicherte Baseline hängt an Runner-Image, Treiber und Schriften; eine Bildschwelle braucht eine Lücke zwischen „gleich“ und „anders“.
- **Optionen:** gespeicherte Baseline mit Schwelle (Pixelanteil oder SSIM); Toleranzmodus für gewollte Änderungen; beide Stände im selben Job rendern.
- **Entscheidung:** **Beide Stände im selben `windows-latest`-Job** mit derselben App (`appTag`, SD8): erst alter Datenstand, dann neuer, Vergleich **hash-exakt** (`ShipPictureTests`). Keine Schwelle, kein Toleranzmodus, kein Schalter `render-change`. Gewollte Datenänderungen an vielen Schiffen gehen in den PR-Pfad.
- **Messung (S12.0, Lauf 3):** selbe VM alt↔neu **1 414 / 1 414** Bilder ohne 100i gleich, gesamt 1 427 / 1 427, Placement 108 / 108; VM↔VM und lokal↔Runner ebenfalls 1 427 / 1 427. „Anders“ (holo-v2↔v3, 96 Paare): Pixelanteil min **8,3 · 10⁻⁵**; **Lücke 0 gegen 8,3 · 10⁻⁵**. SSIM trennt erst in der 6. Nachkommastelle (max 0,999998) und fällt weg. Gate-Job ≈ 10 min (B0 271 s, B 139 s).
- **Gegenargument:** Zwei Bildläufe pro Lauf kosten ≈ 7 min Windows-Zeit, und der Job hängt am Cross-Repo-Checkout (SD1). Hash-exakt heißt: auch ein harmloser Re-Export ändert Bilder; das Gate sagt dann nur „anders“, das „wie schlimm“ bleibt dem Judge (SD5).
- **Konsequenz:** Keine gespeicherte Baseline, kein Runner-Pin fürs Gate. Ein neuer App-Tag ist ein gewöhnlicher Commit in `tools/pins.json`; Renderer-Regressionen prüft das App-Repo selbst (App-D90).

## SD4 – Release-Reihe `ships-YYYY.MM[.N]`, Pre-Release aus, letzte zwei bleiben, flaches Asset-Layout

- **Kontext:** Die App braucht genau eine URL ohne API (`…/releases/latest/download/manifest.json`). GitHub-Assets können keine Ordner sein; der T12.1-Release-Ordner hat `ships/` und `holo/`.
- **Entscheidung:** Tag `ships-YYYY.MM`, ein zweites Release im selben Monat `ships-YYYY.MM.1`. **Pre-Release-Flag aus**, damit `releases/latest` immer das letzte Data-Release ist; die **letzten zwei** bleiben, ältere löscht der Lauf. **Asset-Layout (D3, 18.11.):** `manifest.json` und `NOTICE.md` flach; **`ships.zip`** mit `ships/**` und `outlines.json` (die App lädt genau dieses Archiv); Holos flach als **`<slug>.holo`** (lazy pro Schiff, wie holo-v3). Heute 101 Holos + ZIP + Manifest + NOTICE = **104 Assets** (holo-v3: 103).
- **Grenzen (GitHub-Doku „About releases“, geprüft 18.11.):** „Up to 1000 release assets may be associated with a single release“, „Each file … must be under 2 GiB“, keine Grenze für die Gesamtgröße. Größtes Holo ≈ 0,1 MB, Release ≈ 33 MB.
- **Gegenargument:** Jedes Release lädt alle Holos neu hoch, auch unveränderte (≈ 30 MB im Monat), statt nur die geänderten. Zwei Releases sind ein kurzes Gedächtnis: eine App, die zwei Monate offline war, findet ihr Holo-Release nicht mehr und fällt auf die Baseline zurück (T12.4).
- **Konsequenz:** Jedes Release ist in sich vollständig, deshalb braucht das Manifest kein `holo.baseUrl` (SD2). `diff --previous` lädt nur Manifest + `ships.zip` (`gh release download` als `run.py`-Schritt, T12.2). Schreiber und Leser des Layouts baut T12.1b.

## SD5 – Judge: Verschlechterung heißt Metrik, nicht Flag (ersetzt P9)

- **Vorgeschichte:** T12.1 P9 (Martin, 17.11.): PR bei `passed=false`, wenn das Schiff vorher `passed=true` hatte, neu ist oder ein **neues Modell** bekam. Motherlode exportiert aber ohne Build-Wechsel alle Modelle neu (17.11.: **96 von 99**), und **22** veröffentlichte Holos sind dauerhaft `passed=false` – mit P9 ginge jeder Re-Export-Monat in den PR.
- **Messung:** Alle 22 verfehlen nur **Hausdorff** (0,0058 … 0,0931 bei Schwelle 0,005; IoU, F-Score, Löcher erfüllt). Der Judge rendert die Silhouette mit 512 px auf der langen Seite; ein Pixel ist ≈ 0,002 der Schiffslänge.
- **Entscheidung (D1, 18.11.):** PR, wenn (1) `passed` von true auf false kippt; (2) das Holo über 110 % seines Budgets liegt; (3) die verfehlte Metrik (Hausdorff) um mehr als **`HAUSDORFF_TOLERANCE = 0.0025`** gegenüber dem Vorgänger schlechter wird; (4) das Holo keinen vergleichbaren Vorgänger hat (neues Schiff, Quellwechsel wie F7C Fleetyards → Motherlode); (5) bei einem Schiff mit `passed=false` eine **zusätzliche** Metrik verfehlt wird (F3, 18.11.). Sonst Hinweis, auch bei `passed=false`.
- **Toleranz:** **vorläufig.** 0,0025 ist gut ein Judge-Pixel bei 512 px: das Pixelrauschen eines Re-Exports feuert nicht, zwei Pixel schon. Gemessen wird in T12.1b (die 22 mit den Modellen vom 17.11.); Bestätigung oder Korrektur als Addendum. Ändert sich die Render-Auflösung des Judge, ist die Zahl neu zu bewerten.
- **Gegenargument:** Eine feste Toleranz lässt eine schleichende Verschlechterung durch, Monat für Monat knapp darunter. Fall (4) schickt jedes neue Schiff einmal in den PR, auch wenn sein Holo besteht.
- **Konsequenz:** Der erste echte Lauf geht weiter in den PR (F7C, Fall 4) – gewollt. Die Konstante steht in `rules.py`; die Regel bekommt in T12.1b einen Test je Fall, jeder einmal provoziert rot. CLAUDE.md verweist auf SD5.

## SD6 – Verschwunden, Variante, wieder da; Stopp-Schwelle > 3

- **Kontext:** Motherlode ist Fremdquelle ohne Vertrag (A11). Am 17.11. fehlten 8 von 105 Schiffen: **6 Varianten** neu (Carrack w/C8X, Carrack Expedition w/C8X, MOLE Carbon, MOLE Talus, Mustang Alpha Vindicator, Valkyrie Liberator), jede mit Basis-`className` im Katalog; Cyclone und 600i Executive fehlten schon am 16.11. Der F7C Hornet Mk II war zurück.
- **Entscheidung:** **Verschwunden** heißt nie löschen: das Schiff behält seinen letzten Stand und Holo, `missingSince` = Datum des ersten Laufs ohne es; nach 3 Läufen eine Backlog-Zeile. **Variante:** steht die Basis-`className` noch im Katalog und waren die Racks im letzten Manifest hash-gleich zur Basis (`racksSha256`), folgt sie der Basis (`follows`); sonst `missingSince`. **Stopp:** mehr als **3** neu Verschwundene ohne Basis → PR-Pfad. **Wieder da (E1, 18.11.):** steht ein Schiff wieder im Katalog, werden `missingSince` und `follows` `null`, und es läuft wie jedes andere Schiff durch `diff`, Build und Judge (bei Quellwechsel Fall 4 in SD5).
- **Gegenargument:** Die Schwelle 3 ist gesetzt, nicht gemessen: am 17.11. 0 ohne Basis, ein Massenabgang (Seite kaputt, halber Katalog) stoppt. Ein Schiff, das monatelang fehlt, zeigt der Hauler weiter mit altem Stand, ohne Hinweis in der App.
- **Konsequenz:** Der Lauf zerstört nie einen gültigen Stand (A11). „Wieder da“ fehlt in den 14 Regeln von T12.1 und kommt in T12.1b mit Test; F7C ist der Live-Fall.

## SD7 – `actions/cache` und Fork-PRs: der Katalog liegt nie im Cache

- **Kontext:** S12.0 E1: Workflows aus Fork-PRs können den Cache des Default-Branch lesen. Der Katalog ist eine API-Antwort mit Key (Rohdaten 180 KB), keine öffentliche Datei; im Repo ist er tabu (A17).
- **Optionen:** Katalog nicht cachen; Workflows aus Fork-PRs abschalten; Katalog verschlüsselt cachen.
- **Entscheidung:** **Der Katalog kommt nie in den Cache, kein Artifact, kein Release.** Jeder Lauf ruft die API genau einmal (CLAUDE.md). Gecacht werden nur Modelle nach SHA (51 MB; bis zum nächsten Release liegen beide Sätze darin, ≈ 2 × 51 MB, T12.1 Auflage B) – sie liegen ohnehin in einem öffentlichen Bucket.
- **Gegenargument:** Ohne Katalog im Cache kann ein abgebrochener Lauf nicht ohne zweiten API-Ruf neu starten, und ein Katalog lässt sich nachträglich nicht untersuchen. Das zeigte die Katalog-Rettung in T12.1 (Workflow + Verschlüsselung für einen Katalog) – sie war Zeremonie: ein lokaler API-Ruf ist billiger.
- **Konsequenz:** Fork-PR-Workflows bleiben an (Standard „Approve workflows to run“). Wer einen Katalog zur Analyse braucht, ruft die API einmal lokal; die Regel heißt „einmal pro Lauf“, nicht „nie“.

## SD8 – Runner-Pin `ubuntu-24.04`, eine maschinenlesbare Quelle je Pin

- **Kontext:** S12.0 Lauf 1 war rot: `ubuntu-latest` ist 26.04, dort gibt es Python 3.14.5 nicht (erst ab 3.14.6). Die Byte-Gleichheit zu holo-v3 hängt an den Pins (S12.0, T12.1: 101 / 101 Holos, 109 / 109 Schiffsdateien).
- **Optionen:** Runner `ubuntu-24.04` mit Python 3.14.5; Python ≥ 3.14.6 auf `ubuntu-latest` (dann neu gegen holo-v3 messen); Pins in `TOOLS.md` und ein Parser dafür.
- **Entscheidung:** **`ubuntu-24.04`, Pins unverändert.** **Eine Quelle je Pin, maschinenlesbar; `TOOLS.md` ist Abschrift mit Test** (Korrektur K1, 18.11.): `.python-version` und `.nvmrc` (gelesen von `setup-python`/`setup-node` per `python-version-file`/`node-version-file`), `tools/pins.json` (`appTag`, `runner`, `pwsh`), `tools/requirements*.txt`, `tools/package-lock.json`. `run.py` liest `APP_TAG` aus `pins.json`, `tools/local-wsl.sh` liest Python, Node und pwsh aus denselben Dateien.
- **Gegenargument:** `ubuntu-24.04` läuft aus (GitHub entfernt alte Images nach ihrem Support-Ende); dann wird der Python-Bump fällig, mit neuer Byte-Messung. Der Runner steht zweimal (YAML kann `pins.json` nicht ohne Logik lesen).
- **Konsequenz:** `tests/test_versions.py` prüft Tabelle gegen Quellen und den gemessenen Stand gegen die Pins (provoziert rot mit verstelltem `.nvmrc`, `appTag` und hart kodiertem Python in `local-wsl.sh`); T12.2 ergänzt den Vergleich Runner im YAML ↔ `pins.json`.

## SD9 – Lebenszeichen-Commit `state/last-run.json`

- **Kontext:** GitHub-Doku („Events that trigger workflows“, `schedule`, geprüft 18.11.): „In a public repository, scheduled workflows are automatically disabled when no repository activity has occurred in 60 days.“ Ein Monatslauf ohne Änderung erzeugt kein Release und keinen Commit.
- **Optionen:** Lebenszeichen-Commit je Lauf; Keepalive-Action eines Dritten; nur Releases als Aktivität.
- **Entscheidung:** **Jeder Lauf schreibt `state/last-run.json`** (Datum, Lauf-ID, Ergebnis, geprüft / gefunden / zu tun) und committet sie, auch wenn sich nichts geändert hat; die Datei ist zugleich die Zusammenfassung des letzten Laufs im Repo.
- **Gegenargument:** Zwölf Commits im Jahr ohne Codeänderung machen die Historie lauter, und der Lauf braucht `contents: write` auf `main` – derselbe Token könnte mehr schreiben.
- **Konsequenz:** Kein Zustand, der nur lokal existiert: Zähler und Herkunft stehen im Manifest (SD2), das Lebenszeichen in `state/`. Den Schreiber baut T12.2; bis dahin gibt es `state/` nicht.

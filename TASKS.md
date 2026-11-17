# TASKS – sc-cargoplan-shipdata

## Phase 12 – Schiffsdaten über einen eigenen Kanal

Ziel: Schiffsdaten, Umrisse und Holos kommen aus diesem Repo über einen eigenen Kanal, gebaut von einer Pipeline, die
ohne Martin läuft. Gates: Schiffs-JSON byteidentisch; Umrisse und Holos per Bildvergleich mit Schwelle.

### [ ] S12.0 Spike: ein Schiff end-to-end auf GitHub Actions

Plan: `docs/plans/S12.0-spike.md`, freigegeben von Claude.ai am 17.11.2026 mit K1 (gate-b rendert alten und neuen
Stand im selben Job) und E1–E3. Workflow: `.github/workflows/spike.yml` (`workflow_dispatch`).

- [ ] 1. Kette auf `ubuntu-latest`: Katalog → Modell → Flatten → Leiter → Export → Umriss → Anker; Laufzeit,
  Toolchain-Pins, Cache-Größe
- [ ] 2. Scraper vom Runner: Modell-URLs von einer Datacenter-IP (Status, Block, Rate-Limit)
- [ ] 3. Gate-Job auf `windows-latest`: `sc-cargoplan@v0.5.1`, `ShipPictureTests` headless, Cross-Repo-Checkout +
  Testlauf in einem Job
- [ ] 4. Schwelle: Bildabstand „gleich“ gegen „anders“, Methode und Zahl
- [ ] 5. Manifest: was fehlt, was ist überflüssig
- [ ] Dispatch-Lauf (Martin, per Knopf)
- [ ] S12.0 Befund und „Das ändert sich am Phasenplan“

**S12.0 Befund:** folgt nach dem Dispatch-Lauf.

### [ ] T12.0 Doku
### [ ] T12.1 Pipeline `run.py fetch · diff · build · verify · release`
### [ ] T12.2 Workflow `ship-data.yml`
### [ ] T12.3 App-Datenkanal
### [ ] T12.4 Holo aus dem Manifest
### [ ] T12.5 App-Baseline aus dem Release
### [ ] T12.6 Release v0.6.0

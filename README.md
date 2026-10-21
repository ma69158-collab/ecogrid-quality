# EcoGrid Energy – Quality Prototype

A small Python prototype of the EcoGrid Energy peer-to-peer solar trading platform,
built for ICT711 Assessment 3 (Software Quality Management).

## Bounded contexts
- `ecogrid/meter.py` – Smart Meter Integration: ingest and validate IoT meter readings
- `ecogrid/marketplace.py` – Marketplace: match sellers' surplus energy with buyers
- `ecogrid/settlement.py` – Financial Settlement: pay sellers, take platform fee, keep ledger
- `ecogrid/models.py` – shared domain models

## Run
```bash
pip install -r requirements.txt
python -m ecogrid.main
pytest --cov=ecogrid --cov-report=term
```

## Quality analysis
Analysed with SonarQube Cloud via GitHub Actions (`.github/workflows/sonarcloud.yml`).

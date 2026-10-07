# R1 synthetic inputs (pinned copies)

These files are synthetic data: byte-identical copies of R1's `data/synthetic/` files at the commit pinned in `standard/standard-reference.yaml`. Do not edit them. Their SHA-256 values and row counts are in `../manifest.yaml`, and `tools/validate.py` fails if they drift. To change them, change R1 and re-run `tools/sync_r1_contracts.py` with an explicit commit.

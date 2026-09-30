# Runner guide

Run from any directory; the wrappers resolve the package root themselves.

| Runner | Intended use | Default | Safety behavior |
|---|---|---|---|
| `run_production.py` | One live workbook | QUICK, full schedule | Exact snapshot, independent validation, sealed packaging |
| `run_smoke.py` | Fast defect/contract check | SMOKE | No production claim without all gates |
| `run_targeted_regression.py` | Explicit affected scenarios | QUICK, full schedule | Requires `--only` or `--input` |
| `run_standard_regression.py` | Manifest regression | QUICK, full schedule | Verifies engine and input hashes |
| `run_deep.py` | Genuine unresolved optimization defect | DEEP | Requires nonblank `--reason` |
| `run_parallel.py` | Independent manifest shards | QUICK | One guard pass, unique ledgers, one final gate pass |
| `run_resume.py` | Resume interrupted exact run | QUICK | Resume identity must match input/contract/engine/parameters |
| `rc922_runner.py` | Canonical manifest runner | Manifest/CLI | Runtime, engine, input, guards, return codes, release gates |

For Colab, use `RC922_Colab_B_WITH_DRIVE.ipynb` for persistent checkpoints and
results, or `RC922_Colab_A_NO_DRIVE.ipynb` when temporary `/content` storage is
acceptable. Both notebooks call the canonical `rc922_runner.py` entry point.

Examples:

```bash
python3 runners/run_targeted_regression.py --only NMG_EN_PRODUCTION,NMG_EN_SP,GDI_REAL28 --results-root results_targeted
python3 runners/run_standard_regression.py --results-root results_standard
python3 runners/run_parallel.py --instances 3 --only NMG_EN_PRODUCTION,NMG_EN_SP,GDI_REAL28
python3 runners/run_resume.py --input inputs/RC9_2_2_NMG_EN_PRODUCTION_INPUT.xlsx --schedule-id NMG_EN_PRODUCTION_QUICK_RC5 --output-root results
python3 runners/run_deep.py --only NMG_EN_PRODUCTION --reason "QUICK reproduced unresolved break-feasibility defect RC922-X"
```

Existing case directories are not overwritten unless `--overwrite` is explicit. Use a new schedule ID for a clean comparison. A nonzero exit code means the schedule is not approved.

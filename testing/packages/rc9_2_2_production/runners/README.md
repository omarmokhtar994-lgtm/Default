# Runner guide

Run from any directory; the wrappers resolve the package root themselves.
These are RC5's runners, restored on top of the final engine (audit F-17), with
the seed-portfolio options added to the canonical runner.

| Runner | Intended use | Default | Safety behavior |
|---|---|---|---|
| `rc922_runner.py` | Canonical manifest runner | Manifest/CLI | Engine sha256 vs manifest, pinned runtime check, input hashes, the full offline gate (`run_tests.sh`), process-group stop on timeout/interrupt, nonzero exit on any failed scenario or failed release gates |
| `run_production.py` | One live workbook | QUICK, full schedule | Exact snapshot, independent validation, sealed packaging |
| `run_smoke.py` | Fast defect/contract check | SMOKE | No production claim without all gates |
| `run_targeted_regression.py` | Explicit affected scenarios | QUICK, full schedule | Requires `--only` or `--input` |
| `run_standard_regression.py` | Manifest regression | QUICK, full schedule | Verifies engine and input hashes |
| `run_deep.py` | DEEP with a recorded reason | DEEP (best of 4 x 1 h seeds) | Requires nonblank `--reason` |
| `run_parallel.py` | Independent manifest shards | QUICK | One full gate pass, one final gate pass |
| `run_resume.py` | Resume an interrupted exact run | QUICK | Resume identity must match input/contract/engine/parameters |

`rc921_runner.py` is the implementation module the others import.

For Colab, use `RC922_Colab_B_WITH_DRIVE.ipynb` for persistent results on Drive,
or `RC922_Colab_A_NO_DRIVE.ipynb` when temporary `/content` storage is enough.
Both call `rc922_runner.py`.

Seeds (`--seeds N`, or `SEEDS` in the notebooks): the scenario is solved once per
seed and the best independently validated schedule is kept. `SEEDS = 0` is
automatic: QUICK 2, DEEP 4 x 1 h, OVERNIGHT 6 x 1 h (evidence/seed_portfolio_ab).
`--single-run` makes DEEP/OVERNIGHT one long run.

Examples:

```bash
python3 runners/run_targeted_regression.py --only NMG_EN,NMG_EN_SP,GDI_REAL28 --results-root results_targeted
python3 runners/run_standard_regression.py --results-root results_standard
python3 runners/run_parallel.py --instances 3 --only NMG_EN,NMG_EN_SP,GDI_REAL28
python3 runners/run_deep.py --only CRICUT_CHAT --reason "QUICK left target gaps on Chat"
```

Existing case directories are not overwritten unless `--overwrite` is explicit.
A nonzero exit code means the schedule is not approved.

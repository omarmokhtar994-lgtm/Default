# Worker curve: 4 workers wins. No code change required.

All at 1800s, `after_target`, one run per point.

| case | 1w | 2w | 4w | active | best |
|---|---|---|---|---|---|
| AE_AR_B2B | 165 | 168 | **168** | 168 | 4w (ceiling) |
| Cricut_Chat | **163** | 159 | 159 | 242 | **1w** |
| Cricut_Voice | 224 | 247 | **248** | 264 | 4w |
| GDI_REAL28 | 137 | 111 | **141** | 156 | 4w |
| **TOTAL** | **689** | **685** | **716** | | |

**4 workers: +27 intervals over 1 worker. Best on 3 of 4 cases.**

**2 workers is not a useful middle step** -- it scores *below* 1 worker in
aggregate (-4). That is driven by GDI at 111, which sits 26 below its 1w result
and 30 below its 4w result. Multi-worker CP-SAT is nondeterministic and these
are single runs, so that point is likely an unlucky draw rather than a property
of 2 workers; either way 2 is not worth choosing.

Cricut_Chat is the one case that prefers a single worker (163 vs 159), and it
prefers it consistently at both 2w and 4w.

## Why this needs no code change

The shipped default is already:

```python
max(1, min(8, os.cpu_count() or 4))
```

On a 4-core host that resolves to **4** -- the measured best. Colab caps at 4
cores, so production already gets the right value without intervention.

## Honest limits

* **One run per point.** Multi-worker is nondeterministic; the GDI 2w outlier
  shows the size of that noise. The 4w total advantage (+27) is larger than any
  single anomaly, but individual cells should not be quoted as precise.
* **4 workers on 4 cores.** No oversubscription was tested. If a host reports
  fewer cores, the default drops with it and there is no data below 4.
* **Cricut_Chat regresses with workers** and that is unexplained. It is the same
  case that keeps climbing past 3600s, so it may simply be far from any
  plateau where portfolio diversity helps.

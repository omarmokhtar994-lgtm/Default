# RC5 vs RC9.1 — AE comparison review

No code changed, per the brief. Everything below was computed by running the
shipped RC5 engine (`0e6f6435…`) against the six AE workbooks in
`RC5_AE_REAL_SCHEDULES_QUICK_PACKAGE`.

---

## Headline: two of your five compared cases are capacity-infeasible

**Your aggregate table mixes cases the engine can win with cases no engine can
win.** I recomputed supply and demand from the workbooks:

| Case | HC | Leave days | Effective days | Supply h | Demand h | Slack | Verdict |
|---|---:|---:|---:|---:|---:|---:|---|
| AE_AR_B2B | 39 | 11 | 184 | 1472 | 1111 | **+361 (+32%)** | ample |
| AE_FR_B2B | 38 | 4 | 186 | 1488 | 1186 | **+303 (+26%)** | ample |
| **AE_FR_Choice** | 14 | 2 | 68 | 544 | 441 | **+103 (+23%)** | **ample** |
| AE_AR_Choice | 11 | 1 | 54 | 432 | 410 | +22 (+5.5%) | tight |
| **AE_IT_B2B** | 13 | 3 | 62 | 496 | 524 | **−28 (−5.4%)** | **CAPACITY-SHORT** |
| **AE_IT_Choice** | 8 | 11 | 29 | 232 | 279 | **−47 (−17%)** | **CAPACITY-SHORT** |

Supply = (HC × 5 workdays − leave days) × (9 h shift − 1 h breaks).
Demand = Σ over active intervals of `req × target_ratio × hours / (1 − shrinkage)` —
the engine's own formula, verified against `capacity_diagnostics` to the decimal.

**A case with negative slack cannot reach its target under any break placement,
by either engine.** Including AE_IT_B2B in an aggregate coverage KPI measures
the roster, not the optimiser.

---

## 1. Your AE_IT_Choice diagnosis is wrong on all three points

You state: *"A single English resource bottleneck around Friday 08:00–14:00. At
least one no-break exception is required."*

**All eight associates are English.** There is no language mix:

```
languages: Counter({'english': 8})
language rule: English 08:00-00:00, minimum 1, eligible ['english']
```

A minimum of 1 against 8 eligible people is never the binding constraint.

**Friday 08:00–14:00 is not a bottleneck.** It needs 2–3 of 8:

```
Fri 08:00 need 2   Fri 11:00 need 3
Fri 09:00 need 2   Fri 12:00 need 3
Fri 10:00 need 3   Fri 13:00 need 3   Fri 14:00 need 3
```

Peak need across the entire week is **4 of 8**.

**The real cause is leave.** 11 of 40 associate-days are on leave — **27.5% of
the roster-week**:

```
Salma …      Sun:L Mon:L Thu:L Fri:OFF Sat:OFF
Mahmoud …    Mon:L Tue:OFF Wed:OFF Thu:L
Abdullah …   Mon:OFF Tue:OFF Wed:L Thu:L Fri:L
Mariam …     Tue:L Wed:L Thu:OFF Fri:OFF
Youssef …    Tue:L
```

Effective capacity is 29 associate-days = 232 productive hours against 279
required. The engine's own preflight agrees exactly:
`AGGREGATE_TARGET_CAPACITY_SHORTAGE, capacity_slack_hours: -46.6111`.

**And the proposed remedy would not work.** A no-break exception recovers one
hour per associate-day. Closing a 46.6-hour gap needs roughly **47 exceptions**,
not one. Authorising a single exception cannot make this schedule feasible.
What closes it: about **6 more associate-days** (less leave, or cover), or a
lower target for this week.

So your point 11 — *"some failures are genuine business infeasibility"* — is
**correct**, and is the right conclusion. The stated mechanism and remedy are
not.

---

## 2. What this does to the aggregate table

Your table reports RC9.1 ahead by 10 after-target intervals across 672. Two of
the five contributing cases are capacity-short, and one of those (AE_IT_B2B) is
where you attribute RC5's largest after-break loss:

> *AE_IT_B2B — before target RC5 83, RC9.1 76; after target RC5 68, RC9.1 72.*
> *"RC5 starts with a better skeleton but loses more during break placement."*

At −28 hours of capacity, **neither engine can reach target on this workbook.**
Both are operating in a regime where the constraint is the roster. A 4-interval
after-break difference there is not evidence about break placement; it is two
engines making different compromises inside an infeasible region.

**Recommended:** report the aggregate over the three capacity-positive cases
only (AE_FR_B2B, AE_FR_Choice, AE_AR_B2B, plus AE_AR_Choice flagged as tight),
and report the two short cases separately as roster findings. The current
aggregate is not measuring what its heading claims.

---

## 3. AE_FR_Choice is the right test — and now for a defensible reason

You nominate it as the most informative candidate. **Agreed, and the capacity
numbers are why:** it has **+103 hours (+23%) of slack**, equal before-break
coverage in both engines (112/112), and RC5 loses 6 after-break target
intervals.

That combination is the clean experiment:

- capacity is not binding, so the loss cannot be blamed on the roster;
- the skeletons start equal, so it isolates the break stage;
- 6 intervals on 112 is a 5.4% swing — large enough to measure past noise.

This is the one case in the set where a difference genuinely measures the
optimiser. Run it.

---

## 4. Comparison validity — section A answered

| Question | Answer |
|---|---|
| Are inputs comparable? | **Cannot verify.** The RC9.1 package was not uploaded. I only have the RC5 side. |
| Same engine hashes? | **Yes** for RC5 — all six input hashes and the engine hash match `PACKAGE_IDENTITY.json` exactly. |
| Did the modernized input architecture change the problem? | **Unverifiable without the RC9.1 workbooks.** `PACKAGE_IDENTITY.json` declares `input_architecture: RC5_modernized_input_architecture` and `engine_behavior_changed: false` — a self-declaration, not evidence. |
| 672 comparable active intervals? | **Verified exactly.** 168+168+112+112+112 = 672. |
| Same interval definitions? | **Yes** — all six are 60-minute, 24 intervals/day. |
| Same targets? | **No.** Five cases are target 1.0; **AE_IT_Choice is 0.85.** Worth stating when the set is described as one population. |

**This is the one thing I still cannot do.** Section B asks me to recompute
after-break coverage, floor gaps, break concurrency and overage from actual
results. **No result artifacts were uploaded** — this package contains inputs,
engine and runners only. Send the result ZIPs and I can recompute the whole
table.

---

## 5. Your interpretation, challenged point by point

| Your statement | Verdict |
|---|---|
| "RC5 is safer on breaks" | **Supported** by your data — 31 vs 138 violations is a large, consistent margin. |
| "RC9.1 wins final coverage" | **Not established.** Two of five cases are capacity-short; the aggregate mixes populations. |
| "Largest weakness is post-break optimisation" | **Plausible but untested.** AE_FR_Choice is the only clean evidence for it, and it is a single case. |
| "Language-window logic has little measurable impact" | **Wrong reason.** All six workbooks parse to `language_working_window_mode: OFF`. It was never enabled — so the tests show nothing about its impact either way. |
| "Maximum coverage is not mathematically guaranteed" | **Correct**, and stronger than you state — see below. |
| "The core CP-SAT foundation is not the immediate problem" | **Disagree.** The formulation is the problem, not the solver. |
| "AE_IT_Choice may be input/roster infeasibility" | **Correct.** Confirmed at −46.6 h. |

### On "maximum coverage is not guaranteed"

From my earlier measurements on this engine, which stand: the Stage-1 objective
is a **single weighted sum of 77 terms spanning 800,000,000 : 1**
(`target_miss` 3.2e9 vs `preference` 4). Weighted-sum scalarization provably
cannot reach unsupported Pareto points, so some better schedules are unreachable
at **any** runtime. And the largest model here is **5,880 binary variables** —
small — yet runs truncate at 2 of 15 skeleton profiles.

Your staged architecture is a reasonable industrial decomposition. It is not
what is costing you coverage. The objective is.

---

## 6. Blunt recommendation

**Use RC9.1 as the production baseline while improving RC5 — with one
correction to how you are measuring.**

Not because RC9.1 is the better optimiser; that is not established. Because RC5
has not yet been shown to beat it on a fair comparison, and the comparison you
have is measuring two capacity-infeasible cases as if they were optimiser tests.

The hybrid option in your list — *RC9.1 optimisation behaviour with RC5
validation/release controls* — is the wrong shape. The RC5 release chain is
genuinely good, but it is not separable from the engine it wraps, and the
evidence does not show RC9.1's search is better. You would be freezing an
optimiser you also have not measured.

### Answer to your final question

> *Has RC5 genuinely improved the scheduling engine, or mainly the controls
> around it?*

**Mainly the controls — and that is not a criticism, it is what the evidence
supports.** Your own note is correct: the closure pass did not materially
replace the CP-SAT search. What RC5 demonstrably improved:

- break safety (31 vs 138 violations — a real scheduling-quality gain, not a
  control);
- balance observations (72 vs 105 overage-cap, 29 vs 55 imbalance);
- validation, identity, sealing, metric parity — all control-layer.

What RC5 has **not** demonstrated: better final coverage. On the three cases
where capacity permits a fair test, you have one tie, one small RC5 win, and one
RC5 loss of 6 intervals.

---

## 7. Smallest next test with the highest information value

**One case. AE_FR_Choice. Before-breaks-only, then full, both engines, twice
each.**

Why this and not a six-hour sweep:

- It is the only case with ample capacity **and** equal before-break coverage
  **and** a measurable after-break gap. Every other case either has a capacity
  confound or no gap to explain.
- Before-breaks-only isolates Stage 1. If both engines still tie at 112, the
  loss is entirely in break placement and you have localised it to one stage.
- Twice each, because the same input at the same seed has previously produced
  both a shippable schedule and no schedule at all on this codebase. One run is
  not evidence.

Budget: roughly 4 runs × 1 hour, versus 6 hours for the full sweep — and it
answers the actual question, which the sweep does not.

**Second priority, and cheap:** re-run AE_IT_Choice with one no-break exception
authorised. My arithmetic says it will still fail, by roughly 46 hours. If it
succeeds, my capacity model is wrong and I want to know.

---

## 8. Package and runner design — section G

**Keep both, add one manifest.** The distinction is technically justified — a
six-case quick comparison genuinely is a different artifact from the canonical
release package. But `PACKAGE_IDENTITY.json` and `SCENARIOS.json` carry the same
information in two shapes, which is what broke your Colab cell.

Cheapest fix: have the quick package emit **both** files, with `SCENARIOS.json`
as the canonical name and `PACKAGE_IDENTITY.json` retained for compatibility.
One runner, one manifest name, no detection logic.

---

## 9. What I could not verify

- **No result artifacts.** Every number in your section 5 table remains
  unrecomputed. This is now the fourth handoff where the packages arrive without
  the runs.
- **No RC9.1 package.** I cannot compare input architectures, so I cannot answer
  whether the modernized inputs changed the problem definition — which is your
  own question A3, and it matters more than anything else in the comparison.

Send `RC9_1_AE_REAL_SCHEDULES_QUICK_PACKAGE.zip` and the result ZIPs and I can
close sections A and B properly.

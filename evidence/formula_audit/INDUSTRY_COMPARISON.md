# The engine against published WFM practice

Each row compares one thing the engine does with what the industry sources
state, and says whether they agree. Sources are listed at the end.

| topic | industry practice | this engine | agree? |
|---|---|---|---|
| **Shrinkage gross-up** | Divide by `(1 − shrinkage)`. Multiplying by `(1 + shrinkage)` under-staffs: 100 FTE at 30% needs 143, not 130. | All 24 shrinkage sites use `1 − s`; 0 use the multiply form. Headcount formulas return exactly the metric's minimum on 28,905 cases. | **Yes** |
| **Interval coverage** | Compare net scheduled staff with required staff per 15- or 30-minute interval. | Net = average headcount over the interval's quarters × (1 − shrinkage), compared with the requirement. A 15-minute break counts as half of a 30-minute interval. | **Yes** |
| **Break contract** | 8-hour shift: two 15-minute breaks and one 30-minute meal. | Every corpus workbook: Break 1 (15), Lunch (30), Break 2 (15). The generator is proven valid and complete for that contract and 7,140 others. | **Yes** |
| **Concurrent breaks** | 10–15% of agents on break at once is typical; 30% is the usual outer limit. | Default: at most 30% **or** 4 people, whichever is smaller — 28% at 14 on the floor, 15% at 27, 10% at 40. Workbook-configurable. | **Yes**, at the permissive end for small teams |
| **Architecture** | Calabrio optimises shifts, then moves breaks in a separate pass ("intra interval balance"). NICE IEX and Verint use heuristic + integer-programming hybrids. | Stage-1 builds the shift skeleton, Stage-2 places breaks, both with CP-SAT, plus heuristic recovery phases. | **Same shape** |
| **Solve time** | Reported CP-SAT rostering: ~150 employees × 30 days in 2–5 min; 300+ in 10–30 min. | QUICK is 1800s for 27–39 associates over a week with 15-minute break placement. | Slower than those reports, on a harder sub-problem (break placement at quarter-hour resolution is modelled explicitly). |

## Where the comparison says something the audit did not

* **Integer arithmetic has to match the report.** Commercial tools report
  coverage from the same model they optimise. This engine optimised Stage-2 in
  a rounded integer form and reported in exact arithmetic, and the two
  disagreed on the non-terminating shrinkage in two workbooks. That is F-1.
* **Break time is part of shrinkage.** Peopleware's example: if the staffing
  model assumes 28% shrinkage and breaks are 10% of it, the break schedule must
  deliver exactly that 10%. Here, break loss is modelled explicitly per quarter
  rather than folded into the shrinkage percentage, so the two cannot be
  double-counted — provided the workbook's shrinkage excludes break time. That
  is a workbook-authoring rule, not something the engine can detect.

## Sources

- [Call Centre Helper — How to include shrinkage in your planning process](https://www.callcentrehelper.com/include-shrinkage-planning-process-143070.htm)
- [Peopleware — Call center shrinkage](https://blog.peopleware.com/forecasting/call-center-shrinkage)
- [WFM Labs — Shrinkage](https://wiki.wfmlabs.org/wiki/Shrinkage)
- [WFM Labs — Schedule Optimization](https://wiki.wfmlabs.org/wiki/Schedule_Optimization)
- [Calabrio — How schedule optimization works](https://help.calabrio.com/doc/Content/user-guides/schedules/about-optimization-steps.htm)
- [Verint — Calabrio WFM vs NiCE CXone WFM](https://www.verint.com/blog/calabrio-wfm-vs-nice-wfm/)
- [Google OR-Tools — Employee scheduling](https://developers.google.com/optimization/scheduling/employee_scheduling)
- [CP-SAT rostering: constraint programming for workforce scheduling](https://mbrenndoerfer.com/writing/cp-sat-rostering-constraint-programming-workforce-scheduling)
- [TELUS — Net staffing thresholds at interval level](https://portal.wfo.telusinternational.com/OnlineHelp/en_US/wfm/WFM_ForeSch/wfm_ForeSch_net_staffing_thresholds.htm)
- [HiveDesk — Call center shift schedule with break times](https://www.hivedesk.com/resources/call-center-shift-scheduling-with-break-times)
- [HiveDesk — Break management in contact centers](https://www.hivedesk.com/blog/guide-tracking-managing-break-times-in-contact-centers/)
- [Call Centre Helper — Break optimisation strategies](https://www.callcentrehelper.com/break-optimisation-strategies-207088.htm)

# B-12: a one-word header lookup still matches a prose banner

What this file answers: why `_find_header_row` picks row 2 of the NMG13
Preference sheet when the real header is on row 4, how much damage that does
today, and why it had to be fixed before B-11 could ship.

Found while validating B-11, not by looking for it.

---

## 1. The defect

`_find_header_row` was hardened once already. Its own docstring records the
case: the Language Setup banner in NMG13 contains both "language" and
"minimum", so it satisfied `["language", "minimum"]` on its own and was chosen
as the header over the real row. The fix requires the terms to appear in
**distinct cells**.

That fix does nothing when there is only **one** term. One cell trivially
satisfies "the terms are in distinct cells".

All three name-matched sheets look up `["name"]`:

| line | sheet |
|---|---|
| 1442 | Preference |
| 1454 | Previous week scheduled |
| 1484 | Fixed Request |

The NMG13 Preference banner on row 2 reads:

> "Optional: enter Leave/OFF/shift preference by day. Sheet **name**
> intentionally matches legacy engine spelling."

It contains "name". Row 2 is returned. The real header is row 4.

## 2. How much damage, honestly

**None on this corpus.** This is latent, not live.

With row 2 as the header, `_day_columns` binds nothing, so every column falls
back to positional guessing: `name_col + 2 .. name_col + 8`. On NMG13 the real
day block is exactly columns 3-9 and the name column is exactly column 1, so
the fallback lands on the right cells and the right values are read. The loop
simply starts two rows early over blank rows and the row-4 header text.

Measured across 15 workbooks and 40 name-matched sheets: **2 misdetections**,
both NMG13 Preference. Parsing with and without the fix produces **identical
canonical contract hashes and identical preference values on all 15**.

It survives on exactly the luck the `_day_columns` docstring already names —
"a property of the sample, not a guarantee". A Preference sheet whose day
block does not begin two columns after the name would be read from the wrong
columns, and the wrong people would get the wrong leave and OFF days, silently.

## 3. Why it blocked B-11

B-11 makes an unmatched row on a name-matched sheet a contract failure. With
the header misdetected at row 2, the loop reads row 4 — the literal header
text `"SF Name"` — as a data row. Two shipped workbooks would have failed
their contract over a cell that is a column title.

That is a false positive of the exact kind that erodes trust in a fail-closed
check, so B-12 lands first.

## 4. The fix

Among the rows that already pass the term test, prefer one whose headers bind
all seven weekdays. A fully bound day header is not something a banner
produces, and it is a structural property of the sheet rather than a guess
about prose length or wording.

It is strictly additive: when no candidate binds seven days the previous
answer is returned unchanged. It is enabled only at the three day-bearing
name-matched call sites, so roster, demand and language parsing are untouched.

| sheet | before | after |
|---|---|---|
| NMG13 Preference (x2 workbooks) | row 2 (banner) | row 4 (real header) |
| every other name-matched sheet (38) | unchanged | unchanged |

`Previous week scheduled` carries a Saturday column only and binds no
seven-day header anywhere, so it is unaffected; it is passed the flag for
consistency, not for effect.

SAKS and GDI Preference sheets detect row 1 with zero day columns because
their day headers are **dates**, not day names. Row 1 genuinely is the header
there, the positional fallback is correct, and the fix leaves them alone.

## 5. Verification

* 15 workbooks parsed with and without: 0 contract-hash changes, 0 preference
  changes.
* Full gate on the patched tree: 17 suites PASS, both selfchecks PASS,
  undefined-name sweep PASS.

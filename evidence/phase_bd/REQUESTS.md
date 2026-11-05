# Phase BD: a separate OFF asked for in Preference is accepted (owner, 2026-10-29)

Owner: "for the engine I want, if I added in Preference a separate OFF, to be accepted even if the instructions say no separate OFF: stick to the instructions except for what is mentioned in Preference."

## Measured first
With Separate OFF Days = No and Strict OFF Count = Yes, one associate whose Preference row has hard OFF on Sunday and Wednesday makes Stage 1 **INFEASIBLE** for the whole roster
(`tests_staged/test_rc9_2_60_separate_off_in_preference.py`, 10 associates, the same demand as `test_rc9_2_30`): every person must have two OFF days in a row, and a person
whose two OFF days are fixed apart cannot. Before this change the owner had to switch the instruction to Yes for everybody.

## Rule (pre-registered before the change; engine, validators)
1. An associate "asks for separate OFF days" when Separate OFF Days = No and their own request rows name at least two hard OFF days of which at least one has no neighbour among them (Saturday is next to Sunday, as in the rule).
   The Preference row counts when Hard OFF Preferences = Yes, and (owner, same day: "make Fixed like Preference") the Fixed Request row counts when Fixed Request Use = Yes; the two together count as one set of days.
   One OFF day, or OFF days next to each other, are not such a request.
2. For that associate only, the consecutive-OFF rule is not demanded in the Stage 1 model, the joint model, the engine's `validate_schedule`, the independent validator and the clean-room check. Everyone else keeps it (Separate OFF Days = No is still the rule). The OFF count is unchanged (Strict OFF Count still fixes it).
3. The aggregate search guidance counts that associate outside the pairs.
4. With Separate OFF Days = Yes, with Hard OFF Preferences = No, and for workbooks with no such request, nothing changes: the protected RC9.1 baseline workbooks (`AE_AR_B2B.xlsx`, `Cricut_Voice_RC9_1_READY_SKELETON.xlsx`, `NMG_SP_RC9_1_READY_FIXED.xlsx`) and `engine/regression_assets` keep their bytes, and the gate (parity, identity, the staged suites) passes.
**Acceptance:** the new tests fail first (they did: the roster is INFEASIBLE, the checker flags everybody) and pass; the staged release gate passes with the engine identity refreshed (`tools/refresh_engine_identity.py`) and the engine map written; the website suites pass.
Not changed: any other instruction, the break and channel planners.

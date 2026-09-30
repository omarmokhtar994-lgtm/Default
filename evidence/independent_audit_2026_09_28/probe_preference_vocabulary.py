# Audit probe: which ordinary Preference-sheet values does the FINAL engine classify
# as "other" (=> hard contract failure UNRECOGNISED_PREFERENCE_VALUE)?
import sys; sys.path.insert(0, "engine/_tools")
import l632_universal_scheduler as E
VALS = ["Leave","Annual Leave","annual-leave","A/L","Sick Leave","Vacation","OFF","Day Off","RD","WO",
        "Public Holiday","PH","Bank Holiday","Comp Off","Casual Leave","CL","PL","Emergency Leave",
        "Medical Leave","Maternity Leave","Personal Leave","Vacation Leave","Holiday Leave","Unpaid","LOA",
        "Training","WFH","Half Day","OFF (approved)","Leave (approved)","Requested Off","Off Request",
        "R/D","D/O","N/A","-","TBD","09:00-18:00","9-6"]
for v in VALS:
    print(f"{v!r:20} -> {E.preference_kind(v)}")

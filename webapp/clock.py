# © 2026 Omar Mokhtar. All rights reserved.
"""Egypt time for the whole website (owner's rule: times in Egypt time).

Egypt changes its clocks: UTC+3 in summer, UTC+2 in winter (from midnight on the last
Thursday of October to the last Friday of April). The Africa/Cairo zone follows those
changes, so every module takes EGYPT from here instead of fixing an offset. The zone
comes from the server's time zone data (the tzdata package); without it the website
stops at start-up with ZoneInfoNotFoundError rather than show times an hour out.
"""
from zoneinfo import ZoneInfo

EGYPT = ZoneInfo("Africa/Cairo")

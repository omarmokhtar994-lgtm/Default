# Dependency installation record

- Required solver: `ortools==9.15.6755`.
- Attempted command: `python3 -m pip install 'ortools==9.15.6755'`.
- Result: the restricted package index available to this workspace returned no matching distribution.
- Filesystem/cache search: no compatible local OR-Tools installation or wheel was present.
- Other required packages passed the runtime version check.
- Consequence: current-build CP-SAT validation is blocked in this environment. The release candidate is therefore NO-GO, regardless of offline-test success.

No untrusted or unpinned substitute solver was installed.

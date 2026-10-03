"""Prove the RC9.1 baseline workbooks' contracts are unchanged by Phase B.

B2 (audit F-08) widened canonical_contract_snapshot, so the canonical contract
hash of every workbook moves although no workbook changed. For each of the
three baseline-protected workbooks this checks: the file bytes equal the pinned
file_sha256; every field the Phase A engine's snapshot recorded has the same
value under the Phase B engine; and lists the fields Phase B added."""
import hashlib, importlib.util, json, sys
from pathlib import Path
def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec); sys.modules[name] = mod; spec.loader.exec_module(mod); return mod
old = load(sys.argv[1] + '/l632_universal_scheduler.py', 'eng_a')
sys.modules.pop('canonical_metrics', None)
new = load('engine/_tools/l632_universal_scheduler.py', 'eng_b')
baseline = json.loads(Path('evidence/RC9_1_BASELINE.json').read_text())
names = {"AE_AR_B2B.xlsx": "AE AR B2B", "Cricut_Voice_RC9_1_READY_SKELETON.xlsx": "Cricut Voice",
         "NMG_SP_RC9_1_READY_FIXED.xlsx": "NMG SP"}
out = {}
for filename, scenario in names.items():
    path = Path('packages/rc9_2_2_production/inputs') / filename
    hist = baseline["scenarios"][scenario]["input_sha256_prefix_history"][-1]
    a = old.canonical_contract_snapshot(old.parse_input(path))
    b = new.canonical_contract_snapshot(new.parse_input(path))
    out[scenario] = {
        "file_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "file_sha256_pinned": hist.get("file_sha256"),
        "phase_a_hash": old.canonical_hash(a), "phase_a_hash_recorded": hist.get("canonical_contract_hash"),
        "phase_b_hash": new.canonical_hash(b),
        "changed_existing_fields": sorted(k for k in a if json.dumps(a[k], default=str, sort_keys=True) != json.dumps(b.get(k), default=str, sort_keys=True)),
        "added_fields": sorted(set(b) - set(a)),
        "removed_fields": sorted(set(a) - set(b)),
    }
print(json.dumps(out, indent=1))
json.dump(out, open(sys.argv[2], 'w'), indent=1)

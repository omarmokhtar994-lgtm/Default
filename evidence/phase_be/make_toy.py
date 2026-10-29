import sys
exec(open("/tmp/prefexp/pref_free.py").read().split("asked = sum")[0].replace("with tempfile.TemporaryDirectory() as tmp:\n    path = Path(tmp) / \"case.xlsx\"; W.build(spec, path); parsed = E.parse_input(path)", "W.build(spec, Path('/tmp/prefexp/toy.xlsx'))"))
print("toy written")

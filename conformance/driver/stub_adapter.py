"""The smallest adapter, for the driver's own test (test_driver.py): it knows one syntax case, the empty text.

stub_adapter.py ok | crash | bad-hello | stall

stall answers hello and never answers parse: it keeps reading, as a hung binding would.
"""

import json
import sys

MODE = sys.argv[1]
EMPTY = {"tokens": [], "root": ["document", 0, 0, []], "diagnostics": []}
for line in sys.stdin:
    request = json.loads(line)
    if request["op"] == "hello":
        unit = "furlong" if MODE == "bad-hello" else "utf-16"
        ok = {"protocol": 1, "binding": "stub", "unit": unit, "level": 0}
    elif MODE == "crash":
        sys.exit(3)
    elif MODE == "stall" and request["op"] == "parse":
        continue
    else:
        ok = EMPTY
    sys.stdout.write(json.dumps({"id": request["id"], "ok": ok}) + "\n")
    sys.stdout.flush()

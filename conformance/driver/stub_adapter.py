"""The smallest adapter, for the driver's own test (test_driver.py): it knows one syntax case, the empty text.

stub_adapter.py ok | crash | bad-hello
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
    else:
        ok = EMPTY
    sys.stdout.write(json.dumps({"id": request["id"], "ok": ok}) + "\n")
    sys.stdout.flush()

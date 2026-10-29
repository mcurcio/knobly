"""The driver's end of the adapter protocol (spec/conformance.md section 2): one adapter process, JSON lines on its
standard input and output, one request and its response at a time."""

from __future__ import annotations

import json
import subprocess
from typing import Any, Dict, List, Optional

PROTOCOL = 1


class AdapterFault(Exception):
    """The adapter broke the protocol, failed inside itself, or exited: the case fails, the run goes on."""


class Thrown(Exception):
    """The binding raised one of its own errors (a ``villanelle error``): ``error`` is the neutral error object."""

    def __init__(self, error: Dict[str, Any]) -> None:
        super().__init__(error.get("group", "?"))
        self.error = error


class Adapter:
    def __init__(self, command: List[str], cwd: Optional[str]) -> None:
        self.command = command
        self.cwd = cwd
        self.process: Optional[subprocess.Popen] = None  # type: ignore[type-arg]
        self.next_id = 0
        self.hello: Dict[str, Any] = {}

    def start(self) -> Dict[str, Any]:
        self.process = subprocess.Popen(
            self.command,
            cwd=self.cwd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            encoding="utf-8",
            bufsize=1,
        )
        self.hello = self.request("hello", protocol=PROTOCOL)
        if self.hello.get("protocol") != PROTOCOL:
            raise AdapterFault(f"adapter speaks protocol {self.hello.get('protocol')!r}, the driver {PROTOCOL}")
        return self.hello

    def stop(self, kill: bool = False) -> None:
        """Close the adapter's input (its signal to exit) and wait for it; ``kill`` it first after a fault."""
        process, self.process = self.process, None
        if process is None:
            return
        if kill:
            process.kill()
        for pipe in (process.stdin, process.stdout):
            try:
                if pipe is not None:
                    pipe.close()
            except OSError:
                pass
        process.wait()

    def restart(self) -> None:
        self.stop(kill=True)
        self.start()

    def request(self, op: str, **params: Any) -> Any:
        """Send one request; return its ``ok`` value, raise ``Thrown`` for a binding error, ``AdapterFault`` for the
        rest."""
        if self.process is None or self.process.poll() is not None:
            raise AdapterFault("the adapter is not running")
        self.next_id += 1
        message = {"id": self.next_id, "op": op, **params}
        assert self.process.stdin is not None and self.process.stdout is not None
        try:
            self.process.stdin.write(json.dumps(message, ensure_ascii=True, separators=(",", ":")) + "\n")
            self.process.stdin.flush()
            line = self.process.stdout.readline()
        except (OSError, UnicodeDecodeError) as error:
            raise AdapterFault(f"{op}: {error}") from error
        if not line:
            code = self.process.wait()
            self.stop()
            raise AdapterFault(f"{op}: the adapter exited (status {code})")
        try:
            response = json.loads(line)
        except ValueError as error:
            raise AdapterFault(f"{op}: not one JSON line: {line[:200]!r}") from error
        if not isinstance(response, dict) or response.get("id") != self.next_id:
            raise AdapterFault(f"{op}: response {line[:200]!r} does not answer request {self.next_id}")
        if "ok" in response:
            return response["ok"]
        if "thrown" in response:
            raise Thrown(response["thrown"])
        raise AdapterFault(f"{op}: {response.get('fault', 'a response with neither ok, thrown nor fault')}")

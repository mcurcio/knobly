"""The driver's end of the adapter protocol (spec/conformance.md section 2): one adapter process, JSON lines on its
standard input and output, one request and its response at a time. Each request waits at most the timeout
(KNOBLY_DRIVER_TIMEOUT seconds, 60 by default): a stalled adapter is a fault, killed, and the run goes on."""

from __future__ import annotations

import json
import os
import queue
import subprocess
import threading
from typing import IO, Any, Dict, List, Optional, Union

PROTOCOL = 1
DEFAULT_TIMEOUT = 60.0


def request_timeout() -> float:
    """Seconds one request may wait for its response: KNOBLY_DRIVER_TIMEOUT, else 60."""
    return float(os.environ.get("KNOBLY_DRIVER_TIMEOUT", DEFAULT_TIMEOUT))


class AdapterFault(Exception):
    """The adapter broke the protocol, failed inside itself, or exited: the case fails, the run goes on."""


class Thrown(Exception):
    """The binding raised one of its own errors (a ``knobly error``): ``error`` is the neutral error object."""

    def __init__(self, error: Dict[str, Any]) -> None:
        super().__init__(error.get("group", "?"))
        self.error = error


class Adapter:
    def __init__(self, command: List[str], cwd: Optional[str]) -> None:
        self.command = command
        self.cwd = cwd
        self.process: Optional[subprocess.Popen] = None  # type: ignore[type-arg]
        self.lines: "queue.Queue[Union[str, Exception]]" = queue.Queue()
        self.timeout = request_timeout()
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
        # One reader thread per process feeds its lines to a queue, so a request can wait for a line with a timeout
        # (a blocking readline cannot be abandoned). The queue is the process's own: a late line never reaches the next.
        self.lines = queue.Queue()
        assert self.process.stdout is not None
        threading.Thread(target=_read_lines, args=(self.process.stdout, self.lines), daemon=True).start()
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
        except OSError as error:
            raise AdapterFault(f"{op}: {error}") from error
        try:
            line = self.lines.get(timeout=self.timeout)
        except queue.Empty:
            self.stop(kill=True)
            raise AdapterFault(f"timed out after {self.timeout:g} s waiting for {op}") from None
        if isinstance(line, Exception):
            raise AdapterFault(f"{op}: {line}") from line
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


def _read_lines(stdout: IO[str], lines: "queue.Queue[Union[str, Exception]]") -> None:
    """Put each line the adapter writes on ``lines``, then "" at end of file (or the read's error)."""
    try:
        for line in stdout:
            lines.put(line)
        lines.put("")
    except (OSError, UnicodeDecodeError, ValueError) as error:  # ValueError: the pipe was closed under the read
        lines.put(error)

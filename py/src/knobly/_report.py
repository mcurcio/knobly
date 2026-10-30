"""Located diagnostics (shared by the low level and the rendered layer), and the one sink that load, value readers
and programs all report into (round 11 review finding 2; R14's report helper). Prior art: HCL's
``hcl.Diagnostics``, PostCSS ``Result.messages``. ``Diagnostics`` implements its generated Protocol
(``villanelle._api.shared``); ``Locatable`` is that module's."""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from types import TracebackType

from villanelle._api import shared
from villanelle._api.codes import DiagnosticCode
from villanelle._api.errors import DiagnosticError
from villanelle._api.limits import PROGRAM_CODE
from villanelle._api.shared import Locatable
from villanelle._origin import Place, Step


@dataclass(frozen=True, slots=True)
class LocatedDiagnostic(shared.LocatedDiagnostic):
    code: DiagnosticCode | str = field()
    message: str = field()
    """For people; not part of the cross-language contract."""
    place: Place = field()
    via: tuple[Step, ...] = field()
    """The variables, uses and extension directives that brought the text to ``place``'s reader; innermost first."""

    def __post_init__(self) -> None:
        """Raise ValueError when ``code`` is neither a DiagnosticCode value nor a namespaced program code."""
        if isinstance(self.code, DiagnosticCode):
            return
        if self.code in _CODES:
            object.__setattr__(self, "code", DiagnosticCode(self.code))
            return
        check_program_code(self.code)

    def __str__(self) -> str:
        return f"{self.place}: {self.code}: {self.message}"


class Collecting:
    """``with problems.collecting(): ...``: a DiagnosticError raised inside is recorded and the block ends; any other
    exception passes through. A class (not ``@contextmanager``) so type checkers know the block can end early."""

    __slots__ = ("_into",)

    def __init__(self, into: Diagnostics, /) -> None:
        self._into = into

    def __enter__(self) -> None:
        return None

    def __exit__(
        self,
        kind: type[BaseException] | None,
        error: BaseException | None,
        trace: TracebackType | None,
        /,
    ) -> bool:
        """True (swallow) for a DiagnosticError only."""
        if isinstance(error, DiagnosticError):
            self._into.add(error.diagnostic)
            return True
        return False


class Diagnostics(shared.Diagnostics):
    __slots__ = ("_items",)

    def __init__(self, initial: Iterable[LocatedDiagnostic] | None = None, /) -> None:
        self._items: list[LocatedDiagnostic] = list(initial or ())

    def __len__(self) -> int:
        return len(self._items)

    def __iter__(self) -> Iterator[LocatedDiagnostic]:
        return iter(tuple(self._items))

    def add(self, diagnostic: LocatedDiagnostic, /) -> None:
        self._items.append(diagnostic)

    def report(self, at: Locatable, message: str, *, code: str) -> None:
        self.add(at.error(message, code=code).diagnostic)

    def collecting(self) -> Collecting:
        return Collecting(self)


_CODES = frozenset(code.value for code in DiagnosticCode)


def check_program_code(code: str) -> None:
    """Raise ValueError unless ``code`` is ``<namespace>/<name>`` (a program's own code; villanelle's are its own)."""
    if not isinstance(code, str) or PROGRAM_CODE.match(code) is None:
        raise ValueError(f'a program\'s code is "<namespace>/<name>", such as "rasl/unknown-node": {code!r}')

"""The one block shape (spec 2.11; owner, 2026-10-29: "Yes, rename now"), implemented once for the three blocks: the
written block (statements), the expansion block (directive expansions) and the rendered block (directives). Each
is a ``collections.abc.Sequence`` (iterate, index, ``len``, ``in``) with ``directives(name)`` and a depth-first
``walk``; its generated Protocol is ``villanelle._api.shared.Block``. A block says only what its items are, which
of them are directives, and what block an item holds. Private; each layer's block subclasses it and its own
generated Protocol."""

from __future__ import annotations

from collections.abc import Callable, Iterator, Sequence
from typing import Generic, TypeVar, overload

ItemT = TypeVar("ItemT")
DirectiveT = TypeVar("DirectiveT")


class BlockBase(Sequence[ItemT], Generic[ItemT, DirectiveT]):
    """What every block does, over the three hooks below."""

    __slots__ = ()

    def _members(self) -> Sequence[ItemT]:
        """Its items now, in written order."""
        raise NotImplementedError

    def _directive(self, item: ItemT, /) -> DirectiveT | None:
        """``item`` as a directive of this block, or None when it is none (a written block's ``@set`` line)."""
        raise NotImplementedError

    def _name(self, directive: DirectiveT, /) -> str:
        """A directive's name, for ``directives(name)``."""
        raise NotImplementedError

    def _inner(self, item: ItemT, /) -> BlockBase[ItemT, DirectiveT] | None:
        """The block ``item`` holds, if any: what ``walk`` descends into."""
        raise NotImplementedError

    @overload
    def __getitem__(self, index: int, /) -> ItemT: ...

    @overload
    def __getitem__(self, index: slice, /) -> tuple[ItemT, ...]: ...

    def __getitem__(self, index: int | slice, /) -> ItemT | tuple[ItemT, ...]:
        items = self._members()
        return items[index] if isinstance(index, int) else tuple(items[index])

    def __len__(self) -> int:
        return len(self._members())

    def __iter__(self) -> Iterator[ItemT]:
        return iter(tuple(self._members()))

    def __repr__(self) -> str:
        return f"{type(self).__name__}({list(self._members())!r})"

    def directives(self, name: str | None = None, /) -> tuple[DirectiveT, ...]:
        found = (self._directive(item) for item in self._members())
        return tuple(d for d in found if d is not None and (name is None or self._name(d) == name))

    def walk(self, *, descend: Callable[[ItemT], bool] | None = None) -> Iterator[ItemT]:
        stack: list[Iterator[ItemT]] = [iter(self)]
        while stack:
            item = next(stack[-1], _END)
            if item is _END:
                stack.pop()
                continue
            assert not isinstance(item, _End)
            yield item
            inner = self._inner(item)
            if inner and (descend is None or descend(item)):
                stack.append(iter(inner))


class _End:
    __slots__ = ()


_END = _End()

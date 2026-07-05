"""Fractional-index positioning for cards within a column.

Drag-and-drop moves a card to a target column and a target index. Rather
than renumbering every sibling on each move (O(n) writes, a write-write
contention hotspot under concurrent drags), a card carries a fractional
``position``: to drop it between neighbours P and N we store the midpoint
``(P + N) / 2``. A move then writes exactly one row — the moved card — and
concurrent drags into different slots never touch the same row.

``position`` is a 20-decimal-place ``DecimalField``. Repeated midpoints in
the *same* gap eventually exhaust that precision; :func:`needs_rebalance`
detects the degenerate case and the caller renumbers the column with evenly
spaced integers (:func:`rebalanced_positions`) — a rare O(n) fallback, not
the steady-state path.

Ties (two cards that raced into the same midpoint) are allowed: ordering is
``(position, created_at, id)``, so a tie is broken deterministically and
self-heals on the next move. ``position`` is intentionally not unique.
"""
from __future__ import annotations

from decimal import Decimal

STEP = Decimal(1)
# Smallest representable gap at the field's precision (20 dp). If two
# neighbours are already this close, a midpoint would round onto one of them.
_EPSILON = Decimal(1).scaleb(-19)  # 1e-19


def position_between(prev: Decimal | None, nxt: Decimal | None) -> Decimal:
    """Return a position that sorts strictly between ``prev`` and ``nxt``.

    ``prev`` / ``nxt`` are the positions of the neighbours the card is
    dropped between (either may be ``None`` at a column edge). The caller
    must check :func:`needs_rebalance` first for the interior case — this
    function assumes there is room.
    """
    if prev is None and nxt is None:
        return Decimal(0)
    if prev is None:
        return nxt - STEP
    if nxt is None:
        return prev + STEP
    return (prev + nxt) / Decimal(2)


def needs_rebalance(prev: Decimal | None, nxt: Decimal | None) -> bool:
    """True when there is no representable position strictly between the two
    interior neighbours (the precision-exhausted case that forces a column
    renumber). Edge inserts (a ``None`` neighbour) never need a rebalance."""
    if prev is None or nxt is None:
        return False
    return (nxt - prev) <= _EPSILON


def rebalanced_positions(count: int) -> list[Decimal]:
    """Evenly spaced integer positions ``[0, 1, 2, ...]`` for ``count`` cards
    listed in their current display order — the renumber fallback."""
    return [Decimal(i) for i in range(count)]

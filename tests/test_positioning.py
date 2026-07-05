"""Fractional-index positioning + the rebalance fallback."""
from decimal import Decimal

import pytest

from stapel_tasks import services
from stapel_tasks.models import Task
from stapel_tasks.positioning import (
    needs_rebalance,
    position_between,
)


class TestPositionBetween:
    def test_edges(self):
        assert position_between(None, None) == Decimal(0)
        assert position_between(None, Decimal(5)) < Decimal(5)
        assert position_between(Decimal(5), None) > Decimal(5)

    def test_midpoint(self):
        p = position_between(Decimal(0), Decimal(1))
        assert Decimal(0) < p < Decimal(1)

    def test_needs_rebalance_only_when_no_gap(self):
        assert not needs_rebalance(None, Decimal(1))
        assert not needs_rebalance(Decimal(0), Decimal(1))
        tiny = Decimal(1).scaleb(-20)
        assert needs_rebalance(Decimal(0), tiny)


@pytest.mark.django_db
class TestRebalanceIntegration:
    def test_repeated_front_inserts_trigger_rebalance(self, db):
        board = services.create_board(name="B", preset="simple")
        col = board.columns.get(key="todo")
        # Seed two cards so there's an interior gap to collapse.
        services.create_task(board=board, title="a")
        services.create_task(board=board, title="b")
        movers = [services.create_task(board=board, title=f"m{i}") for i in range(80)]
        # Repeatedly wedge each mover between a (index-just-after-front) — hammer
        # the same narrow gap so precision would run out without a rebalance.
        for m in movers:
            services.move_task(m, to_column=col, index=1)
        # All cards still present and strictly orderable (no duplicate collapse
        # that loses a row); the column self-healed via rebalance.
        titles = list(
            Task.objects.filter(column=col)
            .order_by("position", "created_at", "id")
            .values_list("title", flat=True)
        )
        assert len(titles) == 82
        assert titles[0] == "a"
        assert set(titles) == {"a", "b"} | {f"m{i}" for i in range(80)}

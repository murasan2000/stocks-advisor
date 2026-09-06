"""AlertsRepository（ウォッチ銘柄アラートの永続化・issue #81）のテスト。"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.services.watchlist.alerts import DetectedAlert
from app.services.watchlist.alerts_repository import AlertsRepository


@pytest.fixture
async def repo(tmp_path: Path) -> AlertsRepository:
    r = AlertsRepository(str(tmp_path / "alerts.db"))
    await r.initialize()
    return r


async def test_create_many_then_list_all(repo: AlertsRepository) -> None:
    await repo.create_many(
        [
            DetectedAlert(
                code="7203", kind="price", old_value=1000.0, new_value=1100.0,
                change_pct=10.0,
            ),
            DetectedAlert(
                code="6758", kind="score", old_value=40.0, new_value=55.0,
            ),
        ]
    )
    alerts = await repo.list_all()
    assert len(alerts) == 2
    codes = {a.code for a in alerts}
    assert codes == {"7203", "6758"}
    price_alert = next(a for a in alerts if a.kind == "price")
    assert price_alert.old_value == 1000.0
    assert price_alert.new_value == 1100.0
    assert price_alert.change_pct == 10.0
    assert price_alert.read is False
    score_alert = next(a for a in alerts if a.kind == "score")
    assert score_alert.change_pct is None


async def test_create_many_with_empty_list_is_noop(repo: AlertsRepository) -> None:
    await repo.create_many([])
    assert await repo.list_all() == []


async def test_list_unread_excludes_read(repo: AlertsRepository) -> None:
    await repo.create_many(
        [DetectedAlert(code="7203", kind="price", old_value=1000.0, new_value=1100.0)]
    )
    assert len(await repo.list_unread()) == 1
    await repo.mark_all_read()
    assert await repo.list_unread() == []
    # 既読後も list_all では引き続き参照できる
    assert len(await repo.list_all()) == 1


async def test_list_all_is_newest_first(repo: AlertsRepository) -> None:
    await repo.create_many(
        [DetectedAlert(code="7203", kind="price", old_value=1000.0, new_value=1100.0)]
    )
    await repo.create_many(
        [DetectedAlert(code="6758", kind="score", old_value=40.0, new_value=55.0)]
    )
    alerts = await repo.list_all()
    assert [a.code for a in alerts] == ["6758", "7203"]


async def test_list_all_respects_limit(repo: AlertsRepository) -> None:
    await repo.create_many(
        [
            DetectedAlert(code=f"{i}", kind="score", old_value=0.0, new_value=20.0)
            for i in range(5)
        ]
    )
    assert len(await repo.list_all(limit=3)) == 3


async def test_mark_all_read_is_idempotent(repo: AlertsRepository) -> None:
    await repo.create_many(
        [DetectedAlert(code="7203", kind="price", old_value=1000.0, new_value=1100.0)]
    )
    await repo.mark_all_read()
    await repo.mark_all_read()  # 2回呼んでもエラーにならない
    assert await repo.list_unread() == []

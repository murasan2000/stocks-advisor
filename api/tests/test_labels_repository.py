"""ラベル（ウォッチリスト銘柄への自由付与タグ）リポジトリのテスト（issue #68）。"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from app.services.watchlist.labels_repository import LabelsRepository


@pytest.fixture
async def repo(tmp_path: Path) -> LabelsRepository:
    r = LabelsRepository(str(tmp_path / "app.db"))
    await r.initialize()
    return r


async def test_create_then_list(repo: LabelsRepository) -> None:
    label = await repo.create("半導体")
    assert label.name == "半導体"
    assert await repo.list_all() == [label]


async def test_create_is_idempotent_by_name(repo: LabelsRepository) -> None:
    first = await repo.create("半導体")
    second = await repo.create("半導体")
    assert first.label_id == second.label_id
    assert len(await repo.list_all()) == 1


async def test_create_strips_whitespace(repo: LabelsRepository) -> None:
    label = await repo.create("  半導体  ")
    assert label.name == "半導体"


async def test_create_handles_concurrent_same_name_race(repo: LabelsRepository) -> None:
    """同時に同名で新規作成しても例外にならず、1つのラベルに収束する（自己レビュー指摘）。

    name には UNIQUE 制約があるため、素朴な「確認してから作成」だけでは片方の
    INSERT が競合して例外になり得る。create() は競合を捕捉して既存行に
    フォールバックすることを確認する。
    """
    results = await asyncio.gather(repo.create("半導体"), repo.create("半導体"))
    assert results[0].label_id == results[1].label_id
    assert len(await repo.list_all()) == 1


async def test_list_all_sorted_by_name(repo: LabelsRepository) -> None:
    await repo.create("ゲーム")
    await repo.create("半導体")
    await repo.create("自動車")
    names = [label.name for label in await repo.list_all()]
    assert names == sorted(names)


async def test_attach_and_labels_by_code(repo: LabelsRepository) -> None:
    label = await repo.create("半導体")
    await repo.attach("6758", label.label_id)
    result = await repo.labels_by_code(["6758"])
    assert [label.name for label in result["6758"]] == ["半導体"]


async def test_attach_is_idempotent(repo: LabelsRepository) -> None:
    label = await repo.create("半導体")
    await repo.attach("6758", label.label_id)
    await repo.attach("6758", label.label_id)
    result = await repo.labels_by_code(["6758"])
    assert len(result["6758"]) == 1


async def test_multiple_labels_per_code(repo: LabelsRepository) -> None:
    a = await repo.create("半導体")
    b = await repo.create("配当")
    await repo.attach("6758", a.label_id)
    await repo.attach("6758", b.label_id)
    result = await repo.labels_by_code(["6758"])
    assert {label.name for label in result["6758"]} == {"半導体", "配当"}


async def test_labels_by_code_omits_codes_without_labels(
    repo: LabelsRepository,
) -> None:
    label = await repo.create("半導体")
    await repo.attach("6758", label.label_id)
    result = await repo.labels_by_code(["6758", "7203"])
    assert "7203" not in result


async def test_labels_by_code_empty_input(repo: LabelsRepository) -> None:
    assert await repo.labels_by_code([]) == {}


async def test_detach_removes_association(repo: LabelsRepository) -> None:
    label = await repo.create("半導体")
    await repo.attach("6758", label.label_id)
    await repo.detach("6758", label.label_id)
    result = await repo.labels_by_code(["6758"])
    assert "6758" not in result


async def test_detach_is_safe_when_not_attached(repo: LabelsRepository) -> None:
    label = await repo.create("半導体")
    await repo.detach("6758", label.label_id)  # 付与されていなくてもエラーにならない


async def test_delete_label_cascades_to_attachments(repo: LabelsRepository) -> None:
    label = await repo.create("半導体")
    await repo.attach("6758", label.label_id)
    await repo.delete(label.label_id)
    assert await repo.list_all() == []
    result = await repo.labels_by_code(["6758"])
    assert "6758" not in result


async def test_delete_is_safe_for_unknown_label_id(repo: LabelsRepository) -> None:
    await repo.delete("does-not-exist")  # エラーにならない


async def test_attach_uppercases_code(repo: LabelsRepository) -> None:
    label = await repo.create("半導体")
    await repo.attach("aapl", label.label_id)
    result = await repo.labels_by_code(["AAPL"])
    assert [label.name for label in result["AAPL"]] == ["半導体"]

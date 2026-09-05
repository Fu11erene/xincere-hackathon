from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from backend.ai.task_decomposition import (
    MAX_DURATION_HOURS,
    MAX_TASKS,
    MIN_DURATION_HOURS,
    TOOL_NAME,
    _clamp_durations,
    _drop_dangling_dependencies,
    _find_cycle_description,
    _validate_task_shape,
    _warn_if_task_count_out_of_range,
    decompose_goal,
)


def _tool_response(tasks: list[dict]) -> SimpleNamespace:
    block = SimpleNamespace(type="tool_use", name=TOOL_NAME, input={"tasks": tasks})
    return SimpleNamespace(content=[block])


def _client_returning(*task_lists: list[dict]) -> MagicMock:
    client = MagicMock()
    client.messages.create.side_effect = [_tool_response(tasks) for tasks in task_lists]
    return client


def _task(id_: str, depends_on: list[str] | None = None, hours: float = 4.0) -> dict:
    return {
        "id": id_,
        "name": f"task {id_}",
        "category": "実装",
        "estimated_duration_hours": hours,
        "depends_on": depends_on or [],
    }


def test_find_cycle_description_detects_cycle():
    tasks = [_task("a", ["b"]), _task("b", ["a"])]
    description = _find_cycle_description(tasks)
    assert description is not None
    assert "循環依存" in description


def test_find_cycle_description_returns_none_for_acyclic_graph():
    tasks = [_task("a"), _task("b", ["a"]), _task("c", ["a", "b"])]
    assert _find_cycle_description(tasks) is None


def test_drop_dangling_dependencies_removes_unknown_ids():
    tasks = [_task("a", ["ghost"])]
    _drop_dangling_dependencies(tasks)
    assert tasks[0]["depends_on"] == []


def test_clamp_durations_clamps_out_of_range_values():
    tasks = [_task("a", hours=1000.0), _task("b", hours=0.01)]
    _clamp_durations(tasks)
    assert tasks[0]["estimated_duration_hours"] == MAX_DURATION_HOURS
    assert tasks[1]["estimated_duration_hours"] == MIN_DURATION_HOURS


def test_validate_task_shape_accepts_well_formed_tasks():
    _validate_task_shape([_task("a")])  # 例外が出ないことを確認


def test_validate_task_shape_rejects_missing_required_field():
    malformed = [{"id": "a", "name": "x"}]  # category/estimated_duration_hours/depends_onが無い
    with pytest.raises(HTTPException) as exc_info:
        _validate_task_shape(malformed)
    assert exc_info.value.status_code == 502


def test_decompose_goal_raises_502_when_ai_omits_required_field():
    malformed = [{"id": "a", "name": "x"}]
    client = _client_returning(malformed)

    with pytest.raises(HTTPException) as exc_info:
        decompose_goal(client, "test-model", "ゴール文", None)

    assert exc_info.value.status_code == 502


def test_decompose_goal_maps_id_to_temp_id():
    client = _client_returning([_task("a"), _task("b", ["a"])])

    result = decompose_goal(client, "test-model", "ゴール文", None)

    assert [t.temp_id for t in result] == ["a", "b"]
    assert result[1].depends_on == ["a"]
    client.messages.create.assert_called_once()


def test_decompose_goal_retries_once_when_cyclic_then_succeeds():
    cyclic = [_task("a", ["b"]), _task("b", ["a"])]
    fixed = [_task("a"), _task("b", ["a"])]
    client = _client_returning(cyclic, fixed)

    result = decompose_goal(client, "test-model", "ゴール文", None)

    assert [t.temp_id for t in result] == ["a", "b"]
    assert client.messages.create.call_count == 2


def test_warn_if_task_count_out_of_range_logs_when_too_few(caplog):
    with caplog.at_level("WARNING"):
        _warn_if_task_count_out_of_range([_task("a")])
    assert any("outside the expected range" in record.message for record in caplog.records)


def test_warn_if_task_count_out_of_range_silent_when_within_bounds(caplog):
    tasks = [_task(str(i)) for i in range(MAX_TASKS)]
    with caplog.at_level("WARNING"):
        _warn_if_task_count_out_of_range(tasks)
    assert caplog.records == []


def test_decompose_goal_raises_after_exhausting_retries_on_persistent_cycle():
    cyclic = [_task("a", ["b"]), _task("b", ["a"])]
    client = _client_returning(cyclic, cyclic, cyclic)

    with pytest.raises(HTTPException) as exc_info:
        decompose_goal(client, "test-model", "ゴール文", None)

    assert exc_info.value.status_code == 502

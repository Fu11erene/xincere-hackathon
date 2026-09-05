import pytest
from fastapi import HTTPException

from backend.schemas import TaskPreview
from backend.validation import validate_task_graph


def _task(temp_id: str, depends_on: list[str] | None = None, hours: float = 2.0) -> TaskPreview:
    return TaskPreview(
        temp_id=temp_id,
        name=f"task {temp_id}",
        category="実装",
        estimated_duration_hours=hours,
        depends_on=depends_on or [],
    )


def test_validate_task_graph_accepts_valid_graph():
    validate_task_graph([_task("a"), _task("b", ["a"])])


def test_validate_task_graph_rejects_duplicate_temp_id():
    with pytest.raises(HTTPException) as exc_info:
        validate_task_graph([_task("a"), _task("a")])
    assert exc_info.value.status_code == 422


def test_validate_task_graph_rejects_unknown_dependency():
    with pytest.raises(HTTPException) as exc_info:
        validate_task_graph([_task("a", ["ghost"])])
    assert exc_info.value.status_code == 422


def test_validate_task_graph_rejects_cycle():
    with pytest.raises(HTTPException) as exc_info:
        validate_task_graph([_task("a", ["b"]), _task("b", ["a"])])
    assert exc_info.value.status_code == 422


def test_validate_task_graph_rejects_empty_task_list():
    with pytest.raises(HTTPException) as exc_info:
        validate_task_graph([])
    assert exc_info.value.status_code == 422


def test_validate_task_graph_rejects_out_of_range_duration():
    with pytest.raises(HTTPException) as exc_info:
        validate_task_graph([_task("a", hours=1000.0)])
    assert exc_info.value.status_code == 422


def test_validate_task_graph_rejects_non_positive_duration():
    with pytest.raises(HTTPException) as exc_info:
        validate_task_graph([_task("a", hours=0.0)])
    assert exc_info.value.status_code == 422

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from backend.db.projects import create_project, get_project, list_projects
from backend.schemas import TaskPreview

FAKE_UUIDS = [f"1111111{i}-1111-1111-1111-111111111111" for i in range(10)]


def _table_mock() -> MagicMock:
    """table("x")呼び出し1つ分のfluentビルダーmock。"""
    return MagicMock()


def _fake_db(tables: dict[str, MagicMock]) -> MagicMock:
    db = MagicMock()
    db.table.side_effect = lambda name: tables[name]
    return db


def test_create_project_persists_tasks_and_maps_dependencies():
    projects_table = _table_mock()
    projects_table.insert.return_value.execute.return_value = SimpleNamespace(
        data=[
            {
                "id": "project-1",
                "goal_text": "ゴール",
                "deadline": None,
                "created_at": "2026-09-05T00:00:00Z",
            }
        ]
    )

    tasks_table = _table_mock()
    deps_table = _table_mock()

    db = _fake_db(
        {"projects": projects_table, "tasks": tasks_table, "task_dependencies": deps_table}
    )

    tasks = [
        TaskPreview(temp_id="a", name="設計", category="設計", estimated_duration_hours=3.0),
        TaskPreview(
            temp_id="b",
            name="実装",
            category="実装",
            estimated_duration_hours=5.0,
            depends_on=["a"],
        ),
    ]

    with patch("backend.db.projects.uuid.uuid4", side_effect=FAKE_UUIDS):
        result = create_project(db, "user-1", "ゴール", None, tasks)

    assert result.id == "project-1"
    task_id_a, task_id_b = FAKE_UUIDS[0], FAKE_UUIDS[1]
    assert [t.id for t in result.tasks] == [task_id_a, task_id_b]
    assert result.tasks[1].depends_on == [task_id_a]

    # task_dependenciesにはtemp_idではなく実際のtask id(採番したUUID)で
    # 書き込まれていること。挿入結果の返却順序には一切依存しない。
    deps_table.insert.assert_called_once_with(
        [{"task_id": task_id_b, "depends_on_task_id": task_id_a}]
    )

    # tasksへのinsertペイロード自体に、こちらで採番したidが含まれていること
    inserted_tasks = tasks_table.insert.call_args[0][0]
    assert [t["id"] for t in inserted_tasks] == [task_id_a, task_id_b]

    # projectsへのinsertにuser_idが含まれること(データ分離の担保)
    projects_table.insert.assert_called_once()
    inserted_project = projects_table.insert.call_args[0][0]
    assert inserted_project["user_id"] == "user-1"


def test_create_project_skips_dependency_insert_when_no_dependencies():
    projects_table = _table_mock()
    projects_table.insert.return_value.execute.return_value = SimpleNamespace(
        data=[
            {
                "id": "project-1",
                "goal_text": "g",
                "deadline": None,
                "created_at": "2026-09-05T00:00:00Z",
            }
        ]
    )
    tasks_table = _table_mock()
    deps_table = _table_mock()

    db = _fake_db(
        {"projects": projects_table, "tasks": tasks_table, "task_dependencies": deps_table}
    )

    with patch("backend.db.projects.uuid.uuid4", side_effect=FAKE_UUIDS):
        create_project(
            db,
            "user-1",
            "g",
            None,
            [TaskPreview(temp_id="a", name="設計", category="設計", estimated_duration_hours=3.0)],
        )

    deps_table.insert.assert_not_called()


def test_get_project_returns_none_when_not_found():
    projects_table = _table_mock()
    projects_table.select.return_value.eq.return_value.eq.return_value.execute.return_value = (
        SimpleNamespace(data=[])
    )
    db = _fake_db({"projects": projects_table})

    assert get_project(db, "user-1", "missing") is None


def test_get_project_builds_dependencies_from_rows():
    projects_table = _table_mock()
    projects_table.select.return_value.eq.return_value.eq.return_value.execute.return_value = (
        SimpleNamespace(
            data=[
                {
                    "id": "project-1",
                    "goal_text": "g",
                    "deadline": None,
                    "created_at": "2026-09-05T00:00:00Z",
                }
            ]
        )
    )

    tasks_table = _table_mock()
    tasks_table.select.return_value.eq.return_value.execute.return_value = SimpleNamespace(
        data=[
            {
                "id": "task-a",
                "project_id": "project-1",
                "name": "設計",
                "category": "設計",
                "original_estimated_duration_hours": 3.0,
                "current_estimated_duration_hours": 3.0,
                "status": "todo",
                "actual_start_at": None,
                "actual_end_at": None,
                "skip_count": 0,
            },
            {
                "id": "task-b",
                "project_id": "project-1",
                "name": "実装",
                "category": "実装",
                "original_estimated_duration_hours": 5.0,
                "current_estimated_duration_hours": 5.0,
                "status": "todo",
                "actual_start_at": None,
                "actual_end_at": None,
                "skip_count": 0,
            },
        ]
    )

    deps_table = _table_mock()
    deps_table.select.return_value.in_.return_value.execute.return_value = SimpleNamespace(
        data=[{"task_id": "task-b", "depends_on_task_id": "task-a"}]
    )

    db = _fake_db(
        {"projects": projects_table, "tasks": tasks_table, "task_dependencies": deps_table}
    )

    result = get_project(db, "user-1", "project-1")

    assert result is not None
    assert result.tasks[0].depends_on == []
    assert result.tasks[1].depends_on == ["task-a"]

    # user_idフィルタがかかっていること
    projects_table.select.return_value.eq.assert_called_with("id", "project-1")
    projects_table.select.return_value.eq.return_value.eq.assert_called_with("user_id", "user-1")


def test_create_project_rolls_back_project_when_task_insert_fails():
    projects_table = _table_mock()
    projects_table.insert.return_value.execute.return_value = SimpleNamespace(
        data=[
            {
                "id": "project-1",
                "goal_text": "g",
                "deadline": None,
                "created_at": "2026-09-05T00:00:00Z",
            }
        ]
    )
    tasks_table = _table_mock()
    tasks_table.insert.side_effect = RuntimeError("db unavailable")

    db = _fake_db({"projects": projects_table, "tasks": tasks_table})

    with pytest.raises(RuntimeError):
        create_project(
            db,
            "user-1",
            "g",
            None,
            [TaskPreview(temp_id="a", name="設計", category="設計", estimated_duration_hours=3.0)],
        )

    projects_table.delete.return_value.eq.assert_called_once_with("id", "project-1")
    projects_table.delete.return_value.eq.return_value.execute.assert_called_once()


def test_list_projects_filters_by_user_id():
    projects_table = _table_mock()
    projects_table.select.return_value.eq.return_value.order.return_value.execute.return_value = (
        SimpleNamespace(
            data=[
                {
                    "id": "project-1",
                    "goal_text": "g",
                    "deadline": None,
                    "created_at": "2026-09-05T00:00:00Z",
                }
            ]
        )
    )
    db = _fake_db({"projects": projects_table})

    result = list_projects(db, "user-1")

    assert [p.id for p in result] == ["project-1"]
    projects_table.select.return_value.eq.assert_called_with("user_id", "user-1")

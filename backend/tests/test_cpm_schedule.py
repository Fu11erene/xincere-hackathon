from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from backend.cpm.schedule import (
    CyclicDependencyError,
    PaceProfile,
    TaskInput,
    compute_schedule,
)

NOW = datetime(2026, 9, 5, 9, 0, tzinfo=UTC)


def _task(
    id_: str,
    hours: float,
    depends_on: list[str] | None = None,
    status: str = "todo",
    category: str = "実装",
    actual_start_at: datetime | None = None,
    actual_end_at: datetime | None = None,
) -> TaskInput:
    return TaskInput(
        id=id_,
        category=category,
        status=status,
        original_estimated_duration_hours=hours,
        actual_start_at=actual_start_at,
        actual_end_at=actual_end_at,
        depends_on=depends_on or [],
    )


def test_empty_task_list_returns_now_as_projected_completion():
    result = compute_schedule([], NOW, None, PaceProfile())
    assert result.tasks == []
    assert result.projected_completion_at == NOW


def test_linear_chain_is_fully_critical():
    tasks = [
        _task("a", 2.0),
        _task("b", 3.0, depends_on=["a"]),
        _task("c", 1.0, depends_on=["b"]),
    ]

    result = compute_schedule(tasks, NOW, None, PaceProfile())
    by_id = {t.id: t for t in result.tasks}

    assert by_id["a"].earliest_start == NOW
    assert by_id["a"].earliest_finish == NOW + timedelta(hours=2)
    assert by_id["b"].earliest_start == NOW + timedelta(hours=2)
    assert by_id["b"].earliest_finish == NOW + timedelta(hours=5)
    assert by_id["c"].earliest_finish == NOW + timedelta(hours=6)
    assert result.projected_completion_at == NOW + timedelta(hours=6)

    for task in result.tasks:
        assert task.slack_hours == pytest.approx(0.0)
        assert task.is_critical is True


def test_diamond_marks_only_the_longer_branch_critical():
    tasks = [
        _task("a", 1.0),
        _task("b", 4.0, depends_on=["a"]),
        _task("c", 1.0, depends_on=["a"]),
        _task("d", 1.0, depends_on=["b", "c"]),
    ]

    result = compute_schedule(tasks, NOW, None, PaceProfile())
    by_id = {t.id: t for t in result.tasks}

    assert by_id["a"].is_critical is True
    assert by_id["b"].is_critical is True
    assert by_id["d"].is_critical is True
    assert by_id["c"].is_critical is False
    assert by_id["c"].slack_hours == pytest.approx(3.0)


def test_done_task_uses_actual_times_and_ignores_pace_coefficient():
    actual_start = NOW - timedelta(hours=10)
    actual_end = NOW - timedelta(hours=6)
    tasks = [
        _task(
            "a",
            hours=2.0,
            status="done",
            actual_start_at=actual_start,
            actual_end_at=actual_end,
        ),
        _task("b", 3.0, depends_on=["a"]),
    ]

    result = compute_schedule(tasks, NOW, None, PaceProfile(pace_coefficient=2.0))
    by_id = {t.id: t for t in result.tasks}

    assert by_id["a"].earliest_start == actual_start
    assert by_id["a"].earliest_finish == actual_end
    assert by_id["a"].current_estimated_duration_hours == pytest.approx(4.0)
    assert by_id["a"].slack_hours == 0.0
    assert by_id["a"].is_critical is False

    # 先行タスクの実績終了はnowより過去なので、後続タスクはnow起点で開始する
    assert by_id["b"].earliest_start == NOW


def test_done_task_missing_actual_timestamps_falls_back_and_warns(caplog):
    """statusはdoneだが実績時刻が欠けているデータ不整合ケース。todo同様に
    フォールバックしつつ、気づけるよう警告ログを残す。
    """
    tasks = [_task("a", 2.0, status="done", actual_start_at=None, actual_end_at=None)]

    with caplog.at_level("WARNING"):
        result = compute_schedule(tasks, NOW, None, PaceProfile())

    task = result.tasks[0]
    assert task.earliest_start == NOW
    assert task.current_estimated_duration_hours == pytest.approx(2.0)
    assert any("missing actual_start_at" in record.message for record in caplog.records)


def test_skipped_task_is_scheduled_like_a_pending_task_not_zero_duration():
    """スキップは「そのタスクを完了扱いにする」ものではない。カテゴリのskip_rateを
    通じて将来のタスクにバッファとして反映される設計(product-requirements.md)
    なので、スキップされたタスク自体は通常通りの見積もり時間で予定に残り続ける。
    """
    tasks = [_task("a", 2.0, status="skipped"), _task("b", 3.0, depends_on=["a"])]

    result = compute_schedule(tasks, NOW, None, PaceProfile())
    by_id = {t.id: t for t in result.tasks}

    assert by_id["a"].current_estimated_duration_hours == pytest.approx(2.0)
    assert by_id["a"].earliest_start == NOW
    assert by_id["a"].earliest_finish == NOW + timedelta(hours=2)
    assert by_id["b"].earliest_start == NOW + timedelta(hours=2)


def test_pace_coefficient_and_skip_rate_scale_duration():
    tasks = [_task("a", 10.0, category="調査")]
    pace_profile = PaceProfile(pace_coefficient=1.3, skip_rate_by_category={"調査": 0.4})

    result = compute_schedule(tasks, NOW, None, pace_profile)

    assert result.tasks[0].current_estimated_duration_hours == pytest.approx(15.6)
    assert result.tasks[0].earliest_finish == NOW + timedelta(hours=15.6)


def test_deadline_pushes_latest_finish_of_sink_task():
    tasks = [_task("a", 2.0)]
    deadline = date(2026, 9, 10)

    result = compute_schedule(tasks, NOW, deadline, PaceProfile())
    task = result.tasks[0]

    deadline_at_jst = datetime(2026, 9, 10, 23, 59, 59, tzinfo=ZoneInfo("Asia/Tokyo"))
    deadline_at = deadline_at_jst.astimezone(UTC)
    assert task.latest_finish == deadline_at
    assert task.latest_start == deadline_at - timedelta(hours=2)
    assert task.is_critical is False
    assert task.slack_hours > 0


def test_cyclic_dependency_raises():
    tasks = [_task("a", 1.0, depends_on=["b"]), _task("b", 1.0, depends_on=["a"])]

    with pytest.raises(CyclicDependencyError):
        compute_schedule(tasks, NOW, None, PaceProfile())

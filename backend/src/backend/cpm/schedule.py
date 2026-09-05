"""CPM(クリティカルパス法)計算エンジン。

.claude/rules/cpm-algorithm.md の実装詳細をそのまま反映した副作用のない純粋関数。
UI/DBから独立させてあり、compute_schedule単体でテストできる。
"""

import logging
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import networkx as nx

logger = logging.getLogger(__name__)

CRITICAL_SLACK_THRESHOLD_HOURS = 0.01

# プロダクトは日本語UI・国内向け(JSTユーザー)前提。deadlineは「その日の終わりまで」を
# 意味するカレンダー日付なので、UTCではなくJSTの23:59:59として解釈する
# (UTCの23:59:59として扱うと実質9時間分の余分なスラックを与えてしまう)。
JST = ZoneInfo("Asia/Tokyo")


class CyclicDependencyError(Exception):
    """タスク依存グラフに循環依存が含まれる場合に送出する。"""


@dataclass(frozen=True)
class PaceProfile:
    pace_coefficient: float = 1.0
    skip_rate_by_category: dict[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class TaskInput:
    id: str
    category: str
    status: str
    original_estimated_duration_hours: float
    actual_start_at: datetime | None
    actual_end_at: datetime | None
    depends_on: list[str]


@dataclass(frozen=True)
class ScheduledTask:
    id: str
    current_estimated_duration_hours: float
    earliest_start: datetime
    earliest_finish: datetime
    latest_start: datetime
    latest_finish: datetime
    slack_hours: float
    is_critical: bool


@dataclass(frozen=True)
class ScheduleResult:
    tasks: list[ScheduledTask]
    projected_completion_at: datetime


def _build_graph(tasks: list[TaskInput]) -> nx.DiGraph:
    graph = nx.DiGraph()
    task_ids = {task.id for task in tasks}
    graph.add_nodes_from(task_ids)
    for task in tasks:
        for dep_id in task.depends_on:
            if dep_id in task_ids:
                graph.add_edge(dep_id, task.id)
    return graph


def compute_schedule(
    tasks: list[TaskInput],
    now: datetime,
    deadline: date | None,
    pace_profile: PaceProfile,
) -> ScheduleResult:
    if not tasks:
        return ScheduleResult(tasks=[], projected_completion_at=now)

    graph = _build_graph(tasks)
    if not nx.is_directed_acyclic_graph(graph):
        raise CyclicDependencyError("task dependency graph contains a cycle")

    by_id = {task.id: task for task in tasks}
    order = list(nx.topological_sort(graph))

    # 1. フォワードパス(ES/EF)
    earliest_start: dict[str, datetime] = {}
    earliest_finish: dict[str, datetime] = {}
    duration_hours: dict[str, float] = {}

    for task_id in order:
        task = by_id[task_id]

        if task.status == "done" and (task.actual_start_at is None or task.actual_end_at is None):
            # データ不整合(完了扱いなのに実績時刻が欠落)。安全側としてスケジューリング
            # 対象(todo扱い)にフォールバックするが、気づけるようログには残す。
            logger.warning(
                "task %s is 'done' but missing actual_start_at/actual_end_at; "
                "falling back to normal scheduling",
                task_id,
            )

        if (
            task.status == "done"
            and task.actual_start_at is not None
            and task.actual_end_at is not None
        ):
            earliest_start[task_id] = task.actual_start_at
            earliest_finish[task_id] = task.actual_end_at
            duration_hours[task_id] = (
                task.actual_end_at - task.actual_start_at
            ).total_seconds() / 3600
            continue

        # "skipped"は完了していないタスクなので、"todo"/"in_progress"と同じ扱いで
        # 通常通りスケジューリングする(product-requirements.mdの通り、スキップは
        # そのタスク自体を消すのではなく、カテゴリのskip_rateとして将来のタスクの
        # バッファに反映される仕組み)。
        skip_rate = pace_profile.skip_rate_by_category.get(task.category, 0.0)
        current_duration = (
            task.original_estimated_duration_hours
            * pace_profile.pace_coefficient
            * (1 + skip_rate * 0.5)
        )
        duration_hours[task_id] = current_duration

        predecessor_finishes = [earliest_finish[dep_id] for dep_id in graph.predecessors(task_id)]
        task_start = max(now, *predecessor_finishes) if predecessor_finishes else now
        earliest_start[task_id] = task_start
        earliest_finish[task_id] = task_start + timedelta(hours=current_duration)

    project_completion_at = max(earliest_finish.values())
    deadline_at = (
        datetime.combine(deadline, time(23, 59, 59), tzinfo=JST).astimezone(now.tzinfo)
        if deadline is not None
        else project_completion_at
    )

    # 2. バックワードパス(LS/LF)
    latest_start: dict[str, datetime] = {}
    latest_finish: dict[str, datetime] = {}

    for task_id in reversed(order):
        task = by_id[task_id]

        if task.status == "done":
            latest_start[task_id] = earliest_start[task_id]
            latest_finish[task_id] = earliest_finish[task_id]
            continue

        successor_starts = [latest_start[succ_id] for succ_id in graph.successors(task_id)]
        task_finish = min(successor_starts) if successor_starts else deadline_at
        latest_finish[task_id] = task_finish
        latest_start[task_id] = task_finish - timedelta(hours=duration_hours[task_id])

    # 3. スラック・クリティカルパス判定
    scheduled_tasks = []
    for task_id in order:
        task = by_id[task_id]
        if task.status == "done":
            slack_hours = 0.0
            is_critical = False
        else:
            slack_hours = (latest_start[task_id] - earliest_start[task_id]).total_seconds() / 3600
            is_critical = slack_hours <= CRITICAL_SLACK_THRESHOLD_HOURS

        scheduled_tasks.append(
            ScheduledTask(
                id=task_id,
                current_estimated_duration_hours=duration_hours[task_id],
                earliest_start=earliest_start[task_id],
                earliest_finish=earliest_finish[task_id],
                latest_start=latest_start[task_id],
                latest_finish=latest_finish[task_id],
                slack_hours=slack_hours,
                is_critical=is_critical,
            )
        )

    return ScheduleResult(tasks=scheduled_tasks, projected_completion_at=project_completion_at)

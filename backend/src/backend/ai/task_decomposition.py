"""AIタスク分解: ゴール文からCPMで使えるタスク依存グラフを生成する。

設計は .claude/rules/ai-task-decomposition.md を参照。
プロンプトだけに頼らず、循環依存検知・見積もり時間クランプ・並行度チェックを
決定的な後処理として実施する。
"""

import logging
from datetime import date

import networkx as nx
from anthropic import Anthropic
from fastapi import HTTPException, status

from backend.schemas import TaskPreview

logger = logging.getLogger(__name__)

MIN_TASKS = 5
MAX_TASKS = 15
MIN_DURATION_HOURS = 0.5
MAX_DURATION_HOURS = 40.0
MAX_ATTEMPTS = 3

SYSTEM_PROMPT = """\
あなたはプロジェクトマネジメントの専門家です。
ユーザーが入力した目標を、クリティカルパス分析（CPM）に使えるタスク依存グラフに分解してください。

制約:
- タスク数は5〜15個程度にする
- 各タスクの見積もり時間は現実的な範囲にする（極端に短い/長い値を避ける）
- 依存関係は目標の実態に忠実に設計する。無理に直列や並列の構造を作らない
- 循環依存（AがBに依存し、BがAに依存する等）を作らない
- 出力は指定のJSON schemaに厳密に従い、説明文やコードブロックの前置きは付けない
"""

TOOL_NAME = "emit_tasks"

_TASK_TOOL_SCHEMA = {
    "name": TOOL_NAME,
    "description": "ゴールから分解したタスク依存グラフを出力する。",
    "input_schema": {
        "type": "object",
        "properties": {
            "tasks": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string", "description": "タスクの一意な識別子"},
                        "name": {"type": "string"},
                        "category": {
                            "type": "string",
                            "description": "例: 調査, 設計, 実装, テスト, 準備 など",
                        },
                        "estimated_duration_hours": {"type": "number"},
                        "depends_on": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "先行タスクのid一覧",
                        },
                    },
                    "required": [
                        "id",
                        "name",
                        "category",
                        "estimated_duration_hours",
                        "depends_on",
                    ],
                },
            },
        },
        "required": ["tasks"],
    },
}


def _build_user_prompt(goal_text: str, deadline: date | None) -> str:
    lines = [f"目標: {goal_text}"]
    if deadline is not None:
        lines.append(f"締切: {deadline.isoformat()}")
    else:
        lines.append("締切: 指定なし")
    return "\n".join(lines)


def _call_model(
    client: Anthropic,
    model: str,
    goal_text: str,
    deadline: date | None,
    correction: str | None,
) -> list[dict]:
    messages: list[dict] = [{"role": "user", "content": _build_user_prompt(goal_text, deadline)}]
    if correction:
        messages.append({"role": "assistant", "content": "(前回の出力は破棄)"})
        messages.append({"role": "user", "content": correction})

    response = client.messages.create(
        model=model,
        max_tokens=4096,
        system=SYSTEM_PROMPT,
        tools=[_TASK_TOOL_SCHEMA],
        tool_choice={"type": "tool", "name": TOOL_NAME},
        messages=messages,
    )

    for block in response.content:
        if getattr(block, "type", None) == "tool_use" and block.name == TOOL_NAME:
            return list(block.input.get("tasks", []))

    raise HTTPException(
        status_code=status.HTTP_502_BAD_GATEWAY,
        detail="AIがタスク分解の出力を返しませんでした",
    )


_REQUIRED_TASK_FIELDS = ("id", "name", "category", "estimated_duration_hours", "depends_on")


def _validate_task_shape(tasks: list[dict]) -> None:
    """ツールスキーマのrequired指定はモデルが必ず守るとは限らないため、後続処理が
    素の辞書添字アクセス(KeyError->未処理の500)で落ちる前に、ここで明示的に502へ
    変換する。
    """
    for task in tasks:
        missing = [field for field in _REQUIRED_TASK_FIELDS if field not in task]
        if missing:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"AIの出力に必須フィールドが欠けています: {missing}",
            )


def _find_cycle_description(tasks: list[dict]) -> str | None:
    """循環依存があれば説明文を返す。なければNone。"""
    graph = nx.DiGraph()
    ids = {t["id"] for t in tasks}
    graph.add_nodes_from(ids)
    for task in tasks:
        for dep in task.get("depends_on", []):
            if dep in ids:
                graph.add_edge(dep, task["id"])

    if nx.is_directed_acyclic_graph(graph):
        return None

    cycle = next(nx.simple_cycles(graph))
    return "循環依存が検出されました: " + " -> ".join([*cycle, cycle[0]])


def _drop_dangling_dependencies(tasks: list[dict]) -> None:
    """存在しないidへのdepends_onを取り除く(モデルの出力ミス対策)。"""
    ids = {t["id"] for t in tasks}
    for task in tasks:
        valid_deps = [d for d in task.get("depends_on", []) if d in ids]
        dropped = len(task.get("depends_on", [])) - len(valid_deps)
        if dropped:
            logger.warning(
                "task %s references %d unknown depends_on id(s); dropping them",
                task.get("id"),
                dropped,
            )
        task["depends_on"] = valid_deps


def _clamp_durations(tasks: list[dict]) -> None:
    for task in tasks:
        original = task["estimated_duration_hours"]
        clamped = min(max(original, MIN_DURATION_HOURS), MAX_DURATION_HOURS)
        if clamped != original:
            logger.warning(
                "task %s estimated_duration_hours %.2f clamped to %.2f",
                task.get("id"),
                original,
                clamped,
            )
        task["estimated_duration_hours"] = clamped


def _warn_if_task_count_out_of_range(tasks: list[dict]) -> None:
    """タスク数が5〜15個程度というシステムプロンプトの制約から外れていないかの
    ログのみの検知(再生成のトリガーにはしない。並行度チェックと同じ方針)。
    """
    if not (MIN_TASKS <= len(tasks) <= MAX_TASKS):
        logger.warning(
            "decomposed task count %d is outside the expected range [%d, %d]",
            len(tasks),
            MIN_TASKS,
            MAX_TASKS,
        )


def _warn_if_fully_serial(tasks: list[dict]) -> None:
    """全タスクが一本道(並行タスクなし)になっていないかをログに残すだけの検知。"""
    if len(tasks) <= 1:
        return
    if all(len(task.get("depends_on", [])) <= 1 for task in tasks):
        in_degree_one_count = sum(1 for task in tasks if len(task.get("depends_on", [])) == 1)
        if in_degree_one_count == len(tasks) - 1:
            logger.warning("decomposed tasks form a fully serial chain (no parallel tasks)")


def decompose_goal(
    client: Anthropic,
    model: str,
    goal_text: str,
    deadline: date | None = None,
) -> list[TaskPreview]:
    """ゴール文からタスク依存グラフを生成する(非永続化のプレビュー用)。"""
    correction: str | None = None

    for attempt in range(1, MAX_ATTEMPTS + 1):
        tasks = _call_model(client, model, goal_text, deadline, correction)
        _validate_task_shape(tasks)
        _drop_dangling_dependencies(tasks)

        cycle_description = _find_cycle_description(tasks)
        if cycle_description is None:
            break

        logger.warning("attempt %d/%d: %s", attempt, MAX_ATTEMPTS, cycle_description)
        correction = (
            f"{cycle_description}\n"
            "循環依存のない依存関係グラフになるよう、tasksを作り直してください。"
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="AIタスク分解が循環依存を解消できませんでした",
        )

    _clamp_durations(tasks)
    _warn_if_task_count_out_of_range(tasks)
    _warn_if_fully_serial(tasks)

    return [
        TaskPreview(
            temp_id=task["id"],
            name=task["name"],
            category=task["category"],
            estimated_duration_hours=task["estimated_duration_hours"],
            depends_on=task["depends_on"],
        )
        for task in tasks
    ]

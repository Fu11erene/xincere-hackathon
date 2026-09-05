"""ユーザーが編集した後のタスクグラフを、永続化前に検証する。

AIプレビュー経路(ai/task_decomposition.py)には循環依存検知・不正参照の除去・
見積もり時間クランプがあるが、POST /projects はプレビューをユーザーが手直しした
結果を受け取るため、同じ保証が失われている。保存前にここで同種の検証をかける。
プレビュー経路は「自動補正して継続」だが、ここはユーザーの直接入力を保存する場面
のため、黙って補正はせず422で差し戻す。
"""

import networkx as nx
from fastapi import HTTPException, status

from backend.ai.task_decomposition import MAX_DURATION_HOURS, MAX_TASKS, MIN_DURATION_HOURS
from backend.schemas import TaskPreview

# AIの目標タスク数(5〜15個、MAX_TASKS)はソフトな目安でしかないため、ユーザーが
# 手直しでいくらか増やす分の余地を持たせつつ、際限のない件数(数百〜数千)での
# 永続化だけは防ぐ上限としてMAX_TASKSの倍を上限にする。
MAX_PERSISTED_TASKS = MAX_TASKS * 2


def validate_task_graph(tasks: list[TaskPreview]) -> None:
    if not tasks:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="tasksが空です",
        )

    if len(tasks) > MAX_PERSISTED_TASKS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"tasksが多すぎます: {len(tasks)}件(上限: {MAX_PERSISTED_TASKS}件)",
        )

    for task in tasks:
        if not (MIN_DURATION_HOURS <= task.estimated_duration_hours <= MAX_DURATION_HOURS):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=(
                    f"task '{task.temp_id}' のestimated_duration_hoursが範囲外です: "
                    f"{task.estimated_duration_hours}"
                    f"(許容範囲: {MIN_DURATION_HOURS}〜{MAX_DURATION_HOURS})"
                ),
            )

    ids = [task.temp_id for task in tasks]
    if len(ids) != len(set(ids)):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="tasks[].temp_id が重複しています",
        )

    id_set = set(ids)
    for task in tasks:
        unknown = [dep for dep in task.depends_on if dep not in id_set]
        if unknown:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"task '{task.temp_id}' が存在しないtemp_idに依存しています: {unknown}",
            )

    graph = nx.DiGraph()
    graph.add_nodes_from(ids)
    for task in tasks:
        for dep in task.depends_on:
            graph.add_edge(dep, task.temp_id)

    if not nx.is_directed_acyclic_graph(graph):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="tasksの依存関係に循環があります",
        )

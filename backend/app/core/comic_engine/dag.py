"""
DAG 拓扑排序 — Kahn 算法，返回可并行执行的 batch 列表。
来源: backend-myagent2/app/engine/dag.py (原样迁移)
"""
from __future__ import annotations

from collections import defaultdict, deque
from typing import Any


def topological_sort(nodes: dict[str, Any], edges: list[dict]) -> list[list[str]]:
    """
    Kahn's algorithm — returns batches of node IDs that can be executed in parallel.
    Each batch contains nodes with zero remaining in-degree.
    """
    adj: dict[str, list[str]] = defaultdict(list)
    in_degree: dict[str, int] = {nid: 0 for nid in nodes}

    for e in edges:
        src = e["source"]
        tgt = e["target"]
        if src in nodes and tgt in nodes:
            adj[src].append(tgt)
            in_degree[tgt] = in_degree.get(tgt, 0) + 1

    queue = deque(nid for nid, d in in_degree.items() if d == 0)
    batches: list[list[str]] = []

    while queue:
        batch = list(queue)
        batches.append(batch)
        next_queue: deque[str] = deque()
        for nid in batch:
            for neighbor in adj[nid]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    next_queue.append(neighbor)
        queue = next_queue

    visited_count = sum(len(b) for b in batches)
    if visited_count != len(nodes):
        missing = set(nodes.keys()) - {nid for b in batches for nid in b}
        raise ValueError(f"Cycle detected in DAG. Unreachable nodes: {missing}")

    return batches


def resolve_condition_edges(
    edges: list[dict], node_id: str, branch_result: str | None
) -> list[str]:
    """Given a condition node's output, find which downstream nodes to activate."""
    targets: list[str] = []
    for e in edges:
        if e["source"] != node_id:
            continue
        handle = e.get("sourceHandle", "")
        if not handle or handle == branch_result:
            targets.append(e["target"])
    return targets

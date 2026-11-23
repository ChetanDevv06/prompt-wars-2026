"""
Domain logic: DAG dependency validation for project resource requirements.

Pure Python — no ORM, no HTTP, no FastAPI concerns.
"""

from __future__ import annotations

from collections import deque
from uuid import UUID


class DependencyCycleError(ValueError):
    """Raised when a proposed dependency would introduce a cycle."""

    def __init__(self, cycle_path: list[UUID]) -> None:
        path_str = " → ".join(str(uid) for uid in cycle_path)
        super().__init__(f"Dependency graph contains a cycle: {path_str}")
        self.cycle_path = cycle_path


def detect_cycle(
    adjacency: dict[UUID, list[UUID]],
    start: UUID,
) -> list[UUID] | None:
    """
    Detect a cycle reachable from *start* using DFS.

    Returns the cycle path if found, or None if the graph is acyclic.

    Args:
        adjacency: Maps requirement_id → list[dependency_id] (directed edge means
                   "depends on").
        start:     Root node to traverse from.
    """
    visited: set[UUID] = set()
    path: list[UUID] = []

    def dfs(node: UUID) -> bool:
        if node in path:
            return True  # cycle detected
        if node in visited:
            return False
        visited.add(node)
        path.append(node)
        for neighbour in adjacency.get(node, []):
            if dfs(neighbour):
                return True
        path.pop()
        return False

    if dfs(start):
        return path[:]
    return None


def topological_sort(adjacency: dict[UUID, list[UUID]]) -> list[UUID]:
    """
    Return nodes in topological order (Kahn's algorithm).

    Raises DependencyCycleError if the graph is not a DAG.
    """
    # Compute in-degrees
    in_degree: dict[UUID, int] = dict.fromkeys(adjacency, 0)
    for deps in adjacency.values():
        for dep in deps:
            in_degree[dep] = in_degree.get(dep, 0) + 1

    queue: deque[UUID] = deque(node for node, deg in in_degree.items() if deg == 0)
    result: list[UUID] = []

    while queue:
        node = queue.popleft()
        result.append(node)
        for neighbour in adjacency.get(node, []):
            in_degree[neighbour] -= 1
            if in_degree[neighbour] == 0:
                queue.append(neighbour)

    if len(result) != len(in_degree):
        cycle_nodes = [n for n, d in in_degree.items() if d > 0]
        raise DependencyCycleError(cycle_nodes)

    return result


def validate_no_cycle(
    adjacency: dict[UUID, list[UUID]],
    new_from: UUID,
    new_to: UUID,
) -> None:
    """
    Validate that adding edge (new_from → new_to) does not create a cycle.

    Raises DependencyCycleError if a cycle would result.
    """
    test_graph = {k: list(v) for k, v in adjacency.items()}
    test_graph.setdefault(new_from, []).append(new_to)

    cycle = detect_cycle(test_graph, new_from)
    if cycle is not None:
        raise DependencyCycleError(cycle)

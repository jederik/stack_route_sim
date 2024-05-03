import math
import random
from typing import Callable

CostGraph = dict[int, dict[int, float]]


def reachabilities(adj_lists: CostGraph) -> list[list[bool]]:
    n = len(adj_lists)
    cover = [[False for _ in range(n)] for _ in range(n)]
    for i in range(n):
        cover[i][i] = True
        for j in adj_lists[i].keys():
            cover[i][j] = True
    for k in range(n):
        for i in range(n):
            for j in range(n):
                if cover[i][k] and cover[k][j]:
                    cover[i][j] = True
    return cover


def distances(adj_lists: CostGraph) -> list[list[float]]:
    n = len(adj_lists)
    dist = [[math.inf for _ in range(n)] for _ in range(n)]
    for i in range(n):
        for j, cost in adj_lists[i].items():
            dist[i][j] = cost
        dist[i][i] = 0
    for k in range(n):
        for i in range(n):
            for j in range(n):
                detour = dist[i][k] + dist[k][j]
                if detour < dist[i][j]:
                    dist[i][j] = detour
    return dist


def generate_gilbert_graph(
        n: int,
        p: float, rnd: random.Random,
        cost_generator: Callable[[int, int], tuple[float, float]]
) -> CostGraph:
    graph: CostGraph = {}
    for i in range(n):
        graph[i] = {}
    for i in range(n):
        for j in range(n):
            if p > rnd.random():
                forward_cost, backward_cost = cost_generator(i, j)
                graph[i][j] = forward_cost
                graph[j][i] = backward_cost
    return graph

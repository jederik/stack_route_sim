import math


def reachabilities(adj_lists: list[list[int]]) -> list[list[bool]]:
    n = len(adj_lists)
    cover = [[False for _ in range(n)] for _ in range(n)]
    for i in range(n):
        cover[i][i] = True
        for j in adj_lists[i]:
            cover[i][j] = True
    for k in range(n):
        for i in range(n):
            for j in range(n):
                if cover[i][k] and cover[k][j]:
                    cover[i][j] = True
    return cover


def distances(adj_lists: list[dict[int, float]]) -> list[list[float]]:
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

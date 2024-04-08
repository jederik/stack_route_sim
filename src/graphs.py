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

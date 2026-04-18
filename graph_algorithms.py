"""
graph_algorithms.py
图算法模块。

作用：
1. 实现基于距离的最短路径搜索；
2. 实现基于当前交通状态的最短时间路径搜索；
3. 提供路径重建、路径长度统计等工具函数。
"""

from __future__ import annotations

import heapq
from typing import Callable, Dict, List, Optional, Tuple

from models import Edge, Graph


class PathNotFoundError(Exception):
    """当两个节点之间不存在可达路径时抛出。"""


class GraphAlgorithms:
    """图算法工具类。"""

    @staticmethod
    def shortest_path_by_distance(graph: Graph, start: int, end: int) -> Tuple[List[int], float]:
        """
        使用 Dijkstra 算法计算最短距离路径。

        返回：
            (path, total_distance)
            path 为节点编号列表，例如 [1, 4, 7, 9]
        """
        return GraphAlgorithms._dijkstra(
            graph=graph,
            start=start,
            end=end,
            weight_func=lambda edge: edge.length,
        )

    @staticmethod
    def shortest_path_by_time(graph: Graph, start: int, end: int) -> Tuple[List[int], float]:
        """
        使用 Dijkstra 算法计算当前交通状态下的最短时间路径。

        边权取当前道路通行时间 edge.travel_time()。
        """
        return GraphAlgorithms._dijkstra(
            graph=graph,
            start=start,
            end=end,
            weight_func=lambda edge: edge.travel_time(),
        )

    @staticmethod
    def path_to_edges(graph: Graph, path: List[int]) -> List[Edge]:
        """将节点路径转换为边对象列表。"""
        edges: List[Edge] = []
        if len(path) < 2:
            return edges

        for i in range(len(path) - 1):
            edge = graph.get_edge_by_nodes(path[i], path[i + 1])
            if edge is None:
                raise PathNotFoundError(f"路径中缺少边: {path[i]} -> {path[i + 1]}")
            edges.append(edge)

        return edges

    @staticmethod
    def calculate_path_distance(graph: Graph, path: List[int]) -> float:
        """计算路径总长度。"""
        return sum(edge.length for edge in GraphAlgorithms.path_to_edges(graph, path))

    @staticmethod
    def calculate_path_time(graph: Graph, path: List[int]) -> float:
        """计算路径总通行时间。"""
        return sum(edge.travel_time() for edge in GraphAlgorithms.path_to_edges(graph, path))

    @staticmethod
    def _dijkstra(
        graph: Graph,
        start: int,
        end: int,
        weight_func: Callable[[Edge], float],
    ) -> Tuple[List[int], float]:
        """
        通用 Dijkstra 实现。

        参数：
            graph: 图对象
            start: 起点编号
            end: 终点编号
            weight_func: 边权函数

        返回：
            (最优路径节点列表, 总权重)
        """
        if not graph.has_node(start):
            raise ValueError(f"起点不存在: {start}")
        if not graph.has_node(end):
            raise ValueError(f"终点不存在: {end}")
        if start == end:
            return [start], 0.0

        distances: Dict[int, float] = {node_id: float("inf") for node_id in graph.nodes}
        previous: Dict[int, Optional[int]] = {node_id: None for node_id in graph.nodes}
        visited = set()

        distances[start] = 0.0
        priority_queue: List[Tuple[float, int]] = [(0.0, start)]

        while priority_queue:
            current_distance, current_node = heapq.heappop(priority_queue)

            if current_node in visited:
                continue
            visited.add(current_node)

            if current_node == end:
                break

            for edge in graph.outgoing_edges(current_node):
                neighbor = edge.end
                if neighbor in visited:
                    continue

                weight = weight_func(edge)
                if weight == float("inf"):
                    continue

                new_distance = current_distance + weight
                if new_distance < distances[neighbor]:
                    distances[neighbor] = new_distance
                    previous[neighbor] = current_node
                    heapq.heappush(priority_queue, (new_distance, neighbor))

        if distances[end] == float("inf"):
            raise PathNotFoundError(f"节点 {start} 无法到达节点 {end}")

        path = GraphAlgorithms._reconstruct_path(previous, start, end)
        return path, distances[end]

    @staticmethod
    def _reconstruct_path(previous: Dict[int, Optional[int]], start: int, end: int) -> List[int]:
        """根据前驱表重建路径。"""
        path: List[int] = []
        current: Optional[int] = end

        while current is not None:
            path.append(current)
            current = previous[current]

        path.reverse()

        if not path or path[0] != start:
            raise PathNotFoundError(f"无法从前驱表重建路径: {start} -> {end}")

        return path


if __name__ == "__main__":
    from map_generator import MapGenerator

    generator = MapGenerator(seed=42)
    graph = generator.generate_map()

    start_node = 0
    end_node = min(20, graph.node_count() - 1)

    path1, distance = GraphAlgorithms.shortest_path_by_distance(graph, start_node, end_node)
    print("按距离最短路径:", path1)
    print("总距离:", round(distance, 2))

    path2, time_cost = GraphAlgorithms.shortest_path_by_time(graph, start_node, end_node)
    print("按时间最短路径:", path2)
    print("总时间:", round(time_cost, 2))

"""
map_generator.py
随机地图生成模块。

作用：
1. 在二维平面内随机生成节点；
2. 为每个节点连接若干附近节点，形成道路；
3. 尽量避免不合理的道路相交；
4. 保证生成图是连通图；
5. 为每条边分配长度与容量等属性。
"""

from __future__ import annotations

import math
import random
from typing import List, Optional, Set, Tuple

from config import CONFIG
from models import Edge, Graph, Node


class MapGenerator:
    """地图生成器。"""

    def __init__(self, seed: Optional[int] = None) -> None:
        self.random = random.Random(seed)
        self._base_edge_id = 0

    def generate_map(self) -> Graph:
        """生成一个满足基本要求的随机连通地图。"""
        graph = Graph()

        nodes = self._generate_nodes(CONFIG.MAP.NODE_COUNT)
        for node in nodes:
            graph.add_node(node)

        # 第一步：先构造一棵生成树，保证图连通
        self._build_spanning_connections(graph)

        # 第二步：再补充局部近邻连接，增强道路网络
        self._add_local_connections(graph)

        return graph

    def _generate_nodes(self, count: int) -> List[Node]:
        """在二维平面中随机生成节点。"""
        nodes: List[Node] = []
        for node_id in range(count):
            x = self.random.uniform(CONFIG.MAP.MAP_MIN_X, CONFIG.MAP.MAP_MAX_X)
            y = self.random.uniform(CONFIG.MAP.MAP_MIN_Y, CONFIG.MAP.MAP_MAX_Y)
            nodes.append(Node(node_id=node_id, x=x, y=y, name=f"P{node_id}"))
        return nodes

    def _build_spanning_connections(self, graph: Graph) -> None:
        """
        利用“每次连接到最近已加入节点”的方式构造连通图。
        这样不一定是最小生成树，但能较稳定地形成较自然的道路结构。
        """
        node_ids = list(graph.nodes.keys())
        if not node_ids:
            return

        connected: Set[int] = {node_ids[0]}
        remaining: Set[int] = set(node_ids[1:])

        while remaining:
            best_pair: Optional[Tuple[int, int, float]] = None

            for node_id in remaining:
                node = graph.nodes[node_id]
                nearest_connected = None
                nearest_distance = float("inf")

                for connected_id in connected:
                    other = graph.nodes[connected_id]
                    distance = node.distance_to(other)
                    if distance < nearest_distance:
                        nearest_distance = distance
                        nearest_connected = connected_id

                if nearest_connected is not None:
                    candidate = (node_id, nearest_connected, nearest_distance)
                    if best_pair is None or candidate[2] < best_pair[2]:
                        best_pair = candidate

            if best_pair is None:
                break

            start_id, end_id, distance = best_pair
            if self._can_add_undirected_edge(graph, start_id, end_id):
                self._add_undirected_edge(graph, start_id, end_id, distance)
            else:
                # 若最近边会相交，则尝试寻找其他已连接节点
                alternative_added = False
                sorted_connected = sorted(
                    connected,
                    key=lambda cid: graph.nodes[start_id].distance_to(graph.nodes[cid]),
                )
                for alt_id in sorted_connected:
                    alt_distance = graph.nodes[start_id].distance_to(graph.nodes[alt_id])
                    if self._can_add_undirected_edge(graph, start_id, alt_id):
                        self._add_undirected_edge(graph, start_id, alt_id, alt_distance)
                        alternative_added = True
                        break

                if not alternative_added:
                    # 极端情况下允许跳过相交检测，优先保证连通
                    self._add_undirected_edge(graph, start_id, end_id, distance)

            connected.add(start_id)
            remaining.remove(start_id)

    def _add_local_connections(self, graph: Graph) -> None:
        """为每个节点增加若干条近邻连接。"""
        node_ids = list(graph.nodes.keys())

        for node_id in node_ids:
            current_neighbors = set(graph.neighbors(node_id))
            target_degree = self.random.randint(
                CONFIG.MAP.MIN_NEIGHBORS,
                CONFIG.MAP.MAX_NEIGHBORS,
            )

            if len(current_neighbors) >= target_degree:
                continue

            candidates = self._sorted_neighbor_candidates(graph, node_id)
            for other_id, distance in candidates:
                if other_id == node_id:
                    continue
                if other_id in current_neighbors:
                    continue
                if len(current_neighbors) >= target_degree:
                    break
                if self._has_connection(graph, node_id, other_id):
                    continue
                if not self._can_add_undirected_edge(graph, node_id, other_id):
                    continue

                self._add_undirected_edge(graph, node_id, other_id, distance)
                current_neighbors.add(other_id)

    def _sorted_neighbor_candidates(self, graph: Graph, node_id: int) -> List[Tuple[int, float]]:
        """返回按距离从近到远排序的候选邻居。"""
        base = graph.nodes[node_id]
        candidates: List[Tuple[int, float]] = []
        for other_id, other in graph.nodes.items():
            if other_id == node_id:
                continue
            candidates.append((other_id, base.distance_to(other)))
        candidates.sort(key=lambda item: item[1])
        return candidates

    def _has_connection(self, graph: Graph, a: int, b: int) -> bool:
        """判断两个节点之间是否已经存在连接。"""
        return graph.get_edge_by_nodes(a, b) is not None or graph.get_edge_by_nodes(b, a) is not None

    def _add_undirected_edge(self, graph: Graph, a: int, b: int, length: float) -> None:
        """添加无向边（内部通过双向有向边实现）。"""
        capacity = self.random.randint(
            CONFIG.TRAFFIC.MIN_EDGE_CAPACITY,
            CONFIG.TRAFFIC.MAX_EDGE_CAPACITY,
        )
        edge = Edge(
            edge_id=self._next_edge_id(),
            start=a,
            end=b,
            length=length,
            capacity=capacity,
            current_vehicles=0,
        )
        graph.add_edge(edge, bidirectional=True)

    def _next_edge_id(self) -> int:
        """生成新的边编号。"""
        edge_id = self._base_edge_id
        self._base_edge_id += 2
        return edge_id

    def _can_add_undirected_edge(self, graph: Graph, a: int, b: int) -> bool:
        """
        判断新增道路是否合理。
        当前规则：
        1. 不能重复连边；
        2. 不与已有道路发生不合理相交；
        3. 允许在共享端点处相交。
        """
        if a == b:
            return False
        if self._has_connection(graph, a, b):
            return False

        new_a = graph.nodes[a]
        new_b = graph.nodes[b]

        checked_pairs: Set[Tuple[int, int]] = set()
        for edge in graph.edges.values():
            u, v = edge.start, edge.end

            # 无向边只检查一次
            key = tuple(sorted((u, v)))
            if key in checked_pairs:
                continue
            checked_pairs.add(key)

            if len({a, b, u, v}) < 4:
                # 共享端点，认为合理
                continue

            old_a = graph.nodes[u]
            old_b = graph.nodes[v]
            if self._segments_intersect(
                (new_a.x, new_a.y),
                (new_b.x, new_b.y),
                (old_a.x, old_a.y),
                (old_b.x, old_b.y),
            ):
                return False

        return True

    @staticmethod
    def _segments_intersect(
        p1: Tuple[float, float],
        p2: Tuple[float, float],
        q1: Tuple[float, float],
        q2: Tuple[float, float],
    ) -> bool:
        """判断两线段是否相交。"""

        def orientation(a: Tuple[float, float], b: Tuple[float, float], c: Tuple[float, float]) -> float:
            return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])

        def on_segment(a: Tuple[float, float], b: Tuple[float, float], c: Tuple[float, float]) -> bool:
            return (
                min(a[0], b[0]) <= c[0] <= max(a[0], b[0])
                and min(a[1], b[1]) <= c[1] <= max(a[1], b[1])
            )

        o1 = orientation(p1, p2, q1)
        o2 = orientation(p1, p2, q2)
        o3 = orientation(q1, q2, p1)
        o4 = orientation(q1, q2, p2)

        # 一般相交
        if (o1 > 0 > o2 or o1 < 0 < o2) and (o3 > 0 > o4 or o3 < 0 < o4):
            return True

        # 共线特殊情况
        eps = 1e-9
        if abs(o1) < eps and on_segment(p1, p2, q1):
            return True
        if abs(o2) < eps and on_segment(p1, p2, q2):
            return True
        if abs(o3) < eps and on_segment(q1, q2, p1):
            return True
        if abs(o4) < eps and on_segment(q1, q2, p2):
            return True

        return False


if __name__ == "__main__":
    generator = MapGenerator(seed=42)
    graph = generator.generate_map()
    print(f"节点数: {graph.node_count()}")
    print(f"边数(含双向): {graph.edge_count()}")

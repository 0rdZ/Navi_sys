"""
map_generator.py
随机地图生成模块（优化版）。

优化点：
1. 使用距离缓存，避免重复计算节点间距离；
2. 为每个节点预生成最近邻候选列表，避免反复全量排序；
3. 使用顺序连通构造，降低生成连通图的时间开销；
4. 在线段相交检测前增加包围盒快速排除。
"""

from __future__ import annotations

import math
import random
from typing import Dict, List, Optional, Set, Tuple

from config import CONFIG
from models import Edge, Graph, Node


class MapGenerator:
    """地图生成器。"""

    def __init__(self, seed: Optional[int] = None) -> None:
        self.random = random.Random(seed)
        self._base_edge_id = 0

        # 距离缓存：(a, b) -> distance
        self._distance_cache: Dict[Tuple[int, int], float] = {}

        # 最近邻候选缓存：node_id -> [(other_id, distance), ...]
        self._neighbor_cache: Dict[int, List[Tuple[int, float]]] = {}

        # 每个节点保留的最近邻候选数量
        self._candidate_limit = max(12, CONFIG.MAP.MAX_NEIGHBORS * 3)

    def generate_map(self) -> Graph:
        """生成一个满足基本要求的随机连通地图。"""
        graph = Graph()

        nodes = self._generate_nodes(CONFIG.MAP.NODE_COUNT)
        for node in nodes:
            graph.add_node(node)

        self._prepare_distance_and_neighbor_cache(graph)

        # 第一步：先构造连通图骨架
        self._build_spanning_connections(graph)

        # 第二步：补充局部近邻连接
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

    def _prepare_distance_and_neighbor_cache(self, graph: Graph) -> None:
        """预计算距离缓存和每个节点的最近邻候选。"""
        node_ids = list(graph.nodes.keys())

        # 预计算距离
        for i in range(len(node_ids)):
            a = node_ids[i]
            for j in range(i + 1, len(node_ids)):
                b = node_ids[j]
                self._distance(graph, a, b)

        # 为每个节点构建最近邻候选列表
        for node_id in node_ids:
            candidates: List[Tuple[int, float]] = []
            for other_id in node_ids:
                if other_id == node_id:
                    continue
                candidates.append((other_id, self._distance(graph, node_id, other_id)))
            candidates.sort(key=lambda item: item[1])
            self._neighbor_cache[node_id] = candidates[: self._candidate_limit]

    def _distance(self, graph: Graph, a: int, b: int) -> float:
        """获取两节点间距离，带缓存。"""
        if a == b:
            return 0.0

        key = (a, b)
        if key in self._distance_cache:
            return self._distance_cache[key]

        na = graph.nodes[a]
        nb = graph.nodes[b]
        distance = math.hypot(na.x - nb.x, na.y - nb.y)

        self._distance_cache[(a, b)] = distance
        self._distance_cache[(b, a)] = distance
        return distance

    def _build_spanning_connections(self, graph: Graph) -> None:
        """
        构造连通图骨架。
        优化思路：
        - 不再每轮在 remaining × connected 上做全局扫描；
        - 对每个新节点，优先连接到“最近邻候选列表”中已连通的节点；
        - 如果候选中都没有，再退化为扫描 connected。
        """
        node_ids = list(graph.nodes.keys())
        if not node_ids:
            return

        first_node = node_ids[0]
        connected: Set[int] = {first_node}

        remaining = node_ids[1:]
        self.random.shuffle(remaining)

        for node_id in remaining:
            target_id = self._find_best_connected_neighbor(graph, node_id, connected)
            distance = self._distance(graph, node_id, target_id)

            if self._can_add_undirected_edge(graph, node_id, target_id):
                self._add_undirected_edge(graph, node_id, target_id, distance)
            else:
                # 候选中找替代节点
                alternative_added = False

                for alt_id, alt_distance in self._neighbor_cache.get(node_id, []):
                    if alt_id not in connected:
                        continue
                    if self._can_add_undirected_edge(graph, node_id, alt_id):
                        self._add_undirected_edge(graph, node_id, alt_id, alt_distance)
                        alternative_added = True
                        break

                if not alternative_added:
                    # 最后兜底：扫描所有已连通点
                    connected_sorted = sorted(
                        connected,
                        key=lambda cid: self._distance(graph, node_id, cid),
                    )
                    for alt_id in connected_sorted:
                        alt_distance = self._distance(graph, node_id, alt_id)
                        if self._can_add_undirected_edge(graph, node_id, alt_id):
                            self._add_undirected_edge(graph, node_id, alt_id, alt_distance)
                            alternative_added = True
                            break

                if not alternative_added:
                    # 极端情况下忽略相交检测，优先保证连通
                    self._add_undirected_edge(graph, node_id, target_id, distance)

            connected.add(node_id)

    def _find_best_connected_neighbor(self, graph: Graph, node_id: int, connected: Set[int]) -> int:
        """在已连通节点中寻找最适合连接的节点。"""
        for other_id, _ in self._neighbor_cache.get(node_id, []):
            if other_id in connected:
                return other_id

        # 若局部候选中没有，就退化扫描 connected
        best_id = None
        best_distance = float("inf")
        for other_id in connected:
            d = self._distance(graph, node_id, other_id)
            if d < best_distance:
                best_distance = d
                best_id = other_id

        if best_id is None:
            raise RuntimeError("无法为节点找到可连接的已连通节点。")

        return best_id

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

            for other_id, distance in self._neighbor_cache.get(node_id, []):
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
        规则：
        1. 不能自连；
        2. 不能重复连边；
        3. 不与已有道路发生不合理相交；
        4. 允许在共享端点处相交。
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
            key = tuple(sorted((u, v)))

            # 无向边只检查一次
            if key in checked_pairs:
                continue
            checked_pairs.add(key)

            # 共享端点，认为合理
            if len({a, b, u, v}) < 4:
                continue

            old_a = graph.nodes[u]
            old_b = graph.nodes[v]

            p1 = (new_a.x, new_a.y)
            p2 = (new_b.x, new_b.y)
            q1 = (old_a.x, old_a.y)
            q2 = (old_b.x, old_b.y)

            # 先做包围盒快速排除
            if not self._bbox_overlap(p1, p2, q1, q2):
                continue

            if self._segments_intersect(p1, p2, q1, q2):
                return False

        return True

    @staticmethod
    def _bbox_overlap(
        p1: Tuple[float, float],
        p2: Tuple[float, float],
        q1: Tuple[float, float],
        q2: Tuple[float, float],
    ) -> bool:
        """判断两线段的外接矩形是否重叠。"""
        return not (
            max(p1[0], p2[0]) < min(q1[0], q2[0])
            or max(q1[0], q2[0]) < min(p1[0], p2[0])
            or max(p1[1], p2[1]) < min(q1[1], q2[1])
            or max(q1[1], q2[1]) < min(p1[1], p2[1])
        )

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

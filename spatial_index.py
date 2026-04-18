"""
spatial_index.py
空间检索模块。

作用：
1. 根据输入坐标快速查找最近的若干节点；
2. 查询指定矩形视野范围内的节点和边；
3. 为地图显示、局部显示、最近100个点查询提供基础支持。

当前实现采用“网格索引 + 直接距离筛选”的方式，
兼顾实现难度、可维护性与课程设计可运行性。
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Set, Tuple

from config import CONFIG
from models import Edge, Graph, Node


@dataclass(frozen=True)
class Rect:
    """矩形视野区域。"""

    min_x: float
    min_y: float
    max_x: float
    max_y: float

    def contains_point(self, x: float, y: float) -> bool:
        return self.min_x <= x <= self.max_x and self.min_y <= y <= self.max_y

    def intersects_segment(
        self,
        x1: float,
        y1: float,
        x2: float,
        y2: float,
    ) -> bool:
        """
        判断线段是否与矩形相交。
        先做包围盒判断，再做端点包含和边相交判断。
        """
        if max(x1, x2) < self.min_x or min(x1, x2) > self.max_x:
            return False
        if max(y1, y2) < self.min_y or min(y1, y2) > self.max_y:
            return False

        if self.contains_point(x1, y1) or self.contains_point(x2, y2):
            return True

        corners = [
            (self.min_x, self.min_y),
            (self.max_x, self.min_y),
            (self.max_x, self.max_y),
            (self.min_x, self.max_y),
        ]
        rect_edges = [
            (corners[0], corners[1]),
            (corners[1], corners[2]),
            (corners[2], corners[3]),
            (corners[3], corners[0]),
        ]

        for (ax, ay), (bx, by) in rect_edges:
            if SpatialIndex.segments_intersect((x1, y1), (x2, y2), (ax, ay), (bx, by)):
                return True

        return False


class SpatialIndex:
    """基于均匀网格的空间索引。"""

    def __init__(self, graph: Graph, cell_size: Optional[float] = None) -> None:
        self.graph = graph
        self.cell_size = cell_size or CONFIG.MAP.REPRESENTATIVE_GRID_SIZE

        # 网格索引：cell -> [node_id, ...]
        self.grid: Dict[Tuple[int, int], List[int]] = {}
        self._build_index()

    def _build_index(self) -> None:
        """构建节点网格索引。"""
        self.grid.clear()
        for node in self.graph.nodes.values():
            cell = self._cell_of(node.x, node.y)
            self.grid.setdefault(cell, []).append(node.node_id)

    def rebuild(self) -> None:
        """重建空间索引。"""
        self._build_index()

    def nearest_nodes(self, x: float, y: float, k: int = 100) -> List[Tuple[Node, float]]:
        """
        查找距离指定坐标最近的 k 个节点。

        返回：[(Node, distance), ...]
        """
        if not self.graph.nodes:
            return []

        center_cell = self._cell_of(x, y)
        candidate_ids: Set[int] = set()
        radius = 0

        # 逐层扩展搜索网格，直到候选数足够
        while len(candidate_ids) < k:
            cells = self._cells_in_radius(center_cell, radius)
            for cell in cells:
                for node_id in self.grid.get(cell, []):
                    candidate_ids.add(node_id)

            # 所有节点都已纳入候选时停止
            if len(candidate_ids) >= len(self.graph.nodes):
                break
            radius += 1

        result: List[Tuple[Node, float]] = []
        for node_id in candidate_ids:
            node = self.graph.nodes[node_id]
            distance = math.hypot(node.x - x, node.y - y)
            result.append((node, distance))

        result.sort(key=lambda item: item[1])
        return result[:k]

    def nodes_in_rect(self, rect: Rect) -> List[Node]:
        """查询视野矩形内的所有节点。"""
        cells = self._cells_for_rect(rect)
        result: List[Node] = []
        seen: Set[int] = set()

        for cell in cells:
            for node_id in self.grid.get(cell, []):
                if node_id in seen:
                    continue
                seen.add(node_id)
                node = self.graph.nodes[node_id]
                if rect.contains_point(node.x, node.y):
                    result.append(node)

        return result

    def edges_in_rect(self, rect: Rect) -> List[Edge]:
        """
        查询视野矩形内相关的边。
        规则：只要边的任意端点在矩形中，或边与矩形相交，就认为应显示。
        """
        result: List[Edge] = []
        checked_undirected: Set[Tuple[int, int]] = set()

        for edge in self.graph.edges.values():
            key = tuple(sorted((edge.start, edge.end)))
            if key in checked_undirected:
                continue
            checked_undirected.add(key)

            start_node = self.graph.nodes[edge.start]
            end_node = self.graph.nodes[edge.end]

            if rect.intersects_segment(start_node.x, start_node.y, end_node.x, end_node.y):
                result.append(edge)

        return result

    def representative_nodes_in_rect(self, rect: Rect, unit_size: Optional[float] = None) -> List[Node]:
        """
        缩小时用于稀疏显示：每个单元格只显示一个代表点。
        对应题目 F2 的缩放显示需求。
        """
        unit = unit_size or CONFIG.MAP.REPRESENTATIVE_GRID_SIZE
        nodes = self.nodes_in_rect(rect)

        buckets: Dict[Tuple[int, int], Node] = {}
        for node in nodes:
            key = (int((node.x - rect.min_x) // unit), int((node.y - rect.min_y) // unit))
            if key not in buckets:
                buckets[key] = node

        return list(buckets.values())

    def nearest_subgraph(self, x: float, y: float, k: int = 100) -> Tuple[List[Node], List[Edge]]:
        """
        查找最近的 k 个节点及其关联边。
        用于题目 F1：输入一个坐标，显示最近100个顶点及相关边。
        """
        nearest = self.nearest_nodes(x, y, k)
        nodes = [node for node, _ in nearest]
        node_ids = {node.node_id for node in nodes}

        edges: List[Edge] = []
        checked_undirected: Set[Tuple[int, int]] = set()
        for edge in self.graph.edges.values():
            key = tuple(sorted((edge.start, edge.end)))
            if key in checked_undirected:
                continue
            checked_undirected.add(key)

            if edge.start in node_ids and edge.end in node_ids:
                edges.append(edge)

        return nodes, edges

    def _cell_of(self, x: float, y: float) -> Tuple[int, int]:
        """计算点所属网格坐标。"""
        return int(x // self.cell_size), int(y // self.cell_size)

    def _cells_in_radius(self, center: Tuple[int, int], radius: int) -> Iterable[Tuple[int, int]]:
        """返回以中心网格为核心、指定半径的所有网格坐标。"""
        cx, cy = center
        for gx in range(cx - radius, cx + radius + 1):
            for gy in range(cy - radius, cy + radius + 1):
                yield gx, gy

    def _cells_for_rect(self, rect: Rect) -> Iterable[Tuple[int, int]]:
        """返回矩形覆盖到的所有网格。"""
        min_cell = self._cell_of(rect.min_x, rect.min_y)
        max_cell = self._cell_of(rect.max_x, rect.max_y)

        for gx in range(min_cell[0], max_cell[0] + 1):
            for gy in range(min_cell[1], max_cell[1] + 1):
                yield gx, gy

    @staticmethod
    def segments_intersect(
        p1: Tuple[float, float],
        p2: Tuple[float, float],
        q1: Tuple[float, float],
        q2: Tuple[float, float],
    ) -> bool:
        """判断两条线段是否相交。"""

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

        if (o1 > 0 > o2 or o1 < 0 < o2) and (o3 > 0 > o4 or o3 < 0 < o4):
            return True

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
    from map_generator import MapGenerator

    generator = MapGenerator(seed=42)
    graph = generator.generate_map()
    index = SpatialIndex(graph)

    x, y = 2500.0, 2500.0
    nearest = index.nearest_nodes(x, y, k=5)
    print("最近5个节点：")
    for node, dist in nearest:
        print(f"node={node.node_id}, pos=({node.x:.1f}, {node.y:.1f}), dist={dist:.2f}")

    rect = Rect(1500, 1500, 3000, 3000)
    nodes = index.nodes_in_rect(rect)
    edges = index.edges_in_rect(rect)
    print(f"矩形范围内节点数: {len(nodes)}")
    print(f"矩形范围内边数: {len(edges)}")

"""
models.py
项目核心数据结构定义。

作用：
1. 定义地图中的节点、边、车辆、图结构；
2. 为地图生成、路径搜索、交通仿真提供统一的数据模型；
3. 保证各模块之间的数据接口清晰一致。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
import math

from config import CONFIG


@dataclass
class Node:
    """地图中的地点节点。"""

    node_id: int
    x: float
    y: float
    name: str = ""

    def position(self) -> Tuple[float, float]:
        """返回节点坐标。"""
        return self.x, self.y

    def distance_to(self, other: "Node") -> float:
        """计算当前节点到另一个节点的欧氏距离。"""
        return math.hypot(self.x - other.x, self.y - other.y)


@dataclass
class Edge:
    """地图中的道路边。默认视为双向道路的一条连接关系。"""

    edge_id: int
    start: int
    end: int
    length: float
    capacity: int
    current_vehicles: int = 0

    def is_overloaded(self) -> bool:
        """判断当前道路是否超载。"""
        return self.current_vehicles > self.capacity

    def load_ratio(self) -> float:
        """返回当前负载率。"""
        if self.capacity <= 0:
            return 0.0
        return self.current_vehicles / self.capacity

    def travel_time(self) -> float:
        """
        根据题目要求计算当前道路通行时间。

        当 x <= c 时：f(x)=1
        当 x > c 时：f(x)=1 + OVERLOAD_PENALTY_FACTOR * (x-c)/c
        最终：t = length * f(x) / K
        """
        x = self.current_vehicles
        c = self.capacity
        if c <= 0:
            return float("inf")

        if x <= c:
            factor = 1.0
        else:
            factor = 1.0 + CONFIG.TRAFFIC.OVERLOAD_PENALTY_FACTOR * (x - c) / c

        return self.length * factor / CONFIG.TRAFFIC.TIME_CONSTANT_K


@dataclass
class Vehicle:
    """交通仿真中的车辆对象。"""

    vehicle_id: int
    start_node: int
    target_node: int
    path: List[int] = field(default_factory=list)
    current_path_index: int = 0
    progress_on_edge: float = 0.0
    finished: bool = False

    def current_node(self) -> Optional[int]:
        """返回车辆当前所在路径节点。"""
        if not self.path:
            return None
        if self.current_path_index >= len(self.path):
            return self.path[-1]
        return self.path[self.current_path_index]

    def next_node(self) -> Optional[int]:
        """返回车辆下一目标节点。"""
        if not self.path:
            return None
        next_index = self.current_path_index + 1
        if next_index >= len(self.path):
            return None
        return self.path[next_index]


@dataclass
class Graph:
    """地图图结构，使用邻接表存储。"""

    nodes: Dict[int, Node] = field(default_factory=dict)
    edges: Dict[int, Edge] = field(default_factory=dict)
    adjacency: Dict[int, List[int]] = field(default_factory=dict)
    edge_lookup: Dict[Tuple[int, int], int] = field(default_factory=dict)

    def add_node(self, node: Node) -> None:
        """添加节点。"""
        self.nodes[node.node_id] = node
        if node.node_id not in self.adjacency:
            self.adjacency[node.node_id] = []

    def add_edge(self, edge: Edge, bidirectional: bool = True) -> None:
        """
        添加边。

        参数：
            edge: 原始边对象
            bidirectional: 是否自动建立双向连接
        """
        self.edges[edge.edge_id] = edge

        if edge.start not in self.adjacency:
            self.adjacency[edge.start] = []
        self.adjacency[edge.start].append(edge.edge_id)
        self.edge_lookup[(edge.start, edge.end)] = edge.edge_id

        if bidirectional:
            reverse_edge_id = self._next_edge_id()
            reverse_edge = Edge(
                edge_id=reverse_edge_id,
                start=edge.end,
                end=edge.start,
                length=edge.length,
                capacity=edge.capacity,
                current_vehicles=edge.current_vehicles,
            )
            self.edges[reverse_edge.edge_id] = reverse_edge

            if reverse_edge.start not in self.adjacency:
                self.adjacency[reverse_edge.start] = []
            self.adjacency[reverse_edge.start].append(reverse_edge.edge_id)
            self.edge_lookup[(reverse_edge.start, reverse_edge.end)] = reverse_edge.edge_id

    def _next_edge_id(self) -> int:
        """生成下一个可用边编号。"""
        if not self.edges:
            return 0
        return max(self.edges.keys()) + 1

    def get_node(self, node_id: int) -> Optional[Node]:
        """获取节点对象。"""
        return self.nodes.get(node_id)

    def get_edge(self, edge_id: int) -> Optional[Edge]:
        """获取边对象。"""
        return self.edges.get(edge_id)

    def get_edge_by_nodes(self, start: int, end: int) -> Optional[Edge]:
        """根据起点和终点查找边对象。"""
        edge_id = self.edge_lookup.get((start, end))
        if edge_id is None:
            return None
        return self.edges.get(edge_id)

    def neighbors(self, node_id: int) -> List[int]:
        """返回某节点可到达的邻居节点列表。"""
        result: List[int] = []
        for edge_id in self.adjacency.get(node_id, []):
            edge = self.edges[edge_id]
            result.append(edge.end)
        return result

    def outgoing_edges(self, node_id: int) -> List[Edge]:
        """返回某节点的所有出边。"""
        return [self.edges[edge_id] for edge_id in self.adjacency.get(node_id, [])]

    def node_count(self) -> int:
        """返回节点数量。"""
        return len(self.nodes)

    def edge_count(self) -> int:
        """返回边数量。"""
        return len(self.edges)

    def has_node(self, node_id: int) -> bool:
        """判断节点是否存在。"""
        return node_id in self.nodes

    def clear(self) -> None:
        """清空图数据。"""
        self.nodes.clear()
        self.edges.clear()
        self.adjacency.clear()
        self.edge_lookup.clear()

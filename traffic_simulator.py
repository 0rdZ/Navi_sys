"""
traffic_simulator.py
交通仿真主模块。

作用：
1. 在地图上生成车辆并分配起点、终点；
2. 为车辆计算路径并沿道路推进；
3. 动态维护每条道路上的车辆数；
4. 为界面层提供当前车辆、道路交通状态等数据。
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from config import CONFIG
from graph_algorithms import GraphAlgorithms, PathNotFoundError
from models import Edge, Graph, Vehicle
from traffic_model import TrafficModel


@dataclass
class SimulationStats:
    """仿真统计信息。"""

    current_time: float = 0.0
    total_spawned: int = 0
    total_finished: int = 0
    active_vehicles: int = 0


@dataclass
class VehicleRuntime:
    """车辆运行时状态。"""

    vehicle: Vehicle
    current_edge_start: Optional[int] = None
    current_edge_end: Optional[int] = None
    remaining_time_on_edge: float = 0.0


class TrafficSimulator:
    """交通仿真器。"""

    def __init__(self, graph: Graph, seed: Optional[int] = None) -> None:
        self.graph = graph
        self.random = random.Random(seed)

        self.vehicles: Dict[int, VehicleRuntime] = {}
        self.stats = SimulationStats()
        self._next_vehicle_id = 0
        self._running = False

    def start(self) -> None:
        """开始仿真。"""
        self._running = True

    def stop(self) -> None:
        """停止仿真。"""
        self._running = False

    def reset(self) -> None:
        """重置仿真状态。"""
        self.stop()
        self._clear_edge_vehicles()
        self.vehicles.clear()
        self.stats = SimulationStats()
        self._next_vehicle_id = 0

    def is_running(self) -> bool:
        """返回仿真是否正在运行。"""
        return self._running

    def step(self) -> None:
        """推进一个仿真时间步。"""
        if not self._running:
            return

        self._spawn_vehicles()
        self._advance_vehicles(CONFIG.TRAFFIC.TIME_STEP)
        self.stats.current_time += CONFIG.TRAFFIC.TIME_STEP
        self.stats.active_vehicles = self.active_vehicle_count()

    def active_vehicle_count(self) -> int:
        """返回当前活跃车辆数。"""
        return len(self.vehicles)

    def all_vehicle_runtimes(self) -> List[VehicleRuntime]:
        """返回所有车辆运行时对象。"""
        return list(self.vehicles.values())

    def all_edges(self) -> List[Edge]:
        """返回图中所有边。"""
        return list(self.graph.edges.values())

    def spawn_vehicle(self, start_node: int, target_node: int) -> Optional[VehicleRuntime]:
        """
        手动生成一辆车并加入仿真。
        若路径不存在则返回 None。
        """
        if start_node == target_node:
            return None
        if not self.graph.has_node(start_node) or not self.graph.has_node(target_node):
            return None
        if self.active_vehicle_count() >= CONFIG.TRAFFIC.MAX_ACTIVE_VEHICLES:
            return None

        try:
            path, _ = GraphAlgorithms.shortest_path_by_time(self.graph, start_node, target_node)
        except PathNotFoundError:
            return None

        vehicle = Vehicle(
            vehicle_id=self._next_vehicle_id,
            start_node=start_node,
            target_node=target_node,
            path=path,
            current_path_index=0,
            progress_on_edge=0.0,
            finished=False,
        )
        self._next_vehicle_id += 1

        runtime = VehicleRuntime(vehicle=vehicle)
        self._enter_next_edge(runtime)
        self.vehicles[vehicle.vehicle_id] = runtime

        self.stats.total_spawned += 1
        self.stats.active_vehicles = self.active_vehicle_count()
        return runtime

    def _spawn_vehicles(self) -> None:
        """按配置自动生成若干车辆。"""
        spawn_count = CONFIG.TRAFFIC.VEHICLE_SPAWN_PER_STEP
        node_ids = list(self.graph.nodes.keys())
        if len(node_ids) < 2:
            return

        for _ in range(spawn_count):
            if self.active_vehicle_count() >= CONFIG.TRAFFIC.MAX_ACTIVE_VEHICLES:
                break

            start_node = self.random.choice(node_ids)
            target_node = self.random.choice(node_ids)
            while target_node == start_node:
                target_node = self.random.choice(node_ids)

            self.spawn_vehicle(start_node, target_node)

    def _advance_vehicles(self, delta_time: float) -> None:
        """推进所有车辆。"""
        finished_vehicle_ids: List[int] = []

        for vehicle_id, runtime in list(self.vehicles.items()):
            remaining = delta_time

            while remaining > 0 and not runtime.vehicle.finished:
                if runtime.current_edge_start is None or runtime.current_edge_end is None:
                    runtime.vehicle.finished = True
                    break

                if runtime.remaining_time_on_edge > remaining:
                    runtime.remaining_time_on_edge -= remaining
                    remaining = 0
                else:
                    remaining -= runtime.remaining_time_on_edge
                    self._leave_current_edge(runtime)

                    runtime.vehicle.current_path_index += 1
                    if runtime.vehicle.current_path_index >= len(runtime.vehicle.path) - 1:
                        runtime.vehicle.finished = True
                        break

                    self._enter_next_edge(runtime)

            if runtime.vehicle.finished:
                finished_vehicle_ids.append(vehicle_id)

        for vehicle_id in finished_vehicle_ids:
            self.vehicles.pop(vehicle_id, None)
            self.stats.total_finished += 1

    def _enter_next_edge(self, runtime: VehicleRuntime) -> None:
        """让车辆进入路径中的下一条边。"""
        vehicle = runtime.vehicle
        current_index = vehicle.current_path_index

        if current_index >= len(vehicle.path) - 1:
            vehicle.finished = True
            runtime.current_edge_start = None
            runtime.current_edge_end = None
            runtime.remaining_time_on_edge = 0.0
            return

        start_node = vehicle.path[current_index]
        end_node = vehicle.path[current_index + 1]
        edge = self.graph.get_edge_by_nodes(start_node, end_node)

        if edge is None:
            vehicle.finished = True
            runtime.current_edge_start = None
            runtime.current_edge_end = None
            runtime.remaining_time_on_edge = 0.0
            return

        edge.current_vehicles += 1
        runtime.current_edge_start = start_node
        runtime.current_edge_end = end_node
        runtime.remaining_time_on_edge = TrafficModel.travel_time(edge)

    def _leave_current_edge(self, runtime: VehicleRuntime) -> None:
        """让车辆离开当前道路。"""
        if runtime.current_edge_start is None or runtime.current_edge_end is None:
            return

        edge = self.graph.get_edge_by_nodes(runtime.current_edge_start, runtime.current_edge_end)
        if edge is not None and edge.current_vehicles > 0:
            edge.current_vehicles -= 1

        runtime.current_edge_start = None
        runtime.current_edge_end = None
        runtime.remaining_time_on_edge = 0.0

    def _clear_edge_vehicles(self) -> None:
        """清空所有道路上的车辆计数。"""
        for edge in self.graph.edges.values():
            edge.current_vehicles = 0

    def edge_state_summary(self) -> List[dict]:
        """返回所有道路的简要交通状态，便于界面层读取。"""
        result: List[dict] = []
        for edge in self.graph.edges.values():
            result.append(
                {
                    "edge_id": edge.edge_id,
                    "start": edge.start,
                    "end": edge.end,
                    "length": edge.length,
                    "capacity": edge.capacity,
                    "current_vehicles": edge.current_vehicles,
                    "travel_time": TrafficModel.travel_time(edge),
                    "load_ratio": TrafficModel.load_ratio(edge),
                    "traffic_level": TrafficModel.classify_traffic(edge).value,
                }
            )
        return result


if __name__ == "__main__":
    from map_generator import MapGenerator

    generator = MapGenerator(seed=42)
    graph = generator.generate_map()

    simulator = TrafficSimulator(graph, seed=42)
    simulator.start()

    for step_index in range(10):
        simulator.step()
        print(
            f"step={step_index + 1}, "
            f"time={simulator.stats.current_time:.1f}, "
            f"spawned={simulator.stats.total_spawned}, "
            f"finished={simulator.stats.total_finished}, "
            f"active={simulator.stats.active_vehicles}"
        )

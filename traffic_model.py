"""
traffic_model.py
交通模型模块。

作用：
1. 统一管理道路拥堵状态、通行时间、负载率等交通规则；
2. 为最短时间路径、交通仿真、地图着色显示提供基础计算；
3. 避免将交通公式分散在多个文件中，便于维护和调参。
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from config import CONFIG
from models import Edge


class TrafficLevel(str, Enum):
    """道路交通状态等级。"""

    SMOOTH = "smooth"      # 畅通
    BUSY = "busy"          # 繁忙
    CONGESTED = "congested"  # 拥堵


@dataclass(frozen=True)
class TrafficState:
    """某条道路在当前时刻的交通状态。"""

    load_ratio: float
    travel_time: float
    traffic_level: TrafficLevel
    overloaded: bool


class TrafficModel:
    """交通模型工具类。"""

    @staticmethod
    def load_ratio(edge: Edge) -> float:
        """计算道路负载率 x / c。"""
        if edge.capacity <= 0:
            return 0.0
        return edge.current_vehicles / edge.capacity

    @staticmethod
    def congestion_factor(edge: Edge) -> float:
        """
        计算拥堵修正系数 f(x)。

        当 x <= c 时：f(x) = 1
        当 x > c 时：f(x) = 1 + penalty * (x - c) / c
        """
        x = edge.current_vehicles
        c = edge.capacity

        if c <= 0:
            return float("inf")
        if x <= c:
            return 1.0

        return 1.0 + CONFIG.TRAFFIC.OVERLOAD_PENALTY_FACTOR * (x - c) / c

    @staticmethod
    def travel_time(edge: Edge) -> float:
        """
        根据题目中的交通公式计算通行时间。

        t = length * f(x) / K
        """
        if edge.capacity <= 0:
            return float("inf")

        factor = TrafficModel.congestion_factor(edge)
        if factor == float("inf"):
            return float("inf")

        return edge.length * factor / CONFIG.TRAFFIC.TIME_CONSTANT_K

    @staticmethod
    def classify_traffic(edge: Edge) -> TrafficLevel:
        """
        根据负载率划分交通等级。

        这里采用便于可视化的分段：
        - load_ratio < 0.6    -> 畅通
        - 0.6 <= load_ratio <= 1.0 -> 繁忙
        - load_ratio > 1.0    -> 拥堵
        """
        ratio = TrafficModel.load_ratio(edge)
        if ratio < 0.6:
            return TrafficLevel.SMOOTH
        if ratio <= 1.0:
            return TrafficLevel.BUSY
        return TrafficLevel.CONGESTED

    @staticmethod
    def is_overloaded(edge: Edge) -> bool:
        """判断道路是否超载。"""
        return edge.current_vehicles > edge.capacity

    @staticmethod
    def build_state(edge: Edge) -> TrafficState:
        """构建道路当前完整交通状态。"""
        return TrafficState(
            load_ratio=TrafficModel.load_ratio(edge),
            travel_time=TrafficModel.travel_time(edge),
            traffic_level=TrafficModel.classify_traffic(edge),
            overloaded=TrafficModel.is_overloaded(edge),
        )

    @staticmethod
    def traffic_color_name(edge: Edge) -> str:
        """
        返回交通状态对应的配置颜色名。
        供界面层按需映射使用。
        """
        level = TrafficModel.classify_traffic(edge)
        if level == TrafficLevel.SMOOTH:
            return CONFIG.STYLE.COLOR_TRAFFIC_SMOOTH
        if level == TrafficLevel.BUSY:
            return CONFIG.STYLE.COLOR_TRAFFIC_BUSY
        return CONFIG.STYLE.COLOR_TRAFFIC_CONGESTED


if __name__ == "__main__":
    from models import Edge

    edge = Edge(
        edge_id=0,
        start=1,
        end=2,
        length=200.0,
        capacity=50,
        current_vehicles=30,
    )

    state = TrafficModel.build_state(edge)
    print("负载率:", round(state.load_ratio, 2))
    print("通行时间:", round(state.travel_time, 2))
    print("交通等级:", state.traffic_level.value)
    print("是否超载:", state.overloaded)

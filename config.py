"""
config.py
项目全局配置文件。

作用：
1. 统一管理地图生成、交通仿真、界面显示相关参数；
2. 避免魔法数字散落在各个模块中；
3. 便于后期调参、测试与维护。
"""

from dataclasses import dataclass

@dataclass(frozen=True)
class WindowConfig:
    """主窗口与绘图区配置"""

    WINDOW_WIDTH: int = 1400
    WINDOW_HEIGHT: int = 900
    MAP_VIEW_WIDTH: int = 1000
    MAP_VIEW_HEIGHT: int = 800
    WINDOW_TITLE: str = "Navigation System"


@dataclass(frozen=True)
class MapConfig:
    """地图生成与显示配置"""

    # 地图节点数量
    NODE_COUNT: int = 120

    # 二维平面坐标范围
    MAP_MIN_X: float = 0.0
    MAP_MAX_X: float = 5000.0
    MAP_MIN_Y: float = 0.0
    MAP_MAX_Y: float = 5000.0

    # 每个节点尝试连接的邻居数量范围
    MIN_NEIGHBORS: int = 2
    MAX_NEIGHBORS: int = 5

    # 地图显示相关
    NEAREST_DISPLAY_COUNT: int = 100
    INITIAL_ZOOM: float = 1.0
    MIN_ZOOM: float = 0.2
    MAX_ZOOM: float = 5.0
    ZOOM_STEP: float = 1.2

    # 缩小时用于去重显示的网格大小
    REPRESENTATIVE_GRID_SIZE: float = 120.0


@dataclass(frozen=True)
class TrafficConfig:
    """交通仿真配置"""

    # 刷新周期（毫秒）
    TIMER_INTERVAL_MS: int = 100

    # 仿真时间步长（秒）
    TIME_STEP: float = 1.0

    # 车辆生成参数
    VEHICLE_SPAWN_PER_STEP: int = 3
    MAX_ACTIVE_VEHICLES: int = 300

    # 道路容量范围
    MIN_EDGE_CAPACITY: int = 20
    MAX_EDGE_CAPACITY: int = 100

    # 时间计算常数 t = length * f(x) / K
    TIME_CONSTANT_K: float = 40.0

    # 拥堵惩罚系数（当 x > c 时生效）
    OVERLOAD_PENALTY_FACTOR: float = 2.0


@dataclass(frozen=True)
class StyleConfig:
    """界面绘制样式配置"""

    NODE_RADIUS: int = 4
    HIGHLIGHT_NODE_RADIUS: int = 6
    EDGE_WIDTH: int = 2
    PATH_EDGE_WIDTH: int = 4

    COLOR_BACKGROUND: str = "#F5F7FA"
    COLOR_NODE: str = "#2C3E50"
    COLOR_EDGE: str = "#95A5A6"
    COLOR_PATH: str = "#E67E22"
    COLOR_TEXT: str = "#1F2D3D"

    # 交通状态颜色
    COLOR_TRAFFIC_SMOOTH: str = "#2ECC71"
    COLOR_TRAFFIC_BUSY: str = "#F1C40F"
    COLOR_TRAFFIC_CONGESTED: str = "#E74C3C"


@dataclass(frozen=True)
class FileConfig:
    """数据文件路径配置"""

    MAP_DATA_FILE: str = "data/map_data.json"
    TRAFFIC_DATA_FILE: str = "data/traffic_data.json"
    LOG_FILE: str = "logs/system.log"


class Config:
    """总配置入口，便于统一引用。"""

    WINDOW = WindowConfig()
    MAP = MapConfig()
    TRAFFIC = TrafficConfig()
    STYLE = StyleConfig()
    FILE = FileConfig()


# 统一导出实例，其他模块可直接使用：from config import CONFIG
CONFIG = Config()

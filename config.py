"""
config.py
项目全局配置文件。
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class WindowConfig:
    """主窗口与绘图区配置"""

    WINDOW_WIDTH: int = 1200
    WINDOW_HEIGHT: int = 760
    MAP_VIEW_WIDTH: int = 700
    MAP_VIEW_HEIGHT: int = 560
    WINDOW_TITLE: str = "Navigation System"


@dataclass(frozen=True)
class MapConfig:
    """地图生成与显示配置"""

    NODE_COUNT: int = 500

    MAP_MIN_X: float = 0.0
    MAP_MAX_X: float = 5000.0
    MAP_MIN_Y: float = 0.0
    MAP_MAX_Y: float = 5000.0

    MIN_NEIGHBORS: int = 2
    MAX_NEIGHBORS: int = 5

    NEAREST_DISPLAY_COUNT: int = 100
    INITIAL_ZOOM: float = 1.0
    MIN_ZOOM: float = 0.05
    MAX_ZOOM: float = 5.0
    ZOOM_STEP: float = 1.2

    REPRESENTATIVE_GRID_SIZE: float = 120.0


@dataclass(frozen=True)
class TrafficConfig:
    """交通仿真配置"""

    TIMER_INTERVAL_MS: int = 100
    TIME_STEP: float = 1.0

    # 强演示模式：更容易形成明显拥堵
    VEHICLE_SPAWN_PER_STEP: int = 18
    MAX_ACTIVE_VEHICLES: int = 1200

    MIN_EDGE_CAPACITY: int = 4
    MAX_EDGE_CAPACITY: int = 12

    TIME_CONSTANT_K: float = 35.0
    OVERLOAD_PENALTY_FACTOR: float = 7.0


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


CONFIG = Config()

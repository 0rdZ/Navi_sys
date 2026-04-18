"""
map_view.py
地图绘制组件。
"""

from __future__ import annotations

from typing import List, Optional, Set, Tuple

from PyQt5.QtCore import QPoint, QPointF, Qt, pyqtSignal
from PyQt5.QtGui import QColor, QMouseEvent, QPainter, QPen, QBrush
from PyQt5.QtWidgets import QWidget

from config import CONFIG
from models import Edge, Graph, Node
from spatial_index import Rect, SpatialIndex
from traffic_model import TrafficModel


class MapView(QWidget):
    """地图绘制区域。"""

    nodeClicked = pyqtSignal(int)
    coordinateClicked = pyqtSignal(float, float)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        self.graph: Optional[Graph] = None
        self.spatial_index: Optional[SpatialIndex] = None

        self.zoom = CONFIG.MAP.INITIAL_ZOOM
        self.offset_x = 0.0
        self.offset_y = 0.0

        self.show_representative_only = False
        self.focus_mode = "rect"  # "rect" 或 "nearest"
        self.focus_point: Optional[Tuple[float, float]] = None
        self.focus_nearest_count = CONFIG.MAP.NEAREST_DISPLAY_COUNT

        self.highlight_path_nodes: List[int] = []
        self.highlight_edge_keys: Set[Tuple[int, int]] = set()

        self.selected_node_ids: List[int] = []

        self._last_mouse_pos: Optional[QPoint] = None
        self._dragging = False

        self.setMinimumSize(520, 420)
        self.setMouseTracking(True)

    def set_graph(self, graph: Graph) -> None:
        """设置当前显示的图。"""
        self.graph = graph
        self.spatial_index = SpatialIndex(graph)
        self.clear_path_highlight()
        self.selected_node_ids.clear()
        self.fit_to_view()
        self.update()

    def fit_to_view(self) -> None:
        """让整张地图自动适应当前窗口并居中显示。"""
        if self.graph is None or not self.graph.nodes:
            self.zoom = CONFIG.MAP.INITIAL_ZOOM
            self.offset_x = 0.0
            self.offset_y = 0.0
            return

        xs = [node.x for node in self.graph.nodes.values()]
        ys = [node.y for node in self.graph.nodes.values()]

        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)

        map_width = max(max_x - min_x, 1.0)
        map_height = max(max_y - min_y, 1.0)

        view_width = max(self.width() - 40, 1)
        view_height = max(self.height() - 40, 1)

        scale_x = view_width / map_width
        scale_y = view_height / map_height

        self.zoom = min(scale_x, scale_y)
        self.zoom = max(CONFIG.MAP.MIN_ZOOM, min(self.zoom, CONFIG.MAP.MAX_ZOOM))

        scaled_width = map_width * self.zoom
        scaled_height = map_height * self.zoom

        self.offset_x = (self.width() - scaled_width) / 2 - min_x * self.zoom
        self.offset_y = (self.height() - scaled_height) / 2 - min_y * self.zoom

    def reset_view(self) -> None:
        """重置缩放与平移，并让整张地图适应窗口。"""
        self.focus_point = None
        self.focus_mode = "rect"
        if self.graph is not None:
            self.fit_to_view()
        else:
            self.zoom = CONFIG.MAP.INITIAL_ZOOM
            self.offset_x = 0.0
            self.offset_y = 0.0
        self.update()

    def zoom_in(self) -> None:
        """放大地图。"""
        self.zoom = min(self.zoom * CONFIG.MAP.ZOOM_STEP, CONFIG.MAP.MAX_ZOOM)
        self.update()

    def zoom_out(self) -> None:
        """缩小地图。"""
        self.zoom = max(self.zoom / CONFIG.MAP.ZOOM_STEP, CONFIG.MAP.MIN_ZOOM)
        self.update()

    def set_focus_point(self, x: float, y: float, nearest_mode: bool = True) -> None:
        """设置关注点，可用于显示最近100个点。"""
        self.focus_point = (x, y)
        self.focus_mode = "nearest" if nearest_mode else "rect"
        self.update()

    def set_show_representative_only(self, enabled: bool) -> None:
        """设置是否只显示代表点。"""
        self.show_representative_only = enabled
        self.update()

    def set_nearest_display_count(self, count: int) -> None:
        """设置最近点显示数量。"""
        self.focus_nearest_count = max(1, count)
        self.update()

    def highlight_path(self, path: List[int]) -> None:
        """高亮显示路径。"""
        self.highlight_path_nodes = path[:]
        self.highlight_edge_keys.clear()

        if self.graph and len(path) >= 2:
            for i in range(len(path) - 1):
                key = tuple(sorted((path[i], path[i + 1])))
                self.highlight_edge_keys.add(key)

        self.update()

    def clear_path_highlight(self) -> None:
        """清除路径高亮。"""
        self.highlight_path_nodes.clear()
        self.highlight_edge_keys.clear()
        self.update()

    def selected_nodes(self) -> List[int]:
        """返回当前选中的节点。"""
        return self.selected_node_ids[:]

    def clear_selected_nodes(self) -> None:
        """清空已选节点。"""
        self.selected_node_ids.clear()
        self.update()

    def resizeEvent(self, event) -> None:
        """窗口尺寸变化时，保持整图适应显示。"""
        super().resizeEvent(event)
        if self.graph is not None and not self._dragging and self.focus_mode == "rect":
            self.fit_to_view()

    def paintEvent(self, event) -> None:
        """绘制地图。"""
        super().paintEvent(event)

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.fillRect(self.rect(), QColor(CONFIG.STYLE.COLOR_BACKGROUND))

        if self.graph is None or self.spatial_index is None:
            return

        visible_nodes, visible_edges = self._get_visible_subgraph()

        self._draw_edges(painter, visible_edges)
        self._draw_nodes(painter, visible_nodes)
        self._draw_selected_nodes(painter)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """左键点节点选中，否则拖动；右键/中键也可拖动。"""
        if event.button() == Qt.LeftButton:
            map_x, map_y = self._screen_to_map(event.pos().x(), event.pos().y())
            self.coordinateClicked.emit(map_x, map_y)

            node = self._find_nearest_node(map_x, map_y)
            if node is not None:
                self.selected_node_ids.append(node.node_id)
                if len(self.selected_node_ids) > 2:
                    self.selected_node_ids = self.selected_node_ids[-2:]
                self.nodeClicked.emit(node.node_id)
                self.update()
            else:
                self._dragging = True
                self._last_mouse_pos = event.pos()

        elif event.button() in (Qt.RightButton, Qt.MiddleButton):
            self._dragging = True
            self._last_mouse_pos = event.pos()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        """处理拖拽平移。"""
        if self._dragging and self._last_mouse_pos is not None:
            dx = event.pos().x() - self._last_mouse_pos.x()
            dy = event.pos().y() - self._last_mouse_pos.y()
            self.offset_x += dx
            self.offset_y += dy
            self._last_mouse_pos = event.pos()
            self.update()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        """结束拖拽。"""
        if event.button() in (Qt.LeftButton, Qt.RightButton, Qt.MiddleButton):
            self._dragging = False
            self._last_mouse_pos = None

    def wheelEvent(self, event) -> None:
        """滚轮缩放。"""
        if event.angleDelta().y() > 0:
            self.zoom_in()
        else:
            self.zoom_out()

    def _get_visible_subgraph(self) -> Tuple[List[Node], List[Edge]]:
        """根据当前模式获取需要显示的子图。"""
        assert self.graph is not None
        assert self.spatial_index is not None

        if self.focus_mode == "nearest" and self.focus_point is not None:
            x, y = self.focus_point
            nodes, edges = self.spatial_index.nearest_subgraph(x, y, self.focus_nearest_count)
            return nodes, edges

        rect = self._current_view_rect()
        if self.show_representative_only and self.zoom <= 0.5:
            nodes = self.spatial_index.representative_nodes_in_rect(rect)
            node_ids = {node.node_id for node in nodes}
            edges = []
            checked = set()
            for edge in self.graph.edges.values():
                key = tuple(sorted((edge.start, edge.end)))
                if key in checked:
                    continue
                checked.add(key)
                if edge.start in node_ids and edge.end in node_ids:
                    edges.append(edge)
            return nodes, edges

        nodes = self.spatial_index.nodes_in_rect(rect)
        edges = self.spatial_index.edges_in_rect(rect)
        return nodes, edges

    def _current_view_rect(self) -> Rect:
        """计算当前屏幕对应的地图矩形区域。"""
        left_top = self._screen_to_map(0, 0)
        right_bottom = self._screen_to_map(self.width(), self.height())

        min_x = min(left_top[0], right_bottom[0])
        max_x = max(left_top[0], right_bottom[0])
        min_y = min(left_top[1], right_bottom[1])
        max_y = max(left_top[1], right_bottom[1])

        return Rect(min_x, min_y, max_x, max_y)

    def _draw_edges(self, painter: QPainter, edges: List[Edge]) -> None:
        """绘制边。"""
        assert self.graph is not None

        drawn = set()
        for edge in edges:
            key = tuple(sorted((edge.start, edge.end)))
            if key in drawn:
                continue
            drawn.add(key)

            start_node = self.graph.nodes[edge.start]
            end_node = self.graph.nodes[edge.end]

            sx, sy = self._map_to_screen(start_node.x, start_node.y)
            ex, ey = self._map_to_screen(end_node.x, end_node.y)

            if key in self.highlight_edge_keys:
                pen = QPen(QColor(CONFIG.STYLE.COLOR_PATH), CONFIG.STYLE.PATH_EDGE_WIDTH)
            else:
                pen = QPen(QColor(TrafficModel.traffic_color_name(edge)), CONFIG.STYLE.EDGE_WIDTH)

            painter.setPen(pen)
            painter.drawLine(int(sx), int(sy), int(ex), int(ey))

    def _draw_nodes(self, painter: QPainter, nodes: List[Node]) -> None:
        """绘制节点。"""
        for node in nodes:
            x, y = self._map_to_screen(node.x, node.y)
            radius = CONFIG.STYLE.NODE_RADIUS

            if node.node_id in self.highlight_path_nodes:
                painter.setBrush(QBrush(QColor(CONFIG.STYLE.COLOR_PATH)))
                painter.setPen(QPen(QColor(CONFIG.STYLE.COLOR_PATH), 1))
                r = CONFIG.STYLE.HIGHLIGHT_NODE_RADIUS
                painter.drawEllipse(QPointF(x, y), r, r)
            else:
                painter.setBrush(QBrush(QColor(CONFIG.STYLE.COLOR_NODE)))
                painter.setPen(QPen(QColor(CONFIG.STYLE.COLOR_NODE), 1))
                painter.drawEllipse(QPointF(x, y), radius, radius)

    def _draw_selected_nodes(self, painter: QPainter) -> None:
        """绘制被用户选中的节点外圈。"""
        if self.graph is None:
            return

        painter.setBrush(Qt.NoBrush)
        painter.setPen(QPen(QColor("#3498DB"), 2))

        for node_id in self.selected_node_ids:
            node = self.graph.get_node(node_id)
            if node is None:
                continue
            x, y = self._map_to_screen(node.x, node.y)
            painter.drawEllipse(QPointF(x, y), 9, 9)

    def _find_nearest_node(self, map_x: float, map_y: float, threshold_px: float = 12.0) -> Optional[Node]:
        """根据点击位置寻找最近节点。"""
        if self.spatial_index is None:
            return None

        nearest = self.spatial_index.nearest_nodes(map_x, map_y, k=1)
        if not nearest:
            return None

        node, _ = nearest[0]
        sx, sy = self._map_to_screen(node.x, node.y)
        click_x, click_y = self._map_to_screen(map_x, map_y)
        screen_distance = ((sx - click_x) ** 2 + (sy - click_y) ** 2) ** 0.5
        if screen_distance <= threshold_px:
            return node
        return None

    def _map_to_screen(self, x: float, y: float) -> Tuple[float, float]:
        """地图坐标转屏幕坐标。"""
        sx = x * self.zoom + self.offset_x
        sy = y * self.zoom + self.offset_y
        return sx, sy

    def _screen_to_map(self, sx: float, sy: float) -> Tuple[float, float]:
        """屏幕坐标转地图坐标。"""
        if self.zoom == 0:
            return 0.0, 0.0
        x = (sx - self.offset_x) / self.zoom
        y = (sy - self.offset_y) / self.zoom
        return x, y


if __name__ == "__main__":
    import sys
    from PyQt5.QtWidgets import QApplication
    from map_generator import MapGenerator

    app = QApplication(sys.argv)

    generator = MapGenerator(seed=42)
    graph = generator.generate_map()

    view = MapView()
    view.set_graph(graph)
    view.show()

    sys.exit(app.exec_())

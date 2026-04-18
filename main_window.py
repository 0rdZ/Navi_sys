"""
main_window.py
主窗口模块。
"""

from __future__ import annotations

from typing import Optional

from PyQt5.QtCore import QTimer, Qt
from PyQt5.QtWidgets import (
    QCheckBox,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from config import CONFIG
from graph_algorithms import GraphAlgorithms, PathNotFoundError
from map_generator import MapGenerator
from map_view import MapView
from models import Graph
from traffic_simulator import TrafficSimulator


class MainWindow(QMainWindow):
    """导航系统主窗口。"""

    def __init__(self) -> None:
        super().__init__()

        self.graph: Optional[Graph] = None
        self.simulator: Optional[TrafficSimulator] = None

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._on_timer_tick)
        self.timer.setInterval(CONFIG.TRAFFIC.TIMER_INTERVAL_MS)

        self._setup_ui()
        self._connect_signals()

        self.setWindowTitle(CONFIG.WINDOW.WINDOW_TITLE)
        self.resize(CONFIG.WINDOW.WINDOW_WIDTH, CONFIG.WINDOW.WINDOW_HEIGHT)

    def _setup_ui(self) -> None:
        """创建界面。"""
        central = QWidget()
        self.setCentralWidget(central)

        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(8)

        control_widget = QWidget()
        control_panel = QVBoxLayout(control_widget)
        control_panel.setContentsMargins(0, 0, 0, 0)
        control_panel.setSpacing(8)

        control_panel.addWidget(self._build_map_group())
        control_panel.addWidget(self._build_focus_group())
        control_panel.addWidget(self._build_path_group())
        control_panel.addWidget(self._build_simulation_group())
        control_panel.addWidget(self._build_status_group())
        control_panel.addStretch()

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll_area.setMinimumWidth(340)
        scroll_area.setMaximumWidth(380)
        scroll_area.setWidget(control_widget)

        self.map_view = MapView()

        main_layout.addWidget(scroll_area, 0)
        main_layout.addWidget(self.map_view, 1)

    def _build_map_group(self) -> QGroupBox:
        group = QGroupBox("地图控制")
        layout = QVBoxLayout(group)

        self.btn_generate_map = QPushButton("生成地图")
        self.btn_reset_view = QPushButton("重置视图")
        self.btn_zoom_in = QPushButton("放大")
        self.btn_zoom_out = QPushButton("缩小")
        self.chk_representative = QCheckBox("缩小时只显示代表点")

        layout.addWidget(self.btn_generate_map)

        zoom_layout = QHBoxLayout()
        zoom_layout.addWidget(self.btn_zoom_in)
        zoom_layout.addWidget(self.btn_zoom_out)
        layout.addLayout(zoom_layout)

        layout.addWidget(self.btn_reset_view)
        layout.addWidget(self.chk_representative)
        return group

    def _build_focus_group(self) -> QGroupBox:
        group = QGroupBox("坐标查询 / 附近显示")
        layout = QFormLayout(group)

        self.input_focus_x = QLineEdit()
        self.input_focus_y = QLineEdit()
        self.spin_nearest_count = QSpinBox()
        self.spin_nearest_count.setRange(1, 500)
        self.spin_nearest_count.setValue(CONFIG.MAP.NEAREST_DISPLAY_COUNT)

        self.btn_show_nearest = QPushButton("显示附近节点")
        self.btn_clear_focus = QPushButton("恢复视野模式")

        layout.addRow("坐标 X:", self.input_focus_x)
        layout.addRow("坐标 Y:", self.input_focus_y)
        layout.addRow("显示数量:", self.spin_nearest_count)
        layout.addRow(self.btn_show_nearest)
        layout.addRow(self.btn_clear_focus)
        return group

    def _build_path_group(self) -> QGroupBox:
        group = QGroupBox("路径查询")
        layout = QGridLayout(group)

        self.input_start_node = QLineEdit()
        self.input_end_node = QLineEdit()

        self.btn_shortest_distance = QPushButton("按距离最短路径")
        self.btn_shortest_time = QPushButton("按时间最短路径")
        self.btn_clear_path = QPushButton("清除路径高亮")
        self.btn_use_selected_nodes = QPushButton("使用当前选点")

        layout.addWidget(QLabel("起点 ID:"), 0, 0)
        layout.addWidget(self.input_start_node, 0, 1)
        layout.addWidget(QLabel("终点 ID:"), 1, 0)
        layout.addWidget(self.input_end_node, 1, 1)

        layout.addWidget(self.btn_use_selected_nodes, 2, 0, 1, 2)
        layout.addWidget(self.btn_shortest_distance, 3, 0, 1, 2)
        layout.addWidget(self.btn_shortest_time, 4, 0, 1, 2)
        layout.addWidget(self.btn_clear_path, 5, 0, 1, 2)
        return group

    def _build_simulation_group(self) -> QGroupBox:
        group = QGroupBox("交通仿真")
        layout = QVBoxLayout(group)

        self.btn_start_sim = QPushButton("开始仿真")
        self.btn_stop_sim = QPushButton("停止仿真")
        self.btn_reset_sim = QPushButton("重置仿真")
        self.btn_step_once = QPushButton("单步推进")

        self.label_sim_time = QLabel("当前时间: 0.0")
        self.label_spawned = QLabel("已生成车辆: 0")
        self.label_finished = QLabel("已到达车辆: 0")
        self.label_active = QLabel("活跃车辆: 0")

        layout.addWidget(self.btn_start_sim)
        layout.addWidget(self.btn_stop_sim)
        layout.addWidget(self.btn_step_once)
        layout.addWidget(self.btn_reset_sim)
        layout.addWidget(self.label_sim_time)
        layout.addWidget(self.label_spawned)
        layout.addWidget(self.label_finished)
        layout.addWidget(self.label_active)
        return group

    def _build_status_group(self) -> QGroupBox:
        group = QGroupBox("状态与输出")
        layout = QVBoxLayout(group)

        self.label_clicked_coord = QLabel("点击坐标: -")
        self.label_selected_nodes = QLabel("当前选点: []")

        self.text_output = QTextEdit()
        self.text_output.setReadOnly(True)
        self.text_output.setMinimumWidth(300)
        self.text_output.setMinimumHeight(140)

        layout.addWidget(self.label_clicked_coord)
        layout.addWidget(self.label_selected_nodes)
        layout.addWidget(self.text_output)
        return group

    def _connect_signals(self) -> None:
        self.btn_generate_map.clicked.connect(self.generate_map)
        self.btn_reset_view.clicked.connect(self.map_view.reset_view)
        self.btn_zoom_in.clicked.connect(self.map_view.zoom_in)
        self.btn_zoom_out.clicked.connect(self.map_view.zoom_out)
        self.chk_representative.toggled.connect(self.map_view.set_show_representative_only)

        self.btn_show_nearest.clicked.connect(self.show_nearest_nodes)
        self.btn_clear_focus.clicked.connect(self.clear_focus_mode)

        self.btn_use_selected_nodes.clicked.connect(self.use_selected_nodes)
        self.btn_shortest_distance.clicked.connect(self.show_shortest_distance_path)
        self.btn_shortest_time.clicked.connect(self.show_shortest_time_path)
        self.btn_clear_path.clicked.connect(self.map_view.clear_path_highlight)

        self.btn_start_sim.clicked.connect(self.start_simulation)
        self.btn_stop_sim.clicked.connect(self.stop_simulation)
        self.btn_reset_sim.clicked.connect(self.reset_simulation)
        self.btn_step_once.clicked.connect(self.step_once)

        self.map_view.nodeClicked.connect(self._on_node_clicked)
        self.map_view.coordinateClicked.connect(self._on_coordinate_clicked)

    def generate_map(self) -> None:
        try:
            generator = MapGenerator(seed=42)
            self.graph = generator.generate_map()
            self.simulator = TrafficSimulator(self.graph, seed=42)
            self.map_view.set_graph(self.graph)
            self._update_simulation_labels()
            self._log(f"地图生成完成：节点数={self.graph.node_count()}，边数(含双向)={self.graph.edge_count()}")
        except Exception as exc:
            self._show_error(f"生成地图失败：{exc}")

    def show_nearest_nodes(self) -> None:
        if not self._require_graph():
            return
        try:
            x = float(self.input_focus_x.text().strip())
            y = float(self.input_focus_y.text().strip())
            count = int(self.spin_nearest_count.value())
            self.map_view.set_nearest_display_count(count)
            self.map_view.set_focus_point(x, y, nearest_mode=True)
            self._log(f"显示坐标 ({x:.2f}, {y:.2f}) 附近的 {count} 个节点。")
        except ValueError:
            self._show_warning("请输入合法的坐标数值。")

    def clear_focus_mode(self) -> None:
        self.map_view.focus_mode = "rect"
        self.map_view.focus_point = None
        self.map_view.update()
        self._log("已恢复到当前视野显示模式。")

    def use_selected_nodes(self) -> None:
        selected = self.map_view.selected_nodes()
        if len(selected) < 2:
            self._show_warning("请先在地图上左键选择两个节点。")
            return
        self.input_start_node.setText(str(selected[-2]))
        self.input_end_node.setText(str(selected[-1]))
        self._log(f"已使用选点作为路径查询起终点：{selected[-2]} -> {selected[-1]}")

    def show_shortest_distance_path(self) -> None:
        if not self._require_graph():
            return
        try:
            start, end = self._read_path_input()
            path, total_distance = GraphAlgorithms.shortest_path_by_distance(self.graph, start, end)
            self.map_view.highlight_path(path)
            self._log(f"按距离最短路径：{path}")
            self._log(f"总距离：{total_distance:.2f}")
        except ValueError:
            self._show_warning("请输入合法的起点和终点节点 ID。")
        except PathNotFoundError as exc:
            self._show_warning(str(exc))
        except Exception as exc:
            self._show_error(f"最短路径计算失败：{exc}")

    def show_shortest_time_path(self) -> None:
        if not self._require_graph():
            return
        try:
            start, end = self._read_path_input()
            path, total_time = GraphAlgorithms.shortest_path_by_time(self.graph, start, end)
            self.map_view.highlight_path(path)
            self._log(f"按时间最短路径：{path}")
            self._log(f"总时间：{total_time:.2f}")
        except ValueError:
            self._show_warning("请输入合法的起点和终点节点 ID。")
        except PathNotFoundError as exc:
            self._show_warning(str(exc))
        except Exception as exc:
            self._show_error(f"最短时间路径计算失败：{exc}")

    def start_simulation(self) -> None:
        if not self._require_simulator():
            return
        self.simulator.start()
        self.timer.start()
        self._log("交通仿真已开始。")

    def stop_simulation(self) -> None:
        if self.simulator is None:
            return
        self.simulator.stop()
        self.timer.stop()
        self._log("交通仿真已停止。")

    def reset_simulation(self) -> None:
        if not self._require_simulator():
            return
        self.timer.stop()
        self.simulator.reset()
        self._update_simulation_labels()
        self.map_view.update()
        self._log("交通仿真已重置。")

    def step_once(self) -> None:
        if not self._require_simulator():
            return
        if not self.simulator.is_running():
            self.simulator.start()
            self.simulator.step()
            self.simulator.stop()
        else:
            self.simulator.step()
        self._update_simulation_labels()
        self.map_view.update()

    def _on_timer_tick(self) -> None:
        if self.simulator is None:
            return
        self.simulator.step()
        self._update_simulation_labels()
        self.map_view.update()

    def _on_node_clicked(self, node_id: int) -> None:
        self.label_selected_nodes.setText(f"当前选点: {self.map_view.selected_nodes()}")
        self._log(f"选中节点: {node_id}")

    def _on_coordinate_clicked(self, x: float, y: float) -> None:
        self.label_clicked_coord.setText(f"点击坐标: ({x:.2f}, {y:.2f})")

    def _update_simulation_labels(self) -> None:
        if self.simulator is None:
            self.label_sim_time.setText("当前时间: 0.0")
            self.label_spawned.setText("已生成车辆: 0")
            self.label_finished.setText("已到达车辆: 0")
            self.label_active.setText("活跃车辆: 0")
            return
        stats = self.simulator.stats
        self.label_sim_time.setText(f"当前时间: {stats.current_time:.1f}")
        self.label_spawned.setText(f"已生成车辆: {stats.total_spawned}")
        self.label_finished.setText(f"已到达车辆: {stats.total_finished}")
        self.label_active.setText(f"活跃车辆: {stats.active_vehicles}")

    def _read_path_input(self) -> tuple[int, int]:
        return int(self.input_start_node.text().strip()), int(self.input_end_node.text().strip())

    def _require_graph(self) -> bool:
        if self.graph is None:
            self._show_warning("请先生成地图。")
            return False
        return True

    def _require_simulator(self) -> bool:
        if self.simulator is None:
            self._show_warning("请先生成地图。")
            return False
        return True

    def _log(self, text: str) -> None:
        self.text_output.append(text)

    def _show_warning(self, text: str) -> None:
        QMessageBox.warning(self, "提示", text)

    def _show_error(self, text: str) -> None:
        QMessageBox.critical(self, "错误", text)


if __name__ == "__main__":
    import sys
    from PyQt5.QtWidgets import QApplication

    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())


import os
import sys

try:
    from PySide6 import QtCore, QtWidgets
    from shiboken6 import wrapInstance
except ImportError:
    try:
        from PySide2 import QtCore, QtWidgets
        from shiboken2 import wrapInstance
    except ImportError:
        raise ImportError("无法导入PySide6或PySide2")

import maya.OpenMayaUI as omui
import maya.cmds as cmds

# 导入核心逻辑
try:
    from tile_node_exporter_core import TileNodeExporter
except ImportError:
    current_dir = os.path.dirname(__file__)
    if current_dir not in sys.path:
        sys.path.insert(0, current_dir)
    from tile_node_exporter_core import TileNodeExporter


def get_maya_main_window():
    main_window_ptr = omui.MQtUtil.mainWindow()
    return wrapInstance(int(main_window_ptr), QtWidgets.QWidget)


class TileNodeConfigModel(QtCore.QObject):
    dataChanged = QtCore.Signal()

    def __init__(self):
        super().__init__()
        self._configs = {}

    def load_from_scene(self):
        """刷新节点列表"""
        current_nodes = TileNodeExporter.get_all_tile_nodes()
        print(f"[ConfigModel] 从场景加载节点: {current_nodes}")

        # 移除不存在的节点
        for node in list(self._configs.keys()):
            if node not in current_nodes:
                del self._configs[node]

        # 添加新节点
        for node in current_nodes:
            if node not in self._configs:
                scene_path = cmds.file(query=True, sceneName=True)
                if scene_path:
                    default_dir = os.path.dirname(scene_path)
                else:
                    default_dir = os.path.expanduser("~")
                default_filename = node
                self._configs[node] = {'path': default_dir, 'filename': default_filename}
                print(f"[ConfigModel] 添加新节点 {node}")

        self.dataChanged.emit()
        return current_nodes

    def get_node_config(self, node_name):
        return self._configs.get(node_name)

    def set_node_path(self, node_name, path):
        if node_name in self._configs:
            self._configs[node_name]['path'] = path
            self.dataChanged.emit()

    def set_node_filename(self, node_name, filename):
        if node_name in self._configs:
            self._configs[node_name]['filename'] = filename
            self.dataChanged.emit()

    def get_all_configs(self):
        return {name: (cfg['path'], cfg['filename']) for name, cfg in self._configs.items()}

    def get_node_list(self):
        return list(self._configs.keys())


class TileNodeListView(QtWidgets.QListWidget):
    selectionChanged = QtCore.Signal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        self.itemSelectionChanged.connect(self._on_selection_changed)

    def _on_selection_changed(self):
        selected_names = [item.text() for item in self.selectedItems()]
        self.selectionChanged.emit(selected_names)

    def update_nodes(self, node_names):
        self.clear()
        for name in node_names:
            self.addItem(name)
        print(f"[ListView] 更新列表，共 {len(node_names)} 个节点")


class PropertiesPanel(QtWidgets.QWidget):
    def __init__(self, config_model, parent=None):
        super().__init__(parent)
        self.config_model = config_model
        self.current_node = None
        self.setup_ui()
        self.connect_signals()

    def setup_ui(self):
        layout = QtWidgets.QVBoxLayout(self)

        self.node_label = QtWidgets.QLabel("未选中任何TileNode")
        self.node_label.setStyleSheet("font-weight: bold; font-size: 12px;")
        layout.addWidget(self.node_label)

        # 路径选择
        path_layout = QtWidgets.QHBoxLayout()
        path_label = QtWidgets.QLabel("导出目录:")
        self.path_line = QtWidgets.QLineEdit()
        self.path_line.setReadOnly(True)
        self.browse_btn = QtWidgets.QPushButton("浏览...")
        path_layout.addWidget(path_label)
        path_layout.addWidget(self.path_line)
        path_layout.addWidget(self.browse_btn)
        layout.addLayout(path_layout)

        # 文件名
        name_layout = QtWidgets.QHBoxLayout()
        name_label = QtWidgets.QLabel("文件名:")
        self.filename_line = QtWidgets.QLineEdit()
        self.file_ext_label = QtWidgets.QLabel(".mb")
        self.file_ext_label.setStyleSheet("font-weight: bold; color: green;")
        name_layout.addWidget(name_label)
        name_layout.addWidget(self.filename_line)
        name_layout.addWidget(self.file_ext_label)
        layout.addLayout(name_layout)

        layout.addStretch()

    def connect_signals(self):
        self.browse_btn.clicked.connect(self.on_browse_clicked)
        self.filename_line.editingFinished.connect(self.on_filename_changed)

    def set_current_node(self, node_name):
        self.current_node = node_name
        if node_name is None:
            self.node_label.setText("未选中任何TileNode")
            self.path_line.clear()
            self.filename_line.clear()
            self.setEnabled(False)
        else:
            self.setEnabled(True)
            self.node_label.setText(f"TileNode: {node_name}")
            config = self.config_model.get_node_config(node_name)
            if config:
                self.path_line.setText(config['path'])
                self.filename_line.setText(config['filename'])

    def on_browse_clicked(self):
        if not self.current_node:
            return
        current_dir = self.path_line.text() or os.path.expanduser("~")
        new_dir = QtWidgets.QFileDialog.getExistingDirectory(self, "选择导出目录", current_dir)
        if new_dir:
            self.config_model.set_node_path(self.current_node, new_dir)

    def on_filename_changed(self):
        if self.current_node:
            new_name = self.filename_line.text().strip()
            if new_name:
                self.config_model.set_node_filename(self.current_node, new_name)


class TileNodeExporterUI(QtWidgets.QDialog):
    def __init__(self, parent=get_maya_main_window()):
        super().__init__(parent)
        self.setWindowTitle("TileNode 导出工具")
        self.setMinimumSize(700, 500)
        self.setWindowFlags(QtCore.Qt.Window)

        # 模型
        self.config_model = TileNodeConfigModel()
        self.config_model.dataChanged.connect(self.on_config_updated)

        # UI
        self.create_widgets()
        self.create_layout()
        self.create_connections()

        # 自动刷新
        self.refresh_tile_nodes()

    def create_widgets(self):
        self.list_view = TileNodeListView()
        self.properties_panel = PropertiesPanel(self.config_model)

        # 按钮
        self.create_tileset_btn = QtWidgets.QPushButton("创建Tileset")
        self.refresh_btn = QtWidgets.QPushButton("刷新列表")
        self.export_selected_btn = QtWidgets.QPushButton("导出选中的TileNode")
        self.export_all_btn = QtWidgets.QPushButton("导出所有TileNode")

        self.status_label = QtWidgets.QLabel("就绪")
        self.status_label.setStyleSheet("color: gray; padding: 5px;")

        # 信息面板
        self.info_group = QtWidgets.QGroupBox("使用说明")
        info_text = QtWidgets.QLabel(
            "1. 点击「创建Tileset」创建一个新的空Tileset组\n"
            "2. 点击「刷新列表」加载场景中所有以「Tileset」开头的组\n"
            "3. 选中要导出的TileNode，可多选\n"
            "4. 在右侧设置导出目录和文件名（自动添加.mb后缀）\n"
            "5. 点击「导出选中的TileNode」或「导出所有TileNode」\n\n"
            "提示：导出前会自动刷新列表，确保导出最新的场景状态。"
        )
        info_text.setWordWrap(True)
        info_text.setStyleSheet("color: #FF7F00; font-size: 12px;")
        info_layout = QtWidgets.QVBoxLayout(self.info_group)
        info_layout.addWidget(info_text)

    def create_layout(self):
        self.main_layout = QtWidgets.QVBoxLayout(self)
        self.main_layout.setSpacing(10)

        # 分割线
        splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal)

        # 左侧面板
        left_widget = QtWidgets.QWidget()
        left_layout = QtWidgets.QVBoxLayout(left_widget)
        left_layout.addWidget(QtWidgets.QLabel("场景中的 TileNode:"))
        left_layout.addWidget(self.list_view)

        # 左侧按钮
        left_btn_layout = QtWidgets.QHBoxLayout()
        left_btn_layout.addWidget(self.create_tileset_btn)
        left_btn_layout.addWidget(self.refresh_btn)
        left_layout.addLayout(left_btn_layout)

        # 右侧面板
        right_widget = QtWidgets.QWidget()
        right_layout = QtWidgets.QVBoxLayout(right_widget)
        right_layout.addWidget(QtWidgets.QLabel("导出设置:"))
        right_layout.addWidget(self.properties_panel)
        right_layout.addWidget(self.info_group)

        splitter.addWidget(left_widget)
        splitter.addWidget(right_widget)
        splitter.setSizes([300, 400])

        self.main_layout.addWidget(splitter)

        # 底部按钮
        bottom_btn_layout = QtWidgets.QHBoxLayout()
        bottom_btn_layout.addWidget(self.export_selected_btn)
        bottom_btn_layout.addWidget(self.export_all_btn)
        self.main_layout.addLayout(bottom_btn_layout)
        self.main_layout.addWidget(self.status_label)

    def create_connections(self):
        self.list_view.selectionChanged.connect(self.on_list_selection_changed)
        self.create_tileset_btn.clicked.connect(self.create_tileset)
        self.refresh_btn.clicked.connect(self.refresh_tile_nodes)
        self.export_selected_btn.clicked.connect(self.export_selected)
        self.export_all_btn.clicked.connect(self.export_all)

    def create_tileset(self):
        """创建一个新的空Tileset组"""
        import maya.cmds as cmds

        # 查找现有的Tileset编号
        existing_tilesets = cmds.ls('Tileset_*', type='transform')
        max_num = 0
        for ts in existing_tilesets:
            try:
                num = int(ts.split('_')[-1])
                if num > max_num:
                    max_num = num
            except Exception:
                pass

        new_num = max_num + 1
        new_name = f"Tileset_{new_num}"

        # 创建空组
        new_tileset = cmds.group(empty=True, name=new_name)

        print(f"[UI] 已创建新的Tileset: {new_tileset}")

        # 刷新列表
        self.refresh_tile_nodes()

        # 自动选中新创建的节点
        items = self.list_view.findItems(new_name, QtCore.Qt.MatchExactly)
        if items:
            self.list_view.setCurrentItem(items[0])

        # 在Maya中显示反馈
        cmds.inViewMessage(msg=f'已创建: {new_name}', position='topLine', fade=True, time=2)
        self.status_label.setText(f"✅ 已创建 {new_name}")

    def refresh_tile_nodes(self):
        """刷新节点列表"""
        print("[UI] 开始刷新节点...")
        try:
            # 强制更新场景
            cmds.refresh()

            node_list = self.config_model.load_from_scene()
            self.list_view.update_nodes(node_list)
            self.status_label.setText(f"✅ 已刷新，共找到 {len(node_list)} 个TileNode。")

            if node_list:
                # 保存当前选中的节点
                current_selection = self.list_view.selectedItems()
                if current_selection:
                    current_name = current_selection[0].text()
                    if current_name in node_list:
                        # 如果原来选中的节点还存在，保持选中
                        items = self.list_view.findItems(current_name, QtCore.Qt.MatchExactly)
                        if items:
                            self.list_view.setCurrentItem(items[0])
                    else:
                        self.list_view.setCurrentRow(0)
                else:
                    self.list_view.setCurrentRow(0)
            else:
                self.properties_panel.set_current_node(None)
                print("[UI] 刷新完成，未找到任何节点")

        except Exception as e:
            error_msg = f"刷新失败: {str(e)}"
            self.status_label.setText(f"❌ {error_msg}")
            cmds.warning(error_msg)

    def on_list_selection_changed(self, selected_names):
        if selected_names:
            self.properties_panel.set_current_node(selected_names[0])
        else:
            self.properties_panel.set_current_node(None)

    def on_config_updated(self):
        if self.properties_panel.current_node:
            config = self.config_model.get_node_config(self.properties_panel.current_node)
            if config:
                self.properties_panel.path_line.setText(config['path'])
                self.properties_panel.filename_line.setText(config['filename'])

    def export_selected(self):
        """导出选中的节点（导出前自动刷新）"""
        print("[UI] 导出前自动刷新场景...")

        # 刷新UI，避免卡死
        QtWidgets.QApplication.processEvents()

        # 自动刷新列表
        self.refresh_tile_nodes()

        # 再次刷新UI
        QtWidgets.QApplication.processEvents()

        # 获取选中的节点
        selected_items = self.list_view.selectedItems()
        if not selected_items:
            cmds.warning("请先选中要导出的TileNode")
            return

        selected_nodes = [item.text() for item in selected_items]
        print(f"[UI] 准备导出选中的节点: {selected_nodes}")

        all_configs = self.config_model.get_all_configs()
        export_map = {node: all_configs[node] for node in selected_nodes if node in all_configs}

        if not export_map:
            self.status_label.setText("选中的节点没有有效的配置。")
            return

        self._do_export(export_map, "选中的TileNode导出完成")

    def export_all(self):
        """导出所有节点（导出前自动刷新）"""
        print("[UI] 导出前自动刷新场景...")

        # 刷新UI，避免卡死
        QtWidgets.QApplication.processEvents()

        # 自动刷新列表
        self.refresh_tile_nodes()

        # 再次刷新UI
        QtWidgets.QApplication.processEvents()

        all_configs = self.config_model.get_all_configs()
        if not all_configs:
            self.status_label.setText("没有TileNode可导出。")
            return

        print(f"[UI] 准备导出所有节点: {list(all_configs.keys())}")
        self._do_export(all_configs, "所有TileNode导出完成")

    def _do_export(self, export_map, success_message):
        """执行导出"""
        self.status_label.setText("⏳ 正在导出，请稍候...")

        # 刷新UI，避免卡死
        QtWidgets.QApplication.processEvents()

        # 强制刷新Maya场景
        cmds.refresh()

        results = TileNodeExporter.export_all_tile_nodes(export_map)

        # 刷新UI
        QtWidgets.QApplication.processEvents()

        success_count = sum(1 for v in results.values() if v)
        fail_count = len(results) - success_count

        if fail_count > 0:
            msg = f"⚠️ {success_message}: 成功 {success_count} 个，失败 {fail_count} 个。"
            cmds.warning(msg)
        else:
            msg = f"✅ {success_message}: 成功 {success_count} 个。"
            try:
                cmds.inViewMessage(msg=msg, position='topLine', fade=True, time=3)
            except Exception:
                print(msg)

        self.status_label.setText(msg)

        # 最终刷新
        cmds.refresh()


def launch_tile_node_exporter():
    """启动工具"""
    global tile_node_exporter_ui
    try:
        tile_node_exporter_ui.close()
        tile_node_exporter_ui.deleteLater()
    except Exception:
        pass

    tile_node_exporter_ui = TileNodeExporterUI()
    tile_node_exporter_ui.show()
    return tile_node_exporter_ui


if __name__ == "__main__":
    launch_tile_node_exporter()

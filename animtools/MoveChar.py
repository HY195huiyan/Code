# -*- coding: utf-8 -*-
"""
align_center_ui.py
PySide6 UI 界面 - 基于加权贡献者中心与目标对齐物体
- 可在 Maya 中停靠
- 保存/加载预设 (JSON)
- 调用 AlignObjectsToTargetForTimeline(layerName, targetObjectName, contributors, movers)
"""

from maya import cmds
import json
import os
import AlignToCenterPoint.AlignToCenterPointFunctions as atcp
import BakeTool.bake_tool as bt
from maya_utils.decorators import viewportOff

# ---- Qt / Docking 导入 (PySide6 + shiboken6 for Maya 2024+/2025) ----
from PySide6 import QtCore, QtWidgets, QtGui
import shiboken6
from maya import OpenMayaUI as omui


class ContributorsTable(QtWidgets.QTableWidget):
    """贡献者表格 - 包含物体名称和权重列"""
    rowContextRemoveRequested = QtCore.Signal(list)  # 要删除的行索引列表

    def __init__(self, parent=None):
        super().__init__(0, 2, parent)
        self.setHorizontalHeaderLabels(["物体", "权重"])
        self.horizontalHeader().setStretchLastSection(True)
        self.verticalHeader().setVisible(False)
        self.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.OnContextMenu)
        self.setAlternatingRowColors(True)
        self.setMinimumHeight(140)
        self.setColumnWidth(0, 240)

    def OnContextMenu(self, pos):
        """右键菜单"""
        menu = QtWidgets.QMenu(self)
        actRemove = menu.addAction("删除选中项")
        action = menu.exec_(self.viewport().mapToGlobal(pos))
        if action == actRemove:
            self.EmitRemoveSelectedRows()

    def EmitRemoveSelectedRows(self):
        """发送删除选中行信号"""
        rows = sorted({idx.row() for idx in self.selectedIndexes()}, reverse=True)
        if rows:
            self.rowContextRemoveRequested.emit(rows)

    def AddObjects(self, objNames, defaultWeight=1.0):
        """添加物体到表格"""
        for name in objNames:
            if not name:
                continue
            # 防止重复添加
            if self.FindRowByName(name) != -1:
                continue
            row = self.rowCount()
            self.insertRow(row)
            # 物体名称（不可编辑）
            nameItem = QtWidgets.QTableWidgetItem(name)
            nameItem.setFlags(QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsEnabled)
            self.setItem(row, 0, nameItem)
            # 权重微调框
            spin = QtWidgets.QDoubleSpinBox(self)
            spin.setRange(-100000.0, 100000.0)
            spin.setDecimals(4)
            spin.setSingleStep(0.1)
            spin.setValue(float(defaultWeight))
            spin.setAlignment(QtCore.Qt.AlignRight)
            self.setCellWidget(row, 1, spin)

    def RemoveRows(self, rows):
        """删除指定行"""
        for r in sorted(rows, reverse=True):
            if 0 <= r < self.rowCount():
                self.removeRow(r)

    def FindRowByName(self, name):
        """按名称查找行"""
        for r in range(self.rowCount()):
            item = self.item(r, 0)
            if item and item.text() == name:
                return r
        return -1

    def GetContributorsAndWeights(self):
        """获取所有贡献者名称和权重"""
        names = []
        weights = []
        for r in range(self.rowCount()):
            nameItem = self.item(r, 0)
            spin = self.cellWidget(r, 1)
            if nameItem is None or spin is None:
                continue
            names.append(nameItem.text())
            weights.append(float(spin.value()))
        return names, weights


class SimpleList(QtWidgets.QListWidget):
    """简单列表组件（带右键删除）"""
    rowContextRemoveRequested = QtCore.Signal(list)  # 要删除的行索引列表

    def __init__(self, parent=None, minimumHeight=120):
        super().__init__(parent)
        self.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.OnContextMenu)
        self.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        self.setAlternatingRowColors(True)
        self.setMinimumHeight(minimumHeight)

    def OnContextMenu(self, pos):
        """右键菜单"""
        menu = QtWidgets.QMenu(self)
        actRemove = menu.addAction("删除选中项")
        action = menu.exec_(self.viewport().mapToGlobal(pos))
        if action == actRemove:
            self.EmitRemoveSelectedRows()

    def EmitRemoveSelectedRows(self):
        """发送删除选中行信号"""
        rows = sorted({i.row() for i in self.selectedIndexes()}, reverse=True)
        if rows:
            self.rowContextRemoveRequested.emit(rows)

    def AddUnique(self, entries):
        """添加不重复的项"""
        existing = {self.item(i).text() for i in range(self.count())}
        for e in entries:
            if e and e not in existing:
                self.addItem(e)
                existing.add(e)

    def RemoveRows(self, rows):
        """删除指定行"""
        for r in sorted(rows, reverse=True):
            if 0 <= r < self.count():
                self.takeItem(r)

    def ToList(self):
        """转换为列表"""
        return [self.item(i).text() for i in range(self.count())]


class AlignCenterWindow(QtWidgets.QMainWindow):
    """对齐工具主窗口"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("对齐中心到目标")
        self.resize(800, 1024)

        self.alignFunc = atcp.AlignObjectsToTargetForTimeline

        # 创建中央部件
        central = QtWidgets.QWidget()
        self.setCentralWidget(central)
        self.mainLayout = QtWidgets.QVBoxLayout(central)
        self.mainLayout.setContentsMargins(8, 8, 8, 8)
        self.mainLayout.setSpacing(8)

        # 构建界面
        self.BuildMenuBar()
        self.BuildTopFields()
        self.BuildContributorsSection()
        self.BuildMoversSection()
        self.BuildAlignButton()
        self.AddSeparator()
        self.BuildBatchSection()

        # 加载默认预设
        self.LoadDefaultPresetOnOpen()

    # ---------- UI 构建 ----------
    def BuildMenuBar(self):
        """构建菜单栏"""
        menuBar = self.menuBar()
        settingsMenu = menuBar.addMenu("设置")

        actSave = QtGui.QAction("保存预设", self)
        actSave.triggered.connect(self.SavePreset)
        settingsMenu.addAction(actSave)

        actLoad = QtGui.QAction("加载预设", self)
        actLoad.triggered.connect(self.LoadPreset)
        settingsMenu.addAction(actLoad)

    def BuildTopFields(self):
        """构建顶部输入字段"""
        # 层名称
        layerRow = QtWidgets.QHBoxLayout()
        layerLabel = QtWidgets.QLabel("层名称:")
        self.layerNameEdit = QtWidgets.QLineEdit()
        layerRow.addWidget(layerLabel)
        layerRow.addWidget(self.layerNameEdit)
        self.mainLayout.addLayout(layerRow)

        # 目标物体名称 + 拾取按钮
        targetRow = QtWidgets.QHBoxLayout()
        targetLabel = QtWidgets.QLabel("目标物体名称:")
        self.targetObjectEdit = QtWidgets.QLineEdit()
        self.pickTargetBtn = QtWidgets.QPushButton("拾取")
        self.pickTargetBtn.setToolTip("使用 Maya 中最后选中的物体")
        self.pickTargetBtn.clicked.connect(self.SetTargetFromSelection)
        targetRow.addWidget(targetLabel)
        targetRow.addWidget(self.targetObjectEdit)
        targetRow.addWidget(self.pickTargetBtn)
        self.mainLayout.addLayout(targetRow)

    def BuildContributorsSection(self):
        """构建贡献者区域"""
        headerRow = QtWidgets.QHBoxLayout()
        headerLabel = QtWidgets.QLabel("贡献者（加权中心）")
        headerLabel.setStyleSheet("font-weight: bold;")
        self.addContribBtn = QtWidgets.QPushButton("添加选中物体")
        self.addContribBtn.clicked.connect(self.AddSelectedContributors)
        headerRow.addWidget(headerLabel)
        headerRow.addStretch(1)
        headerRow.addWidget(self.addContribBtn)
        self.mainLayout.addLayout(headerRow)

        self.contributorsTable = ContributorsTable(self)
        self.contributorsTable.rowContextRemoveRequested.connect(self.RemoveContribRows)
        self.mainLayout.addWidget(self.contributorsTable)

    def BuildMoversSection(self):
        """构建移动物体区域"""
        headerRow = QtWidgets.QHBoxLayout()
        headerLabel = QtWidgets.QLabel("移动物体（要平移的物体）")
        headerLabel.setStyleSheet("font-weight: bold;")
        self.addMoverBtn = QtWidgets.QPushButton("添加选中物体")
        self.addMoverBtn.clicked.connect(self.AddSelectedMovers)
        headerRow.addWidget(headerLabel)
        headerRow.addStretch(1)
        headerRow.addWidget(self.addMoverBtn)
        self.mainLayout.addLayout(headerRow)

        self.moversList = SimpleList(self, minimumHeight=120)
        self.moversList.rowContextRemoveRequested.connect(self.RemoveMoverRows)
        self.mainLayout.addWidget(self.moversList)

    def BuildAlignButton(self):
        """构建对齐按钮"""
        self.alignBtn = QtWidgets.QPushButton("对齐物体到目标")
        self.alignBtn.setMinimumHeight(36)
        self.alignBtn.clicked.connect(self.OnAlignClicked)
        self.mainLayout.addWidget(self.alignBtn)

    def AddSeparator(self):
        """添加分隔线"""
        line = QtWidgets.QFrame()
        line.setFrameShape(QtWidgets.QFrame.HLine)
        line.setFrameShadow(QtWidgets.QFrame.Sunken)
        self.mainLayout.addWidget(line)

    def BuildBatchSection(self):
        """构建批量处理区域"""
        headerRow = QtWidgets.QHBoxLayout()
        headerLabel = QtWidgets.QLabel("批量文件")
        headerLabel.setStyleSheet("font-weight: bold;")
        self.addFilesBtn = QtWidgets.QPushButton("添加文件")
        self.addFilesBtn.clicked.connect(self.AddBatchFiles)
        headerRow.addWidget(headerLabel)
        headerRow.addStretch(1)
        headerRow.addWidget(self.addFilesBtn)
        self.mainLayout.addLayout(headerRow)

        self.filesList = SimpleList(self, minimumHeight=150)
        self.filesList.rowContextRemoveRequested.connect(self.RemoveFileRows)
        self.mainLayout.addWidget(self.filesList)

        self.batchBtn = QtWidgets.QPushButton("批量处理文件")
        self.batchBtn.setMinimumHeight(34)
        self.batchBtn.clicked.connect(self.OnBatchClicked)
        self.mainLayout.addWidget(self.batchBtn)

        self.statusLabel = QtWidgets.QLabel("")
        self.statusLabel.setWordWrap(True)
        self.statusLabel.setStyleSheet("color: #89d07f;")  # 成功颜色
        self.mainLayout.addWidget(self.statusLabel)

    # ---------- 设置持久化 ----------
    def GetSettingsFilePath(self):
        """获取设置文件路径"""
        return os.path.join(self.GetScriptFolder(), "AlignCenterSettings.json")

    def LoadSettingsDict(self):
        """读取设置 JSON"""
        try:
            path = self.GetSettingsFilePath()
            if os.path.isfile(path):
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f) or {}
        except Exception:
            pass
        return {}

    def SaveSettingsDict(self, data):
        """保存设置 JSON"""
        try:
            path = self.GetSettingsFilePath()
            os.makedirs(self.GetScriptFolder(), exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data or {}, f, indent=2)
        except Exception:
            pass

    def GetLastBatchDir(self):
        """获取上次使用的批量目录"""
        data = self.LoadSettingsDict()
        lastDir = data.get("lastBatchDir", "")
        if lastDir and os.path.isdir(lastDir):
            return lastDir
        return ""

    def SetLastBatchDir(self, folderPath):
        """保存上次使用的批量目录"""
        if not folderPath:
            return
        data = self.LoadSettingsDict()
        data["lastBatchDir"] = folderPath
        self.SaveSettingsDict(data)

    # ---------- 默认值 / 预设 ----------
    def RestoreDefaults(self):
        """恢复默认值"""
        self.layerNameEdit.setText("")
        self.targetObjectEdit.setText("")
        self.contributorsTable.setRowCount(0)
        self.moversList.clear()
        self.filesList.clear()

    def GetScriptFolder(self):
        """获取脚本所在文件夹"""
        try:
            return os.path.dirname(os.path.abspath(atcp.__file__))
        except NameError:
            return os.getcwd()

    def GetPresetsFolderPath(self):
        """获取预设文件夹路径"""
        return os.path.join(self.GetScriptFolder(), "Presets")

    def GetDefaultPresetPath(self):
        """获取默认预设路径"""
        return os.path.join(self.GetPresetsFolderPath(), "Default.json")

    def LoadDefaultPresetOnOpen(self):
        """打开时加载默认预设"""
        path = self.GetDefaultPresetPath()
        if os.path.exists(path):
            try:
                self.LoadPresetFromPath(path)
                self.ShowStatus(f"已加载默认预设: {path}")
                return
            except Exception as e:
                self.Warn(f"加载默认预设失败:\n{path}\n\n{e}")
        # 未找到预设或加载失败
        self.RestoreDefaults()
        self.ShowStatus("未找到默认预设，使用空默认设置。")

    def SavePreset(self):
        """保存预设"""
        preset = {
            "layerName": self.layerNameEdit.text().strip(),
            "targetObjectName": self.targetObjectEdit.text().strip(),
            "contributors": [],
            "movers": self.moversList.ToList(),
            "batchFiles": self.filesList.ToList()
        }
        contribNames, contribWeights = self.contributorsTable.GetContributorsAndWeights()
        for name, w in zip(contribNames, contribWeights):
            preset["contributors"].append({"name": name, "weight": float(w)})

        defaultDir = self.GetPresetsFolderPath()
        if not os.path.isdir(defaultDir):
            try:
                os.makedirs(defaultDir, exist_ok=True)
            except Exception:
                defaultDir = ""

        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "保存预设", os.path.join(defaultDir, "预设.json"), "JSON 文件 (*.json)")
        if not path:
            return
        if not path.lower().endswith(".json"):
            path += ".json"
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(preset, f, indent=2)
            self.ShowStatus(f"预设已保存: {path}")
        except Exception as e:
            self.Warn(f"保存预设失败:\n{e}")

    def LoadPreset(self):
        """加载预设"""
        defaultDir = self.GetPresetsFolderPath()
        if not os.path.isdir(defaultDir):
            defaultDir = ""
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "加载预设", defaultDir, "JSON 文件 (*.json)")
        if not path:
            return
        try:
            self.LoadPresetFromPath(path)
            self.ShowStatus(f"预设已加载: {path}")
        except Exception as e:
            self.Warn(f"加载预设失败:\n{e}")

    def LoadPresetFromPath(self, path):
        """从路径加载预设"""
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        self.layerNameEdit.setText(data.get("layerName", "AlignToZeroCtrl"))
        self.targetObjectEdit.setText(data.get("targetObjectName", "zeroJointControl1"))

        self.contributorsTable.setRowCount(0)
        for c in data.get("contributors", []):
            name = c.get("name", "")
            weight = float(c.get("weight", 1.0))
            if name:
                self.contributorsTable.AddObjects([name], defaultWeight=weight)

        self.moversList.clear()
        self.moversList.AddUnique(data.get("movers", []))

        self.filesList.clear()
        self.filesList.AddUnique(data.get("batchFiles", []))

    # ---------- Maya 选择辅助 ----------
    def GetSelectedObjects(self):
        """获取选中的物体"""
        sel = cmds.ls(sl=True) or []
        return sel

    def GetLastSelectedObject(self):
        """获取最后选中的物体"""
        sel = cmds.ls(sl=True) or []
        return sel[-1] if sel else None

    # ---------- 按钮/操作处理 ----------
    def SetTargetFromSelection(self):
        """从选择设置目标"""
        lastSel = self.GetLastSelectedObject()
        if lastSel:
            self.targetObjectEdit.setText(lastSel)

    def AddSelectedContributors(self):
        """添加选中的贡献者"""
        objs = self.GetSelectedObjects()
        objs = [o.split(":")[-1] for o in objs]
        if objs:
            self.contributorsTable.AddObjects(objs, defaultWeight=1.0)

    def RemoveContribRows(self, rows):
        """删除贡献者行"""
        self.contributorsTable.RemoveRows(rows)

    def AddSelectedMovers(self):
        """添加选中的移动物体"""
        objs = self.GetSelectedObjects()
        objs = [o.split(":")[-1] for o in objs]
        if objs:
            self.moversList.AddUnique(objs)

    def RemoveMoverRows(self, rows):
        """删除移动物体行"""
        self.moversList.RemoveRows(rows)

    def AddBatchFiles(self):
        """添加批量文件"""
        startDir = self.GetLastBatchDir()
        if not startDir:
            startDir = ""

        files, _ = QtWidgets.QFileDialog.getOpenFileNames(
            self,
            "添加 Maya 批量文件",
            startDir,
            "Maya 文件 (*.ma *.mb);;所有文件 (*.*)"
        )

        if files:
            firstDir = os.path.dirname(files[0])
            if firstDir and os.path.isdir(firstDir):
                self.SetLastBatchDir(firstDir)
            self.filesList.AddUnique(files)

    def RemoveFileRows(self, rows):
        """删除文件行"""
        self.filesList.RemoveRows(rows)

    def OnAlignClicked(self):
        """单次对齐"""
        try:
            layerName = self.layerNameEdit.text().strip()
            targetObject = self.targetObjectEdit.text().strip()
            contribNames, weights = self.contributorsTable.GetContributorsAndWeights()
            movers = self.moversList.ToList()

            if not targetObject:
                self.Warn("请设置目标物体名称。")
                return
            if not contribNames:
                self.Warn("请至少添加一个贡献者。")
                return
            if not movers:
                self.Warn("请至少添加一个移动物体。")
                return

            # 调用对齐函数
            self.alignFunc(
                layerName=layerName,
                targetObjectName=targetObject,
                contributors=contribNames,
                movers=movers,
                weights=weights,
            )
            self.ShowStatus("对齐完成。")
        except Exception as e:
            self.Warn(f"对齐失败:\n{e}")

    @viewportOff
    def OnBatchClicked(self):
        """批量处理"""
        files = self.filesList.ToList()
        if not files:
            self.Warn("请添加批量文件。")
            return

        # 进入安静模式，避免批量处理时弹窗
        self.BeginBatchErrorAggregation()
        try:
            layerName = self.layerNameEdit.text().strip()
            targetObject = self.targetObjectEdit.text().strip()
            contribNames, weights = self.contributorsTable.GetContributorsAndWeights()
            movers = self.moversList.ToList()

            if not targetObject or not contribNames or not movers:
                self.Warn("批量处理需要目标、贡献者和移动物体。")
                return

            # P4 检出
            try:
                bt.checkOutFilesTemp(files)
                bt.determineFileWritability(files)
                bt.importFilesToP4(files)
            except Exception as e:
                self.AppendBatchError(f"P4 检出失败: {e}")

            # 处理文件
            processed = 0
            totalCount = len(files)

            for path in files:
                # 打开文件
                try:
                    cmds.file(path, o=True, f=True, prompt=False)
                except Exception as e:
                    self.AppendBatchError(f"打开文件失败: {os.path.basename(path)}\n{e}")
                    continue

                # 对齐
                try:
                    self.alignFunc(
                        layerName=layerName,
                        targetObjectName=targetObject,
                        contributors=contribNames,
                        movers=movers,
                        weights=weights,
                    )
                except Exception as e:
                    self.AppendBatchError(f"对齐失败: {os.path.basename(path)}\n{e}")
                    continue

                # 保存
                try:
                    cmds.file(save=True)
                except Exception as e:
                    self.AppendBatchError(f"保存失败 (可能为只读): {os.path.basename(path)}\n{e}")
                    continue

                processed += 1
                self.ShowStatus(f"已处理 {processed}/{totalCount}: {os.path.basename(path)}")

            self.ShowStatus(f"批量处理完成。{processed}/{len(files)} 个文件处理成功。")

        except Exception as e:
            self.Warn(f"批量处理失败:\n{e}")

        finally:
            self.ShowAllBatchErrorsAtEnd()

    # ---------- 工具方法 ----------
    def ShowStatus(self, msg):
        """显示状态信息"""
        self.statusLabel.setText(msg)
        print("[对齐工具]", msg)

    def Warn(self, msg):
        """
        警告处理
        - 批量模式下：收集错误（不弹窗）
        - 非批量模式：弹出警告对话框
        """
        print("[对齐工具][警告]", msg)

        if getattr(self, "suppressPopupsDuringBatch", False):
            self.AppendBatchError(msg)
            return

        QtWidgets.QMessageBox.warning(self, "对齐工具", msg)

    # ---------- 错误缓存 ----------
    def BeginBatchErrorAggregation(self):
        """开始批量错误聚合（安静模式）"""
        self.suppressPopupsDuringBatch = True
        self.batchErrors = []

    def AppendBatchError(self, msg):
        """收集错误信息"""
        if not hasattr(self, "batchErrors"):
            self.batchErrors = []
        self.batchErrors.append(msg)

    def ShowAllBatchErrorsAtEnd(self):
        """批量结束时显示所有错误"""
        self.suppressPopupsDuringBatch = False
        errors = getattr(self, "batchErrors", []) or []
        if not errors:
            self.batchErrors = []
            return

        maxLines = 200
        body = "\n".join(f"- {e}" for e in errors[:maxLines])
        extra = "" if len(errors) <= maxLines else f"\n\n(+ 还有 {len(errors) - maxLines} 条)"
        text = f"批量处理期间出现 {len(errors)} 个问题:\n\n{body}{extra}"

        QtWidgets.QMessageBox.warning(self, "对齐工具 — 批量问题", text)
        self.batchErrors = []


# ---------- 停靠辅助 ----------
def _GetMayaMainWindow():
    """获取 Maya 主窗口"""
    ptr = omui.MQtUtil.mainWindow()
    if ptr is not None:
        return shiboken6.wrapInstance(int(ptr), QtWidgets.QWidget)
    return None


def _DockToWorkspace(widget, title="对齐中心工具", controlName="AlignCenterUIWorkspaceControl"):
    """
    将窗口停靠到 Maya 工作区
    """
    if cmds.workspaceControl(controlName, exists=True):
        try:
            cmds.deleteUI(controlName)
        except Exception:
            pass

    ctrl = cmds.workspaceControl(
        controlName,
        label=title,
        retain=False,
        floating=False
    )

    qtCtrl = omui.MQtUtil.findControl(ctrl)
    parentWidget = shiboken6.wrapInstance(int(qtCtrl), QtWidgets.QWidget)

    # 清空原有布局
    for child in parentWidget.children():
        try:
            child.setParent(None)
        except Exception:
            pass

    layout = QtWidgets.QVBoxLayout(parentWidget)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.addWidget(widget)
    return ctrl


# ---------- 公开入口 ----------
def ShowWindow(dock=True):
    """
    创建并显示 UI
    
    Args:
        dock: True 停靠到 Maya，False 浮动窗口
    """
    mainWin = _GetMayaMainWindow()
    ui = AlignCenterWindow(parent=mainWin)

    if dock:
        _DockToWorkspace(ui, title="对齐中心工具", controlName="AlignCenterUIWorkspaceControl")
    else:
        ui.setParent(mainWin)
        ui.setWindowFlag(QtCore.Qt.Window, True)
        ui.show()

    return ui


def CreateAndShow(dock=False):
    """
    ShowWindow 的别名
    """
    return ShowWindow(dock=dock)


# ---------- 直接运行测试 ----------
if __name__ == "__main__":
    ShowWindow(dock=True)

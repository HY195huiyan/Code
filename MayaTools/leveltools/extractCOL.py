
from smpub.qt.QtWrapper.QtWidgets import (QWidget, QLabel, QCheckBox, QPushButton,
                                          QHBoxLayout, QVBoxLayout, QFormLayout,
                                          QScrollArea, QComboBox, QListWidget)
from smpub.qt.QtWrapper.QtCore import Qt, Signal

from maya.api import OpenMaya
from maya import cmds

from maya_widgets import window_widget

import json
import sys
import os


def iterateRefNodes(nodes):
    """
    遍历引用节点，提取 transform 和 refNode 的配对
    输入可以是 transform 或 shape 节点列表
    """
    transformAndShape = [None, None]
    for node in nodes:
        if cmds.nodeType(node) == "transform":
            transformAndShape[0] = node

            children = cmds.listRelatives(node, children=True, fullPath=True)
            if children:
                child = children[0]
                if cmds.nodeType(child) != "refNode":
                    continue

                transformAndShape[1] = children[0]

        elif cmds.nodeType(node) == "refNode":
            transformAndShape[1] = node
            transformAndShape[0] = "|".join(node.split("|")[:-1])
        else:
            continue

        yield transformAndShape


def extractMeshesFromMayaFile(mayaFilePath, visualMeshes=False, highestLod=False):
    """
    从 Maya 文件中提取网格
    highestLod 仅在 visualMeshes 为 True 时生效
    返回包含节点和材质信息的字典
    """
    kwargs = {
        "mayaFile": mayaFilePath,
        "buildMayaFile": True}

    if visualMeshes:
        kwargs["mode"] = 1
        if highestLod:
            kwargs["highestLodLevel"] = True
    else:
        kwargs["extractCollisionMaterials"] = True

    return json.loads(cmds.WadToImageExporter_CreateMayaMeshFromX3DFile(**kwargs))


def assignMaterialsToExtractedMeshes(results, shaderNetworksById):
    """
    将提取的材质分配给对应的网格
    """
    materialToMeshAssignments = results.get("meshMaterialAssignments", dict())
    for meshDagPath, materialId in list(materialToMeshAssignments.items()):
        material, shadingGroup = shaderNetworksById.get(materialId, (None, None))
        if not shadingGroup:
            continue
        cmds.sets(meshDagPath, edit=True, forceElement=shadingGroup)

    meshMaterialToFaceAssignments = results.get("meshMaterialToFaceAssignments", dict())
    for meshDagPath, faceAssignmentsByMaterialId in list(meshMaterialToFaceAssignments.items()):
        for materialId, faceAssignmentRanges in list(faceAssignmentsByMaterialId.items()):
            material, shadingGroup = shaderNetworksById.get(materialId, (None, None))
            if not shadingGroup:
                continue
            objects = list()
            for rangeData in faceAssignmentRanges:
                start = rangeData["start"]
                end = rangeData["end"]
                if start == end:
                    objects.append("{}.f[{}]".format(meshDagPath, start))
                else:
                    objects.append("{}.f[{}:{}]".format(meshDagPath, start, end))
            cmds.sets(objects, edit=True, forceElement=shadingGroup)


# 当提取碰撞网格时，某些文件可能没有碰撞网格
# 此窗口为用户提供从这些文件中提取视觉网格的选项
class ExtractVisualMeshesWidget(QWidget):
    """提取视觉网格的确认窗口"""

    closeRequested = Signal()

    def __init__(self, refNodeTransformAndShapesByMayaFile, parent=None):
        super(ExtractVisualMeshesWidget, self).__init__(parent)

        self.__initGUI()
        self.__refNodeTransformAndShapesByMayaFile = refNodeTransformAndShapesByMayaFile

        for mayaFilePath in list(refNodeTransformAndShapesByMayaFile.keys()):
            self.__filesList.addItem(os.path.basename(mayaFilePath))

    def __initGUI(self):
        """初始化界面"""
        # 文件列表
        self.__filesList = QListWidget(self)
        self.__filesList.setSelectionMode(QListWidget.NoSelection)

        # LOD 级别选择
        self.__extractionLevel = QComboBox(self)
        self.__extractionLevel.addItems(("提取最低 LOD", "提取最高 LOD"))

        # 按钮
        extractButton = QPushButton("提取", self)
        extractButton.clicked.connect(self.__onExtractButtonClicked)
        cancelButton = QPushButton("取消", self)
        cancelButton.clicked.connect(self.closeRequested)

        # 按钮布局
        buttonsLayout = QHBoxLayout()
        buttonsLayout.setContentsMargins(0, 0, 0, 0)
        buttonsLayout.setSpacing(4)
        buttonsLayout.addWidget(extractButton)
        buttonsLayout.addWidget(cancelButton)

        # 主布局
        mainLayout = QVBoxLayout()
        mainLayout.setContentsMargins(4, 4, 4, 4)
        mainLayout.setSpacing(4)
        mainLayout.addWidget(QLabel(
            "以下文件没有碰撞网格。\n是否要改为提取视觉网格？"
        ))
        mainLayout.addWidget(self.__filesList)
        mainLayout.addWidget(self.__extractionLevel)
        mainLayout.addLayout(buttonsLayout)

        self.setLayout(mainLayout)

    def __onExtractButtonClicked(self):
        """提取按钮点击事件"""
        extractHighestLod = (self.__extractionLevel.currentIndex() == 1)

        cmds.undoInfo(openChunk=True, chunkName="ExtractVisualMeshes")
        parentTransforms = list()
        for mayaFilePath, transformAndShapes in list(self.__refNodeTransformAndShapesByMayaFile.items()):
            results = extractMeshesFromMayaFile(mayaFilePath, True, extractHighestLod)
            nodes = results.get("resultNodes", list())

            if len(nodes) == 1:
                cmds.delete(nodes)
                continue

            # 视觉网格没有材质，分配到默认着色组
            cmds.sets(nodes, edit=True, forceElement="initialShadingGroup")

            parentTransform = nodes[0]
            for transformNode, refNode in transformAndShapes:
                transformMatrixWS = cmds.xform(transformNode, query=True, matrix=True, worldSpace=True)
                duplicatedTransform = cmds.ls(cmds.duplicate(parentTransform), long=True)[0]
                parentTransforms.append(duplicatedTransform)
                cmds.xform(duplicatedTransform, matrix=transformMatrixWS, worldSpace=True)
                cmds.setAttr("{}.DisableCollision".format(refNode), True)
            cmds.delete(parentTransform)

        if parentTransforms:
            cmds.group(parentTransforms, name="提取_视觉网格")

        cmds.undoInfo(closeChunk=True)

        self.closeRequested.emit()


def run(nodes):
    """
    主运行函数
    参数: nodes - 选中的节点列表
    """
    # 加载插件
    cmds.loadPlugin("MayaWadToImageExporterPlugin")
    
    # 按文件路径分组引用节点
    refNodeTransformsByFilePath = dict()
    for transform, refNode in iterateRefNodes(nodes):
        mayaFilePath = cmds.getAttr("{}.fileName".format(refNode))
        if not mayaFilePath:
            continue

        mayaFilePath = os.path.normpath(mayaFilePath).lower()
        if mayaFilePath not in refNodeTransformsByFilePath:
            refNodeTransformsByFilePath[mayaFilePath] = list()
        refNodeTransformsByFilePath[mayaFilePath].append((transform, refNode))

    if not refNodeTransformsByFilePath:
        OpenMaya.MGlobal.displayWarning("未选择包含有效文件路径的引用节点")
        return

    cmds.undoInfo(openChunk=True, chunkName="提取碰撞网格")

    shaderNetworksById = dict()
    parentTransforms = list()
    refNodeTransformAndShapesWithNoCollisionByFilePath = dict()
    
    for mayaFilePath, transformAndShapes in list(refNodeTransformsByFilePath.items()):
        # 提取碰撞网格
        results = extractMeshesFromMayaFile(mayaFilePath)
        nodes = results.get("resultNodes", list())

        # 如果只有一个节点，说明没有碰撞网格
        if len(nodes) == 1:
            refNodeTransformAndShapesWithNoCollisionByFilePath[mayaFilePath] = transformAndShapes
            cmds.delete(nodes)
            continue

        # 处理材质网络
        resultShaderNetworks = results.get("resultShaderNetworks", dict())
        # 去重：多个场景可能共享相同的材质
        for materialId, shaderNetwork in list(resultShaderNetworks.items()):
            if materialId not in shaderNetworksById:
                shaderNetworksById[materialId] = shaderNetwork
            else:
                cmds.delete(shaderNetwork)

        # 分配材质到网格
        assignMaterialsToExtractedMeshes(results, shaderNetworksById)

        # 复制网格到原引用位置
        parentTransform = nodes[0]
        for transformNode, refNode in transformAndShapes:
            transformMatrixWS = cmds.xform(transformNode, query=True, matrix=True, worldSpace=True)
            duplicatedTransform = cmds.ls(cmds.duplicate(parentTransform), long=True)[0]
            parentTransforms.append(duplicatedTransform)
            cmds.xform(duplicatedTransform, matrix=transformMatrixWS, worldSpace=True)
            cmds.setAttr("{}.DisableCollision".format(refNode), True)
        cmds.delete(parentTransform)

    # 将提取的碰撞网格分组
    if parentTransforms:
        cmds.group(parentTransforms, name="提取_碰撞网格")

    cmds.undoInfo(closeChunk=True)

    # 如果有文件没有碰撞网格，弹出提取视觉网格的窗口
    if refNodeTransformAndShapesWithNoCollisionByFilePath:
        widget = ExtractVisualMeshesWidget(refNodeTransformAndShapesWithNoCollisionByFilePath)

        window = window_widget.createWindow(
            title="提取视觉网格？", 
            minimumWidth=200, 
            minimumHeight=100, 
            recreate=True
        )
        window.setCentralWidget(widget)
        window.show()

        widget.closeRequested.connect(window.close)


def runOnSelection():
    """从选中的节点运行"""
    try:
        run(cmds.ls(selection=True, long=True))
    except:
        import traceback
        traceback.print_exc()
import json
import os
import re
import traceback

from maya import OpenMaya
from maya import cmds
from maya import mel

import anim_layers
import ReadAnim
import set_api_clipboard


if cmds.pluginInfo("animImportExport", q=True, l=True) != 1:
    cmds.loadPlugin("animImportExport")

PROJ_PATH = os.environ['PROJ_PATH']
DEFAULT_SAVE_DIR = os.path.join(PROJ_PATH, "GameArt", "Characters")
HIDDEN_ATTRIBUTES_DATA = {
    "timecode": {"regex": "TC*", "function": lambda *args: getTimecodeAttrKeys(args)}}

MAYA_VERSION = int(cmds.about(version=True))

# 全局变量存储选择的路径
SELECTED_SAVE_DIR = DEFAULT_SAVE_DIR
SELECTED_TXT_FILE = ""


def select_save_directory():
    """使用 Maya 文件对话框让用户选择保存位置"""
    global SELECTED_SAVE_DIR
    
    # 使用 Maya 的 fileDialog
    selected_dir = cmds.fileDialog2(
        dialogStyle=2,  # 使用 Qt 风格对话框
        fileMode=3,     # 目录选择模式
        caption="请选择保存 selection.txt 和动画文件的目录",
        startingDirectory=DEFAULT_SAVE_DIR if os.path.exists(DEFAULT_SAVE_DIR) else os.path.dirname(DEFAULT_SAVE_DIR)
    )
    
    if selected_dir:
        SELECTED_SAVE_DIR = selected_dir[0]
        print(f"✅ 已选择保存目录: {SELECTED_SAVE_DIR}")
        return True
    else:
        print("❌ 未选择目录，将使用默认路径")
        SELECTED_SAVE_DIR = DEFAULT_SAVE_DIR
        return False


def select_txt_file():
    """使用 Maya 文件对话框让用户选择要读取的 txt 文件"""
    global SELECTED_TXT_FILE, SELECTED_SAVE_DIR
    
    # 设置初始目录
    initial_dir = SELECTED_SAVE_DIR if os.path.exists(SELECTED_SAVE_DIR) else DEFAULT_SAVE_DIR
    
    # 使用 Maya 的 fileDialog
    selected_file = cmds.fileDialog2(
        dialogStyle=2,  # 使用 Qt 风格对话框
        fileMode=1,     # 文件选择模式
        caption="请选择要读取的 selection.txt 文件",
        startingDirectory=initial_dir,
        fileFilter="文本文件 (*.txt);;所有文件 (*.*)"
    )
    
    if selected_file:
        SELECTED_TXT_FILE = selected_file[0]
        SELECTED_SAVE_DIR = os.path.dirname(SELECTED_TXT_FILE)  # 同时更新保存目录
        print(f"✅ 已选择文件: {SELECTED_TXT_FILE}")
        return True
    else:
        print("❌ 未选择文件")
        return False


def convertLongToShortPaths(filePath):
    """将 .anim 文件中的路径改为短路径。这是针对 Maya2019 animExport 写入完整 dagPath 名称的临时修复。

    :param filePath: str, .anim 文件路径
    :return:
    """
    with open(filePath, 'r') as animFile:
        fileDataList = animFile.readlines()

    cleanDataList = []
    for line in fileDataList:
        if line.startswith("anim "):
            parts = line.split(' ')
            if parts[-4].find('|') > -1:
                parts[-4] = parts[-4].rsplit('|', 1)[-1]
            cleanDataList.append(" ".join(parts))
        else:
            cleanDataList.append(line)

    with open(filePath, 'w') as animFile:
        animFile.writelines(cleanDataList)


def replacePrefix(objPath, newPrefix):
    """用新的命名空间替换旧的控件命名空间。

    :param objPath: str, 被复制节点的完整路径
    :param newPrefix: str, 新的命名空间
    :return: str, 带有新命名空间的控件名称
    """
    if newPrefix != "" and not newPrefix.endswith(":"):
        newPrefix = f"{newPrefix}:"

    splitPath = objPath.split("|")
    for i in range(len(splitPath)):
        oldPrefix = re.match("^.+:", splitPath[i])
        if str(oldPrefix.group()) != "":
            splitPath[i] = re.sub("^.+:", newPrefix, splitPath[i])
        else:
            splitPath[i] = newPrefix + splitPath[i]

    newPath = "|".join(splitPath)
    return newPath


def confirmBufferKeys(pasteByNamespace=False):
    """执行 Maya 对话框询问用户是否要插入或合并关键帧。

    :return:
    """
    global SELECTED_TXT_FILE, SELECTED_SAVE_DIR
    
    # 在选择文件之前先弹出文件选择对话框
    if not select_txt_file():
        OpenMaya.MGlobal.displayError("未选择文件，操作取消。")
        return
    
    # 检查选择的文件是否是 selection.txt
    if not SELECTED_TXT_FILE.endswith('selection.txt'):
        # 如果选择的不是 selection.txt，尝试在同目录下找
        dir_path = os.path.dirname(SELECTED_TXT_FILE)
        possible_file = os.path.join(dir_path, 'selection.txt')
        if os.path.exists(possible_file):
            SELECTED_TXT_FILE = possible_file
            print(f"✅ 自动定位到: {SELECTED_TXT_FILE}")
        else:
            OpenMaya.MGlobal.displayError(f"请选择 selection.txt 文件！当前选择: {SELECTED_TXT_FILE}")
            return
    
    set_api_clipboard.resetAPIClipboard()
    result = cmds.confirmDialog(
        title='添加缓冲关键帧',
        message='是否在选定的帧范围之前添加关键帧以保留动画？',
        button=['是', '否', '取消'],
        cancelButton='取消'
    )

    if result == '是':
        pasteKeys(True, "merge", pasteByNamespace)
    elif result == '否':
        pasteKeys(False, "merge", pasteByNamespace)
    else:
        print("粘贴关键帧已取消。")
        return


def setHiddenAttributeKeys(control, hiddenAttrValues, startFrame):
    """在指定范围内将保存的关键帧数据设置到节点上。

    :param control: str, 带有隐藏可关键帧属性的节点
    :param hiddenAttrValues: int, 关键帧值
    :param startFrame: float, 动画范围起始帧
    :return:
    """
    for time in range(int(hiddenAttrValues["range"] + 1)):
        for index, attr in enumerate(hiddenAttrValues["attributes"]):
            cmds.setKeyframe(f"{control}.{attr}",
                             value=hiddenAttrValues["keys"][time][index], time=time + startFrame)


def pasteKeys(bufferKeys, insertOrMerge="insert", pasteByNamespace=False):
    """从 .anim 文件粘贴关键帧到时间轴

    :return:
    """
    global SELECTED_TXT_FILE
    
    selectedObjs = cmds.ls(selection=True)

    aPlayBackSlider = mel.eval('$tmpVar=$gPlayBackSlider')
    timeSelected = False
    current_Time = cmds.currentTime(query=True)
    selectedRange = (current_Time, current_Time)

    # 获取选定的时间范围
    if cmds.timeControl(aPlayBackSlider, query=True, rangeVisible=True):
        selectedRange = cmds.timeControl(aPlayBackSlider, query=True, rangeArray=True)
        current_Time = selectedRange[0]
        timeSelected = True

    cmds.select(clear=True)

    # 如果没有选择任何对象则报错
    if not selectedObjs:
        OpenMaya.MGlobal.displayError("请选择至少一个对象。")
        return

    selectedPrefixes = []
    # 获取选中角色的命名空间
    for selectedObj in selectedObjs:
        prefix = re.match("^[^:]+", selectedObj)
        if prefix.group() == selectedObj:
            if ':' not in selectedPrefixes:
                selectedPrefixes.append(':')
        elif prefix.group() not in selectedPrefixes:
            selectedPrefixes.append(prefix.group())

    cmds.undoInfo(openChunk=True)

    # 打开文本文件读取之前选中的控件并添加到列表
    controls = []
    nonExistingObjects = []
    previousPrefix = ''
    prefixIndex = 0
    
    # 使用选择的文件路径
    sel_file_path = SELECTED_TXT_FILE
    if not os.path.exists(sel_file_path):
        OpenMaya.MGlobal.displayError(f"文件不存在: {sel_file_path}")
        cmds.undoInfo(closeChunk=True)
        return
    
    # 🔧 获取基础目录
    base_dir = os.path.dirname(sel_file_path)
    print(f"📁 读取 selection.txt: {sel_file_path}")
    print(f"📁 基础目录: {base_dir}")
        
    with open(sel_file_path, 'r') as selFile:
        for line in selFile:
            node = line.split("\n")[0]
            prefix = re.match("^[^:]+", node)
            if pasteByNamespace:
                if previousPrefix and prefix.group() != previousPrefix:
                    prefixIndex += 1

                if selectedPrefixes[prefixIndex] == ':':
                    node = node.replace(f'{prefix.group()}:', '')
                else:
                    node = replacePrefix(node, selectedPrefixes[prefixIndex])

            if cmds.objExists(node) and node in selectedObjs:
                controls.append(node)
            else:
                dupeNode = cmds.createNode('transform', name=f'{node}_临时')
                nonExistingObjects.append(dupeNode)
                controls.append(dupeNode)

            previousPrefix = prefix.group()

        selFile.close()

    # 更新选中的对象列表供后续使用
    selectedObjs = controls[:]

    # 🔧 构建动画文件路径（在同一个目录下）
    anim_file_path = os.path.join(base_dir, 'copyKeys.anim')
    hidden_attrs_path = os.path.join(base_dir, 'hiddenAttrKeys.json')
    
    print(f"📁 动画文件路径: {anim_file_path}")
    print(f"📁 动画文件是否存在: {os.path.exists(anim_file_path)}")

    try:
        # 从 .anim 文件读取关键帧并写入 API 剪贴板
        if not os.path.exists(anim_file_path):
            OpenMaya.MGlobal.displayError(f"动画文件不存在: {anim_file_path}")
            cmds.undoInfo(closeChunk=True)
            return
        
        # 🔧 关键修复：传入文件路径！
        animFileData = ReadAnim.AnimFile(anim_file_path)
        set_api_clipboard.writeToAPIClipboard(animFileData)
        print(f"✅ 已从 {anim_file_path} 读取动画数据")
        
    except Exception as e:
        print(f"❌ 读取动画文件失败: {e}")
        traceback.print_exc()
        cmds.undoInfo(closeChunk=True)
        return

    # 设置时间并选择控件进行粘贴
    cmds.currentTime(current_Time)
    cmds.select(selectedObjs, replace=True)

    # 在范围起始处添加缓冲关键帧
    if bufferKeys:
        cmds.setKeyframe(selectedObjs, insert=True, time=(selectedRange[0] - 1, selectedRange[1]))

    # 如果选择了范围，剪切关键帧并后移
    if timeSelected:
        cmds.keyframe(selectedObjs, edit=True, relative=True, timeChange=(selectedRange[0] - (selectedRange[1] - 1)))

    # 从 API 剪贴板粘贴关键帧（可撤销命令）
    cmds.pasteKey(clipboard="api", copies=1, time=(current_Time, current_Time), option=f"{insertOrMerge}")

    # 设置时间码属性
    try:
        if os.path.exists(hidden_attrs_path):
            with open(hidden_attrs_path) as hiddenAttrsFile:
                hiddenAttrKeys = json.load(hiddenAttrsFile)

            for control, hiddenAttributeCategory in hiddenAttrKeys.items():
                for category, keyInfo in hiddenAttributeCategory.items():
                    if keyInfo["keys"]:
                        setHiddenAttributeKeys(control, keyInfo, selectedRange[0])
            print(f"✅ 已恢复隐藏属性数据: {hidden_attrs_path}")
        else:
            cmds.warning(f"时间码属性文件不存在: {hidden_attrs_path}，跳过恢复。")
    except IOError as e:
        cmds.warning(f"读取时间码属性文件失败: {e}")

    # 删除为不存在的控件创建的临时变换节点
    if len(nonExistingObjects) > 0:
        cmds.delete(nonExistingObjects)
        print(f"✅ 已删除 {len(nonExistingObjects)} 个临时节点")

    cmds.undoInfo(closeChunk=True)
    print("✅ 粘贴完成！")


def getHiddenAttributeValues(node, nonCBKeyableFloats, startFrame, endFrame):
    """遍历非通道盒可关键帧浮点属性，使用正则表达式检查特定属性。
       收集与搜索字符串匹配的属性的关键帧信息。

    :param node: str, 带有隐藏可关键帧属性的节点
    :param nonCBKeyableFloats: list, 属性名称列表
    :param startFrame: float, 动画范围起始帧
    :param endFrame: float, 动画范围结束帧
    :return: dict, 包含类别、属性和匹配的隐藏可关键帧属性的关键帧信息
    """
    keyableHiddenAttrValues = dict()
    for category, attributeSearchInfo in list(HIDDEN_ATTRIBUTES_DATA.items()):
        matchingAttrs = [attr for attr in nonCBKeyableFloats if re.match(attributeSearchInfo["regex"], attr)]
        if matchingAttrs:
            keys = attributeSearchInfo["function"](startFrame, endFrame, node, matchingAttrs)
            keyableHiddenAttrValues[node] = {
                category: {"attributes": matchingAttrs, "keys": keys, "range": endFrame - startFrame}}

    return keyableHiddenAttrValues


def getTimecodeAttrKeys(*args):
    """如果时间码属性已被关键帧化，则获取其关键帧值。

    :param startFrame: float, 动画范围起始帧
    :param endFrame: float, 动画范围结束帧
    :param node: str, 带时间码属性的节点
    :param timecodeAttrs: list, 时间码属性列表
    :return:
    """
    startFrame, endFrame, node, timecodeAttrs = args[0]
    timecodeKeys = list()
    keyedTimecodeAttrs = False

    for attr in timecodeAttrs:
        if attr in anim.getAnimCurvesFromNode(node):
            keyedTimecodeAttrs = True

    if keyedTimecodeAttrs:
        for i in range(int(startFrame), int(endFrame) + 1):
            timecodeKeys.append(
                [cmds.getAttr(f"{node}.{attr}", time=i) for attr in timecodeAttrs])

    return timecodeKeys


def copyRangeKeys(startFrame, endFrame):
    """将选中的控件和属性记录到文本文件，
       创建 JSON 文件记录隐藏可关键帧属性，
       并将动画导出到用户选择的目录。

    :param startFrame: float, 动画范围起始帧
    :param endFrame: float, 动画范围结束帧
    :return:
    """
    global SELECTED_SAVE_DIR
    
    # 弹出文件夹选择对话框
    if not select_save_directory():
        OpenMaya.MGlobal.displayWarning("未选择保存目录，将使用默认路径。")
    
    # 确保目录存在
    if not os.path.exists(SELECTED_SAVE_DIR):
        os.makedirs(SELECTED_SAVE_DIR)
        print(f"✅ 已创建目录: {SELECTED_SAVE_DIR}")
    
    # 初始化用于粘贴的变量
    keyableHiddenAttrValues = dict()
    selectedObjs = cmds.ls(selection=True)
    keyedObjs = []
    nonKeyedObjs = []
    if len(selectedObjs) > 0:
        for obj in selectedObjs:
            if cmds.keyframe(obj, query=True, time=(startFrame, endFrame), keyframeCount=True) != 0:
                keyedObjs.append(obj)
            else:
                nonKeyedObjs.append(obj)
    else:
        OpenMaya.MGlobal.displayError("请至少选择一个对象来复制动画。")
        return

    # 将选中的控件写入文本文件
    if len(keyedObjs) > 0:
        sel_file_path = os.path.join(SELECTED_SAVE_DIR, 'selection.txt')
        with open(sel_file_path, 'w') as selFile:
            for obj in keyedObjs:
                selFile.write(obj + "\n")
            selFile.close()
        print(f"✅ 已保存控件列表到: {sel_file_path}")
        
        cmds.undoInfo(openChunk=True)

        cmds.select(clear=True)
        objAttrsDict = dict()
        for obj in keyedObjs:
            keyableAttrs = cmds.listAttr(obj, keyable=True)
            objAttrsDict[obj] = keyableAttrs

            # 基于搜索字符串保存隐藏可关键帧属性
            hiddenAttrs = cmds.listAttr(obj, userDefined=True, settable=True, output=True)
            if hiddenAttrs:
                nonCBKeyableFloats = [
                    attr for attr in hiddenAttrs if cmds.getAttr("{0}.{1}".format(obj, attr), type=True) == "long"]

                if nonCBKeyableFloats:
                    hiddenAttrInfo = getHiddenAttributeValues(obj, nonCBKeyableFloats, startFrame, endFrame)
                    keyableHiddenAttrValues.update(hiddenAttrInfo)

        # 在范围起始/结束处插入关键帧
        for control, attrs in list(objAttrsDict.items()):
            if attrs is None:
                continue

            for attr in attrs:
                if not cmds.keyframe(f"{control}.{attr}", q=True, tc=True, time=(startFrame, endFrame)):
                    cmds.setKeyframe(control, attribute=attr, time=(startFrame, endFrame))
                else:
                    cmds.setKeyframe(control, attribute=attr, insert=True, time=(startFrame, endFrame))

        # 导出数据
        cmds.select(keyedObjs, replace=True)

        animFileOptions = ";options=keys;hierarchy=none;nodeNames=1;controlPoints=0;shapes=0;helpPictures=0;"
        animFileOptions += "useChannelBox=0;copyKeyCmd=-animation objects -time >"

        try:
            # 写入时间码关键帧的 JSON 文件
            timecode_path = os.path.join(SELECTED_SAVE_DIR, "hiddenAttrKeys.json")
            with open(timecode_path, "w") as timecodeFile:
                json.dump(keyableHiddenAttrValues, timecodeFile, indent=4)
            print(f"✅ 已保存隐藏属性数据到: {timecode_path}")

            # 写入 .anim 文件
            anim_path = os.path.join(SELECTED_SAVE_DIR, "copyKeys.anim")
            cmds.file(
                anim_path,
                exportSelected=True,
                force=True,
                type="animExport",
                options=f"precision=8;intValue=17;nodeNames=0;verboseUnits=0;whichRange=2;range={startFrame}:{endFrame}{animFileOptions}{startFrame}:{endFrame}> -float >{startFrame}:{endFrame}> -option keys -hierarchy none -controlPoints 0 -shape 0 ")
            print(f"✅ 已导出动画文件到: {anim_path}")

            # Maya2019 animExport 写入完整 dagPath 名称的临时修复
            if MAYA_VERSION == 2019:
                convertLongToShortPaths(anim_path)
                print("✅ 已应用 Maya2019 路径修复")

            cmds.undoInfo(closeChunk=True)
            cmds.undo()
            if len(nonKeyedObjs) > 0:
                nonKeyed = '\n'.join(nonKeyedObjs)
                print(f"⚠️ 以下对象在选定范围内没有关键帧，未导出：\n{nonKeyed}")

            selectedAnimLayer = anim_layers.getAnimLayersList("selected")
            if selectedAnimLayer:
                cmds.warning(
                    f"关键帧 {startFrame} 到 {endFrame} 已在 {selectedAnimLayer[0]} 动画层上复制。")
            else:
                cmds.warning(f"关键帧 {startFrame} 到 {endFrame} 已复制。")

        except Exception:
            cmds.undoInfo(closeChunk=True)
            cmds.undo()
            message = f"在范围 {startFrame} 到 {endFrame} 内未找到动画曲线。"
            OpenMaya.MGlobal.displayError(message)
            return
    else:
        OpenMaya.MGlobal.displayError(
            "选中的对象必须在选定范围内至少有一个关键帧才能复制动画。")
        return


def copyKeys():
    """从时间轴上选定的范围复制关键帧

    :return:
    """
    # 获取时间轴上选定的范围
    aPlayBackSlider = mel.eval('$tmpVar=$gPlayBackSlider')
    if cmds.timeControl(aPlayBackSlider, q=True, rv=True):
        selectedRange = cmds.timeControl(aPlayBackSlider, q=True, ra=True)
    else:
        OpenMaya.MGlobal.displayError("请先在时间轴上高亮选择要复制的范围。")
        return

    copyRangeKeys(selectedRange[0], selectedRange[1] - 1)
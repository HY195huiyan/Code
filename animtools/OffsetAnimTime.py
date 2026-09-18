import maya.cmds as cmds
import maya.mel as mel


def run():
    """
    创建偏移动画时间的UI窗口
    """
    win = "offsetAnimTimeWin"
    if cmds.window(win, exists=True):
        cmds.deleteUI(win)
    
    cmds.window(win, title="偏移动画时间", toolbox=True, widthHeight=(280, 200))
    
    # 使用垂直布局
    cmds.columnLayout(adj=True, rowSpacing=5)
    
    # 第一行：帧数输入
    cmds.rowLayout(numberOfColumns=2, adj=2)
    cmds.text(label="帧数: ", align="left")
    cmds.textField("txtOffsetVal", 
                   alwaysInvokeEnterCommandOnReturn=True,
                   enterCommand="doOffsetAnimTime(float(cmds.textField('txtOffsetVal', query=True, text=True)))")
    cmds.setParent("..")
    
    cmds.separator(style="in")
    
    # 单选按钮组
    cmds.text(label="选择范围:", align="left")
    cmds.radioCollection("radObjs")
    cmds.rowLayout(numberOfColumns=3)
    cmds.radioButton("radAll", label="所有物体", select=True)
    cmds.radioButton("radSelected", label="已选物体")
    cmds.radioButton("radUnselected", label="未选物体")
    cmds.setParent("..")
    
    cmds.separator(style="in")
    
    # 复选框
    cmds.rowLayout(numberOfColumns=2)
    cmds.checkBox("chkAudio", label="包含音频", value=True)
    cmds.checkBox("chkDeleteKeys", label="删除重叠关键帧", value=False)
    cmds.setParent("..")
    
    cmds.separator(style="in")
    
    # 按钮
    cmds.rowLayout(numberOfColumns=2, columnWidth2=(135, 135), adjustableColumn=2, columnAttach=[(1, 'both', 2), (2, 'both', 2)])
    cmds.button(label="向后偏移", command=lambda x: offsetAnimTimeFromUI("+"))
    cmds.button(label="向前偏移", command=lambda x: offsetAnimTimeFromUI("-"))
    cmds.setParent("..")
    
    cmds.showWindow(win)


def offsetAnimTimeFromUI(operand):
    """
    从UI获取参数并执行偏移
    """
    time = float(cmds.textField("txtOffsetVal", query=True, text=True))
    sel_button = cmds.radioCollection("radObjs", query=True, select=True)
    audio = cmds.checkBox("chkAudio", query=True, value=True)
    delete_keys = cmds.checkBox("chkDeleteKeys", query=True, value=True)
    
    selected = 0
    if sel_button == "radSelected":
        selected = 1
    elif sel_button == "radUnselected":
        selected = 2
    
    if operand == "-":
        time = -time
    
    doOffsetAnimTime(time, selected, audio, delete_keys)


def getAnimCurvesFromObject(obj):
    """
    获取指定对象的所有动画曲线
    """
    anim_curves = []
    
    # 方法1：获取物体所有属性上的动画曲线连接
    connections = cmds.listConnections(obj, source=True, destination=False, 
                                        scn=True, plugs=True, type="animCurve") or []
    
    for conn in connections:
        if cmds.nodeType(conn) in ["animCurveTL", "animCurveTA", "animCurveTU"]:
            if conn not in anim_curves:
                anim_curves.append(conn)
    
    # 方法2：如果方法1没找到，尝试查找物体子节点上的动画曲线
    if not anim_curves:
        children = cmds.listRelatives(obj, children=True, fullPath=True) or []
        for child in children:
            child_curves = cmds.listConnections(child, source=True, destination=False, 
                                                 scn=True, plugs=True, type="animCurve") or []
            for conn in child_curves:
                if cmds.nodeType(conn) in ["animCurveTL", "animCurveTA", "animCurveTU"]:
                    if conn not in anim_curves:
                        anim_curves.append(conn)
    
    # 方法3：查找物体所有可动画属性上的曲线
    all_attrs = cmds.listAttr(obj, keyable=True, settable=True) or []
    
    for attr in all_attrs:
        full_attr = obj + "." + attr
        conns = cmds.listConnections(full_attr, source=True, destination=False, 
                                      type="animCurve") or []
        for conn in conns:
            if cmds.nodeType(conn) in ["animCurveTL", "animCurveTA", "animCurveTU"]:
                if conn not in anim_curves:
                    anim_curves.append(conn)
    
    # 方法4：使用 listHistory 获取所有历史节点，然后筛选动画曲线
    if not anim_curves:
        try:
            history = cmds.listHistory(obj, pruneDagObjects=True) or []
            for node in history:
                if cmds.nodeType(node) in ["animCurveTL", "animCurveTA", "animCurveTU"]:
                    if node not in anim_curves:
                        anim_curves.append(node)
        except:
            pass
    
    return anim_curves


def getAnimCurvesFromObjects(objs):
    """
    从对象列表获取所有动画曲线
    """
    all_curves = []
    for obj in objs:
        curves = getAnimCurvesFromObject(obj)
        if curves:
            all_curves.extend(curves)
    
    # 去重
    all_curves = list(set(all_curves))
    return all_curves


def doOffsetAnimTime(offset, selected, include_audio, delete_overlapping_keys):
    """
    执行偏移动画时间
    """
    curves = []
    anim_curves = []
    locked_curves = []
    
    current_time = cmds.currentTime(query=True)
    
    # 根据选择方式获取动画曲线
    if selected == 1:  # 已选物体
        objs = cmds.ls(selection=True)
        if not objs:
            print("警告：没有已选的物体！")
            return
        anim_curves = getAnimCurvesFromObjects(objs)
    
    elif selected == 2:  # 未选物体
        all_curves = cmds.ls(type=["animCurveTL", "animCurveTA", "animCurveTU"])
        objs = cmds.ls(selection=True)
        unselect = []
        if objs:
            unselect = getAnimCurvesFromObjects(objs)
        anim_curves = [c for c in all_curves if c not in unselect]
    
    else:  # 全部动画
        anim_curves = cmds.ls(type=["animCurveTL", "animCurveTA", "animCurveTU"])
    
    if not anim_curves:
        print("警告：没有找到任何动画曲线！")
        return
    
    # 检查曲线是否被引用或锁定
    for curve in anim_curves:
        if not cmds.referenceQuery(curve, isNodeReferenced=True):
            curves.append(curve)
            
            # 检查并解锁曲线
            try:
                if cmds.getAttr(curve + ".keyTimeValue", lock=True):
                    cmds.setAttr(curve + ".keyTimeValue", lock=False)
                    locked_curves.append(curve)
            except:
                pass
    
    if not curves:
        print("警告：没有可编辑的曲线（可能被锁定或引用）")
        return
    
    # 使用MEL命令执行偏移
    if offset < 0 and delete_overlapping_keys:
        for curve in curves:
            try:
                next_key = cmds.findKeyframe(curve, which="next", time=(current_time,))
                previous_key = cmds.findKeyframe(curve, which="previous", time=(current_time + 1,))
                
                if abs(offset) > (next_key - previous_key):
                    new_time = previous_key - offset + 1
                    value = cmds.getAttr(curve + ".output", time=(new_time,))
                    cmds.setKeyframe(curve, time=(new_time,), value=value)
                    cmds.cutKey(curve, clear=True, time=(current_time + 1, current_time - offset), 
                               index=1, option="keys")
            except Exception as e:
                print("处理曲线时出错: {0}".format(str(e)))
        
        for curve in curves:
            mel_cmd = 'keyframe -e -iub true -r -o over -tc {0} -t "{1}:" {2};'.format(
                offset, current_time + 1, curve)
            mel.eval(mel_cmd)
    else:
        curves_str = " ".join(curves)
        mel_cmd = 'keyframe -e -iub true -r -o over -tc {0} -t "{1}:" {2};'.format(
            offset, current_time + 1, curves_str)
        mel.eval(mel_cmd)
    
    # 偏移音频
    if include_audio:
        audio_list = cmds.ls(type="audio")
        for audio in audio_list:
            try:
                ao = cmds.getAttr(audio + ".offset")
                if ao >= current_time:
                    cmds.setAttr(audio + ".offset", ao + offset)
            except:
                pass
    
    # 重新锁定曲线
    for curve in locked_curves:
        try:
            cmds.setAttr(curve + ".keyTimeValue", lock=True)
        except:
            pass
    
    print("从第 {0} 帧开始的所有关键帧和音频已偏移 {1} 帧。".format(current_time, offset))


if __name__ == "__main__":
    run()

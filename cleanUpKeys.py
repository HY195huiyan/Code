import maya.cmds as cmds

WINDOW_NAME = "cleanUpKeysWin"
CLEANER_NODE = "animCleanupNode"


def get_cleaner_node():
    """获取或创建标记节点"""
    if not cmds.objExists(CLEANER_NODE):
        cmds.createNode("transform", name=CLEANER_NODE, skipSelect=True)
        
        # 锁定所有变换属性
        transform_attrs = [".tx", ".ty", ".tz", ".rx", ".ry", ".rz", ".sx", ".sy", ".sz", ".v"]
        for attr in transform_attrs:
            cmds.setAttr(CLEANER_NODE + attr, lock=True, keyable=False)
        
        # 添加自定义标记属性
        cmds.addAttr(CLEANER_NODE, longName="markedTime", attributeType="bool", defaultValue=True, keyable=True, shortName="mt")
    
    return CLEANER_NODE


def is_obj_on_anim_layer(obj, anim_layer):
    """检查对象是否在指定的动画层上"""
    try:
        affected_layers = cmds.animLayer(query=True, affectedLayers=True) or []
        return obj in affected_layers
    except:
        return False


def add_selected_to_cleanup_list():
    """将选中的物体添加到清理列表"""
    if not cmds.textScrollList(WINDOW_NAME + "_objList", exists=True):
        return
    
    current_items = cmds.textScrollList(WINDOW_NAME + "_objList", query=True, allItems=True) or []
    selected = cmds.ls(selection=True, type="transform") or []
    
    # 过滤掉标记节点本身
    selected = [obj for obj in selected if obj != get_cleaner_node()]
    
    # 只添加尚未在列表中的对象
    new_items = list(set(current_items + selected))
    new_items = sorted(new_items)
    
    # 更新列表
    cmds.textScrollList(WINDOW_NAME + "_objList", edit=True, removeAll=True)
    if new_items:
        cmds.textScrollList(WINDOW_NAME + "_objList", edit=True, append=new_items)


def remove_from_cleanup_list():
    """从清理列表中移除选中的项"""
    if not cmds.textScrollList(WINDOW_NAME + "_objList", exists=True):
        return
    
    selected_indices = cmds.textScrollList(WINDOW_NAME + "_objList", query=True, selectIndexedItem=True) or []
    for idx in sorted(selected_indices, reverse=True):
        cmds.textScrollList(WINDOW_NAME + "_objList", edit=True, removeIndexedItem=idx)


def clear_cleanup_list():
    """清空清理列表"""
    if cmds.textScrollList(WINDOW_NAME + "_objList", exists=True):
        cmds.textScrollList(WINDOW_NAME + "_objList", edit=True, removeAll=True)


def get_time_range():
    """获取场景的时间范围"""
    min_time = cmds.playbackOptions(query=True, minTime=True)
    max_time = cmds.playbackOptions(query=True, maxTime=True)
    return [min_time, max_time]


def set_key_on_cleaner_node():
    """在当前时间给标记节点设置关键帧"""
    cleaner = get_cleaner_node()
    current_time = cmds.currentTime(query=True)
    
    # 保存当前选择
    original_selection = cmds.ls(selection=True)
    
    # 选择标记节点
    cmds.select(cleaner, replace=True)
    
    # 检查动画层
    try:
        all_layers = cmds.ls(type="animLayer") or []
        for layer in all_layers:
            if cmds.animLayer(layer, query=True, selected=True):
                if not is_obj_on_anim_layer(cleaner, layer):
                    cmds.animLayer(layer, edit=True, additiveSelectionOverride=True)
                break
    except:
        pass
    
    # 设置关键帧
    cmds.setKeyframe(cleaner, time=(current_time,))
    
    # 恢复选择
    if original_selection:
        cmds.select(original_selection, replace=True)


def remove_key_from_cleaner_node():
    """移除标记节点在当前时间的关键帧"""
    cleaner = get_cleaner_node()
    current_time = cmds.currentTime(query=True)
    cmds.cutKey(cleaner, time=(current_time, current_time))


def key_every_nth_frame(nth):
    """每隔N帧设置一个标记关键帧"""
    if nth <= 0:
        cmds.warning('您输入的"Nth"值必须大于0')
        return
    
    cleaner = get_cleaner_node()
    time_range = get_time_range()
    
    # 保存当前选择
    original_selection = cmds.ls(selection=True)
    
    # 选择标记节点
    cmds.select(cleaner, replace=True)
    
    # 检查动画层
    try:
        all_layers = cmds.ls(type="animLayer") or []
        for layer in all_layers:
            if cmds.animLayer(layer, query=True, selected=True):
                if not is_obj_on_anim_layer(cleaner, layer):
                    cmds.animLayer(layer, edit=True, additiveSelectionOverride=True)
                break
    except:
        pass
    
    # 每隔N帧设置关键帧
    for t in range(int(time_range[0]), int(time_range[1]) + 1, nth):
        cmds.setKeyframe(cleaner, time=(t,))
    
    # 恢复选择
    if original_selection:
        cmds.select(original_selection, replace=True)


def clean_up_keys_proc():
    """执行清理操作"""
    cleaner = get_cleaner_node()
    
    # 获取标记节点上的所有关键帧时间
    keys = cmds.keyframe(cleaner, query=True, timeChange=True) or []
    if not keys:
        cmds.error("标记节点上没有设置关键帧，请先设置要保留的帧")
        return
    
    # 获取列表中的对象
    items = cmds.textScrollList(WINDOW_NAME + "_objList", query=True, allItems=True) or []
    if not items:
        cmds.error("清理列表为空，请先添加要清理的对象")
        return
    
    # 过滤掉不存在的对象
    valid_objects = [obj for obj in items if cmds.objExists(obj)]
    if not valid_objects:
        cmds.error("列表中的对象都不存在")
        return
    
    time_range = get_time_range()
    
    # 保存评估模式并设置为DG模式（避免Maya 2018崩溃）
    eval_mode = cmds.evaluationManager(query=True, mode=True)[0]
    cmds.evaluationManager(mode="off")
    
    try:
        # 在标记的时间点上插入关键帧
        for obj in valid_objects:
            for key in keys:
                cmds.setKeyframe(obj, insert=True, time=(key,))
        
        # 删除标记时间之外的所有关键帧
        for obj in valid_objects:
            # 获取对象的所有关键帧时间
            all_keys = cmds.keyframe(obj, query=True, timeChange=True) or []
            
            # 找出要删除的关键帧（不在保留列表中的）
            keys_to_delete = []
            for k in all_keys:
                # 检查这个关键帧是否在保留列表中（允许浮点数误差）
                keep = False
                for keep_key in keys:
                    if abs(k - keep_key) < 0.001:
                        keep = True
                        break
                if not keep:
                    keys_to_delete.append(k)
            
            # 删除不在保留列表中的关键帧
            for k in keys_to_delete:
                cmds.cutKey(obj, time=(k, k))
        
        # 清除标记节点上的关键帧
        cmds.cutKey(cleaner)
        
        # 刷新节点
        for obj in valid_objects:
            cmds.dgdirty(obj)
        
        # 选择清理后的对象
        cmds.select(valid_objects, replace=True)
        
        cmds.warning("清理完成！保留了 {} 个关键帧位置".format(len(keys)))
        
    finally:
        # 恢复评估模式
        cmds.evaluationManager(mode=eval_mode)


def on_list_select():
    """列表选择回调"""
    if not cmds.textScrollList(WINDOW_NAME + "_objList", exists=True):
        return
    
    selected = cmds.textScrollList(WINDOW_NAME + "_objList", query=True, selectItem=True) or []
    if selected:
        cmds.select(selected, replace=True)
        cleaner = get_cleaner_node()
        if cmds.objExists(cleaner):
            cmds.select(cleaner, add=True)


def show_ui():
    """显示UI窗口"""
    cleaner = get_cleaner_node()
    
    # 如果窗口已存在，则关闭重建
    if cmds.window(WINDOW_NAME, exists=True):
        cmds.deleteUI(WINDOW_NAME)
    
    # 创建窗口
    window_width = 380
    window = cmds.window(WINDOW_NAME, title="Clean up Keys", toolbox=True, widthHeight=(window_width, 400), retain=False)
    
    # 使用columnLayout作为主布局
    main_layout = cmds.columnLayout(adjustableColumn=True, rowSpacing=5, columnAttach=('both', 10))
    
    # 标签
    cmds.text(label="Objects:", align="left", parent=main_layout)
    
    # 对象列表
    cmds.textScrollList(
        WINDOW_NAME + "_objList",
        allowMultiSelection=True,
        selectCommand=on_list_select,
        height=120,
        parent=main_layout
    )
    
    # ========== 第一行：3个等宽按钮 ==========
    spacing = 6
    btn_width = (window_width - 20 - spacing * 2) / 3
    
    # 使用 gridLayout 实现等宽按钮，但去掉间距控制
    cmds.rowLayout(numberOfColumns=3, parent=main_layout)
    cmds.button(label="添加选中项", width=btn_width, command=lambda x: add_selected_to_cleanup_list(), align="center")
    cmds.separator(width=spacing, height=1, style="none", parent=main_layout)  # 使用 separator 作为间距
    cmds.button(label="删除选中项", width=btn_width, command=lambda x: remove_from_cleanup_list(), align="center")
    cmds.separator(width=spacing, height=1, style="none", parent=main_layout)  # 使用 separator 作为间距
    cmds.button(label="清除列表", width=btn_width, command=lambda x: clear_cleanup_list(), align="center")
    cmds.setParent('..')
    
    # 分隔线
    cmds.separator(style="in", height=8, parent=main_layout)
    
    # ========== 第二行：2个等宽按钮 ==========
    spacing2 = 8
    btn_width2 = (window_width - 20 - spacing2) / 2
    
    cmds.rowLayout(numberOfColumns=2, parent=main_layout)
    cmds.button(label="添加关键帧", width=btn_width2, command=lambda x: set_key_on_cleaner_node(), height=40, align="center")
    cmds.separator(width=spacing2, height=1, style="none", parent=main_layout)  # 使用 separator 作为间距
    cmds.button(label="删除关键帧", width=btn_width2, command=lambda x: remove_key_from_cleaner_node(), height=40, align="center")
    cmds.setParent('..')
    
    # 分隔线
    cmds.separator(style="in", height=8, parent=main_layout)
    
    # ========== 第三行：输入框 + 按钮 ==========
    cmds.rowLayout(numberOfColumns=2, parent=main_layout)
    cmds.textField("txt_nth", text="5", width=60)
    cmds.separator(width=6, height=1, style="none", parent=main_layout)  # 使用 separator 作为间距
    cmds.button(label="给每N帧添加关键帧", 
                width=window_width - 20 - 60 - 6,
                command=lambda x: key_every_nth_frame(int(cmds.textField("txt_nth", query=True, text=True))), 
                align="center")
    cmds.setParent('..')
    
    # 分隔线
    cmds.separator(style="in", height=8, parent=main_layout)
    
    # ========== 第四行：占满整行的清理按钮 ==========
    cmds.button(
        label="清理", 
        command=lambda x: clean_up_keys_proc(), 
        height=40, 
        backgroundColor=[0.3, 0.6, 0.3],
        align="center",
        parent=main_layout
    )
    
    # 显示窗口
    cmds.showWindow(window)
    
    # 自动将当前选择添加到列表
    add_selected_to_cleanup_list()
    
    # 选择标记节点
    if cmds.objExists(cleaner):
        cmds.select(cleaner, add=True)
    
    # 清理回调：删除标记节点
    def on_window_close():
        if cmds.objExists(cleaner):
            cmds.delete(cleaner)
    
    cmds.scriptJob(uiDeleted=[WINDOW_NAME, on_window_close], runOnce=True)


if __name__ == "__main__":
    show_ui()
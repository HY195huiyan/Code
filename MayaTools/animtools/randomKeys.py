# -*- coding: utf-8 -*-

import maya.cmds as cmds
import maya.mel as mel
import random

# ============================================
# UI 部分
# ============================================

def random_keys_ui():
    """创建随机关键帧工具的UI窗口"""
    
    window_name = "randomKeysWindow"
    
    # 如果窗口已存在，先关闭
    if cmds.window(window_name, exists=True):
        cmds.deleteUI(window_name)
    
    # 获取当前播放范围
    start_frame = cmds.playbackOptions(q=True, min=True)
    end_frame = cmds.playbackOptions(q=True, max=True)
    
    # 创建窗口
    window = cmds.window(
        window_name,
        title="随机关键帧工具",
        widthHeight=(400, 450),
        sizeable=True
    )
    
    # 主布局
    main_layout = cmds.columnLayout(
        columnAttach=('both', 5),
        columnOffset=('both', 5),
        rowSpacing=0,
        columnWidth=380
    )
    
    # --- 时间范围 ---
    cmds.rowLayout(numberOfColumns=2, columnWidth2=(200, 160), columnAttach2=('right', 'left'))
    cmds.text(label="起始帧：", align='right')
    start_field = cmds.textField(text=str(int(start_frame)), annotation="设置随机关键帧的开始时间")
    cmds.setParent('..')
    
    cmds.rowLayout(numberOfColumns=2, columnWidth2=(200, 160), columnAttach2=('right', 'left'))
    cmds.text(label="结束帧：", align='right')
    end_field = cmds.textField(text=str(int(end_frame)), annotation="设置随机关键帧的结束时间")
    cmds.setParent('..')
    
    cmds.separator(height=10, style='in')
    
    # --- 新增关键帧选项 ---
    cmds.rowLayout(numberOfColumns=2, columnWidth2=(200, 160), columnAttach2=('right', 'left'))
    cmds.text(label="新增关键帧：", align='right')
    add_keys_check = cmds.checkBox(
        label="",
        value=True,
        annotation="勾选：在时间范围内新增关键帧\n不勾选：只修改现有关键帧的值",
        changeCommand=lambda x: toggle_interval_fields(x, min_interval_field, max_interval_field)
    )
    cmds.setParent('..')
    
    cmds.rowLayout(numberOfColumns=2, columnWidth2=(200, 160), columnAttach2=('right', 'left'))
    cmds.text(label="最小间隔：", align='right')
    min_interval_field = cmds.textField(text="1", enable=True, annotation="新增关键帧的最小帧间隔")
    cmds.setParent('..')
    
    cmds.rowLayout(numberOfColumns=2, columnWidth2=(200, 160), columnAttach2=('right', 'left'))
    cmds.text(label="最大间隔：", align='right')
    max_interval_field = cmds.textField(text="5", enable=True, annotation="新增关键帧的最大帧间隔")
    cmds.setParent('..')
    
    cmds.separator(height=10, style='in')
    
    # --- 数值范围 ---
    cmds.rowLayout(numberOfColumns=2, columnWidth2=(200, 160), columnAttach2=('right', 'left'))
    cmds.text(label="最小值：", align='right')
    min_val_field = cmds.textField(text="-5", annotation="随机值的最小范围")
    cmds.setParent('..')
    
    cmds.rowLayout(numberOfColumns=2, columnWidth2=(200, 160), columnAttach2=('right', 'left'))
    cmds.text(label="最大值：", align='right')
    max_val_field = cmds.textField(text="5", annotation="随机值的最大范围")
    cmds.setParent('..')
    
    cmds.rowLayout(numberOfColumns=2, columnWidth2=(200, 160), columnAttach2=('right', 'left'))
    cmds.text(label="相对模式：", align='right')
    relative_check = cmds.checkBox(
        label="",
        value=False,
        annotation="勾选：随机值会叠加到当前值上\n不勾选：直接替换为随机值（绝对值）"
    )
    cmds.setParent('..')
    
    cmds.separator(height=10, style='in')
    
    # --- 保持帧选项 ---
    cmds.rowLayout(numberOfColumns=2, columnWidth2=(200, 160), columnAttach2=('right', 'left'))
    cmds.text(label="保持每两帧：", align='right')
    hold_check = cmds.checkBox(
        label="",
        value=False,
        annotation="勾选：每两个关键帧的值相同，产生阶梯状效果"
    )
    cmds.setParent('..')
    
    cmds.separator(height=10, style='in')
    
    # --- 按钮 ---
    cmds.rowLayout(numberOfColumns=2, columnWidth2=(180, 180), columnAttach2=('both', 'both'))
    cmds.button(
        label="执行",
        command=lambda x: execute_random_keys(
            start_field, end_field, min_val_field, max_val_field,
            add_keys_check, min_interval_field, max_interval_field,
            relative_check, hold_check
        ),
        annotation="执行随机关键帧操作"
    )
    cmds.button(
        label="关闭",
        command=lambda x: cmds.deleteUI(window),
        annotation="关闭窗口"
    )
    cmds.setParent('..')
    
    cmds.setParent('..')
    
    # 显示窗口
    cmds.showWindow(window)


def toggle_interval_fields(checked, min_field, max_field):
    """切换间隔字段的启用状态"""
    cmds.textField(min_field, edit=True, enable=checked)
    cmds.textField(max_field, edit=True, enable=checked)


# ============================================
# 核心功能部分
# ============================================

def execute_random_keys(
    start_field, end_field, min_val_field, max_val_field,
    add_keys_check, min_interval_field, max_interval_field,
    relative_check, hold_check
):
    """执行随机关键帧的核心逻辑"""
    
    start_time = float(cmds.textField(start_field, q=True, text=True))
    end_time = float(cmds.textField(end_field, q=True, text=True))
    min_val = float(cmds.textField(min_val_field, q=True, text=True))
    max_val = float(cmds.textField(max_val_field, q=True, text=True))
    add_keys = cmds.checkBox(add_keys_check, q=True, value=True)
    min_interval = float(cmds.textField(min_interval_field, q=True, text=True))
    max_interval = float(cmds.textField(max_interval_field, q=True, text=True))
    relative = cmds.checkBox(relative_check, q=True, value=True)
    add_hold = cmds.checkBox(hold_check, q=True, value=True)
    
    random_keys_process(
        start_time, end_time, min_val, max_val,
        add_keys, min_interval, max_interval,
        relative, add_hold
    )


def random_keys_process(
    start_time, end_time, min_val, max_val,
    add_keys, min_interval, max_interval,
    relative, add_hold
):
    """随机关键帧核心处理函数"""
    
    objects = cmds.ls(sl=True)
    if not objects:
        cmds.error("请至少选择一个物体！")
        return
    
    channels = get_selected_channels()
    if not channels:
        cmds.warning("请在通道盒中选择至少一个属性！")
        return
    
    auto_key_state = cmds.autoKeyframe(q=True, state=True)
    cmds.autoKeyframe(state=0)
    
    try:
        random_keys_core(
            start_time, end_time, min_val, max_val,
            add_keys, min_interval, max_interval,
            relative, add_hold, channels
        )
        print("随机关键帧完成！")
    except Exception as e:
        print("执行出错：{}".format(str(e)))
        import traceback
        traceback.print_exc()
    finally:
        cmds.autoKeyframe(state=auto_key_state)


def get_selected_channels():
    """获取通道盒中选中的属性列表"""
    channels = []
    
    main_attrs = cmds.channelBox('mainChannelBox', q=True, selectedMainAttributes=True) or []
    shape_attrs = cmds.channelBox('mainChannelBox', q=True, selectedShapeAttributes=True) or []
    history_attrs = cmds.channelBox('mainChannelBox', q=True, selectedHistoryAttributes=True) or []
    output_attrs = cmds.channelBox('mainChannelBox', q=True, selectedOutputAttributes=True) or []
    
    main_nodes = cmds.channelBox('mainChannelBox', q=True, mainObjectList=True) or []
    shape_nodes = cmds.channelBox('mainChannelBox', q=True, shapeObjectList=True) or []
    history_nodes = cmds.channelBox('mainChannelBox', q=True, historyObjectList=True) or []
    output_nodes = cmds.channelBox('mainChannelBox', q=True, outputObjectList=True) or []
    
    for node in main_nodes:
        for attr in main_attrs:
            obj_attr = "{}.{}".format(node, attr)
            if cmds.objExists(obj_attr):
                channels.append(obj_attr)
    
    for node in shape_nodes:
        for attr in shape_attrs:
            obj_attr = "{}.{}".format(node, attr)
            if cmds.objExists(obj_attr):
                channels.append(obj_attr)
    
    for node in history_nodes:
        for attr in history_attrs:
            obj_attr = "{}.{}".format(node, attr)
            if cmds.objExists(obj_attr):
                channels.append(obj_attr)
    
    for node in output_nodes:
        for attr in output_attrs:
            obj_attr = "{}.{}".format(node, attr)
            if cmds.objExists(obj_attr):
                channels.append(obj_attr)
    
    return channels


def get_attr_at_time(channel, time):
    # 保存当前时间
    current_time = cmds.currentTime(q=True)
    
    # 跳转到目标时间
    cmds.currentTime(time)
    
    # 获取属性值
    value = cmds.getAttr(channel)
    
    # 恢复当前时间
    cmds.currentTime(current_time)
    
    return value


def get_next_keyframe(channel, time):
    # 使用 MEL 命令来查找下一个关键帧（更可靠）
    # 注意：findKeyframe 的 time 参数期望的是 (time, time) 格式
    result = cmds.findKeyframe(channel, time=(time,), which='next')
    
    # findKeyframe 返回 float，如果没有找到则返回 None
    if result is None:
        return None
    
    return float(result)


def set_keyframe_safe(channel, time, value):
    # 确保 time 是浮点数
    time_float = float(time)
    
    # 设置关键帧
    cmds.setKeyframe(channel, t=time_float, v=float(value))


def random_keys_core(
    start_time, end_time, min_val, max_val,
    add_keys, min_interval, max_interval,
    relative, add_hold, channels
):
    
    
    channel_count = len(channels)
    
    # 确保间隔值有效
    min_interval = abs(min_interval)
    max_interval = abs(max_interval)
    if min_interval > max_interval:
        max_interval = min_interval
    
    # 生成所有需要添加关键帧的时间点
    frames = []
    current_time = start_time
    
    
    while current_time <= end_time:
        frames.append(float(current_time))
        
        if add_keys:
            # 随机间隔
            if min_interval == max_interval:
                current_time += int(min_interval)
            else:
                current_time += int(random.uniform(min_interval, max_interval))
            
            if current_time > end_time:
                frames.append(float(end_time))
        else:
            # ✅ 修复：使用 get_next_keyframe 函数
            next_time = get_next_keyframe(channels[0], current_time)
            
            if next_time is None or next_time == current_time:
                break
            else:
                current_time = next_time
    
    frame_count = len(frames)
    print("共生成 {} 个关键帧时间点".format(frame_count))
    
    if frame_count == 0:
        print("没有生成任何关键帧")
        return
    

    if add_keys:
        print("添加初始关键帧...")
        for time in frames:
            for channel in channels:
                current_value = get_attr_at_time(channel, time)
                set_keyframe_safe(channel, time, current_value)
    
    # 生成随机值
    values = []
    
    for c in range(frame_count):
        for i in range(channel_count):
            # 如果是保持模式，奇数帧使用前一个值
            if add_hold and c % 2 == 1 and values:
                values.append(values[-1])
            else:
                # 生成随机值
                rand_val = random.uniform(min_val, max_val)
                
                # 如果使用相对模式，加到当前值上
                if relative:
                    current_val = get_attr_at_time(channels[i], frames[c])
                    rand_val += current_val
                
                values.append(rand_val)
    
    # 应用关键帧
    for c in range(frame_count):
        for i in range(channel_count):
            value_index = c * channel_count + i
            if value_index < len(values):
                set_keyframe_safe(channels[i], frames[c], values[value_index])
    
    print("✅ 随机关键帧处理完成！")

# ============================================
# 启动函数
# ============================================

def random_keys():
    """
    启动随机关键帧工具的入口函数
    """
    random_keys_ui()


# 如果直接在脚本编辑器中运行
if __name__ == "__main__":
    random_keys()

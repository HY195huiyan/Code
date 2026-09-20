# -*- coding: utf-8 -*-
"""
Maya 动画夸张工具 - 中文版
功能：围绕不同枢轴点缩放动画关键帧
"""

import maya.cmds as cmds


def exaggerate_anim_ui():
    """创建UI - 使用Maya原生窗口"""
    
    window_name = "exaggerateAnimWindow_CN"
    
    # 如果窗口已存在则关闭
    if cmds.window(window_name, exists=True):
        cmds.deleteUI(window_name)
    
    # 创建窗口
    window = cmds.window(
        window_name,
        title="动画缩放工具",
        widthHeight=(400, 200),
        sizeable=True
    )
    
    # 主布局
    main_layout = cmds.formLayout(numberOfDivisions=100)
    
    # 标题
    title = cmds.text(
        label="动画缩放工具",
        font="boldLabelFont",
        height=40
    )
    
    # 分隔线0
    sep0 = cmds.separator(style="in", height=5)
    
    # 枢轴点标签
    pivot_label = cmds.text(
        label="枢轴点:",
        align="left",
        font="smallBoldLabelFont"
    )
    
    # 分隔线1
    sep1 = cmds.separator(style="in", height=5)
    
    # ===== 枢轴点选项 - 使用多个 radioButton 手动布局 =====
    # 创建 radioCollection 确保单选
    radio_collection = cmds.radioCollection()
    
    # 创建5个单选按钮
    radio_zero = cmds.radioButton(
        label="零点",
        annotation="以数值 0 为枢轴",
        parent=main_layout
    )
    radio_start = cmds.radioButton(
        label="起始帧",
        annotation="以第一个关键帧的值为枢轴",
        parent=main_layout,
        select=True  # 默认选中
    )
    radio_current = cmds.radioButton(
        label="当前帧",
        annotation="以当前帧的值为枢轴",
        parent=main_layout
    )
    radio_midpoint = cmds.radioButton(
        label="中点",
        annotation="以最大和最小值的中间值为枢轴",
        parent=main_layout
    )
    radio_end = cmds.radioButton(
        label="结束帧",
        annotation="以最后一个关键帧的值为枢轴",
        parent=main_layout
    )
    
    # 分隔线2
    sep2 = cmds.separator(style="in", height=5)
    
    # 乘数设置行
    multiplier_row = cmds.rowLayout(numberOfColumns=2, columnWidth2=[50, 80])
    multiplier_label = cmds.text(label="倍数:", align="right")
    multiplier_field = cmds.textField(text="1.0", width=180)
    cmds.setParent('..')
    
    # 提示
    tip_label = cmds.text(
        label="💡 提示: 在通道盒中高亮属性可只处理特定通道",
        align="center",
        font="smallPlainLabelFont",
        backgroundColor=(0.25, 0.25, 0.25)
    )
    
    # 分隔线3
    sep3 = cmds.separator(style="in", height=5)
    
    # 按钮
    button_layout = cmds.rowLayout(numberOfColumns=2, columnWidth2=[150, 150], adjustableColumn=2, columnAttach=[(1, 'both', 2), (2, 'both', 2)])
    apply_btn = cmds.button(
        label="✓ 应用",
        backgroundColor=(1.0, 0.42, 0.21),
        command=lambda x: exaggerate_anim_from_ui(
            radio_collection, multiplier_field
        )
    )
    close_btn = cmds.button(
        label="✕ 关闭",
        command=lambda x: cmds.deleteUI(window)
    )
    cmds.setParent('..')
    
    # ===== 使用 formLayout 排列 - 所有 attachForm 合并到一个列表 =====
    cmds.formLayout(
        main_layout,
        edit=True,
        # 所有 attachForm 合并到一个列表中
        attachForm=[
            (title, "top", 5), (title, "left", 5), (title, "right", 5),
            (sep0, "left", 5), (sep0, "right", 5),
            (pivot_label, "left", 5),
            (sep1, "left", 5), (sep1, "right", 5),
            # 5个单选按钮的左右位置
            (radio_zero, "left", 5),
            (radio_end, "right", 5),
            (sep2, "left", 5), (sep2, "right", 5),
            (multiplier_row, "left", 5), (multiplier_row, "right", 5),
            (tip_label, "left", 5), (tip_label, "right", 5),
            (sep3, "left", 5), (sep3, "right", 5),
            (button_layout, "left", 5), (button_layout, "right", 5), (button_layout, "bottom", 5)
        ],
        # 所有 attachControl 合并到一个列表中
        attachControl=[
            (sep0, "top", 3, title),
            (pivot_label, "top", 5, sep0),
            (sep1, "top", 3, pivot_label),
            # 5个单选按钮的垂直排列
            (radio_zero, "top", 5, sep1),
            (radio_start, "top", 5, sep1),
            (radio_current, "top", 5, sep1),
            (radio_midpoint, "top", 5, sep1),
            (radio_end, "top", 5, sep1),
            (sep2, "top", 5, radio_end),
            (multiplier_row, "top", 5, sep2),
            (tip_label, "top", 8, multiplier_row),
            (sep3, "top", 5, tip_label),
            (button_layout, "top", 8, sep3)
        ],
        # 水平位置控制 - 让5个按钮水平排列
        attachPosition=[
            (radio_start, "left", 0, 20),
            (radio_current, "left", 0, 40),
            (radio_midpoint, "left", 0, 60),
            (radio_end, "left", 0, 80)
        ]
    )
    
    cmds.showWindow(window)


def exaggerate_anim_from_ui(radio_collection, multiplier_field):
    """从UI获取参数并执行"""
    
    # 获取选中的单选按钮
    selected_radio = cmds.radioCollection(radio_collection, query=True, select=True)
    
    # 根据选中的按钮确定枢轴点
    pivot_map = {
        "radio_zero": "zero",
        "radio_start": "start",
        "radio_current": "current",
        "radio_midpoint": "midpoint",
        "radio_end": "end"
    }
    pivot_chinese_map = {
        "radio_zero": "零点",
        "radio_start": "起始帧",
        "radio_current": "当前帧",
        "radio_midpoint": "中点",
        "radio_end": "结束帧"
    }
    
    pivot = pivot_map.get(selected_radio, "start")
    pivot_chinese = pivot_chinese_map.get(selected_radio, "起始帧")
    
    # 获取乘数
    try:
        multiplier = float(cmds.textField(multiplier_field, query=True, text=True))
    except:
        cmds.warning("请输入有效的数字！")
        return
    
    # 执行处理
    try:
        result = exaggerate_anim_process(multiplier, pivot)
        cmds.confirmDialog(
            title="完成",
            message=f"✅ 动画缩放完成！\n\n枢轴点: {pivot_chinese}\n乘数: {multiplier}\n\n{result}",
            button=["确定"]
        )
    except Exception as e:
        cmds.confirmDialog(
            title="错误",
            message=f"❌ 操作失败：\n\n{str(e)}",
            button=["确定"]
        )


def exaggerate_anim_process(multiplier, pivot):
    """核心处理函数"""
    
    # 获取选中的物体
    selected = cmds.ls(selection=True, type='transform')
    
    if not selected:
        raise Exception("请先选择至少一个带有动画的物体！")
    
    # 获取选中的关键帧
    selected_keys = cmds.keyframe(query=True, selected=True)
    
    # 获取通道盒中高亮的属性
    try:
        highlighted_attrs = cmds.channelBox('mainChannelBox', 
                                            query=True, 
                                            selectedMainAttributes=True) or []
    except:
        highlighted_attrs = []
    
    # 获取时间范围
    time_min = cmds.playbackOptions(query=True, min=True)
    time_max = cmds.playbackOptions(query=True, max=True)
    
    processed_count = 0
    processed_info = []
    
    if selected_keys and len(selected_keys) > 0:
        # ===== 模式1: 处理选中的关键帧 =====
        print(f"🔧 处理选中的 {len(selected_keys)} 个关键帧...")
        
        # 获取关键帧对应的属性
        anim_attrs = cmds.keyframe(query=True, name=True, selected=True)
        if anim_attrs:
            anim_attrs = list(set(anim_attrs))
        else:
            raise Exception("未找到选中的关键帧！")
        
        for attr in anim_attrs:
            if not cmds.objExists(attr):
                continue
                
            # 获取该属性的选中关键帧时间
            attr_keys = cmds.keyframe(attr, query=True, selected=True)
            if not attr_keys or len(attr_keys) == 0:
                continue
                
            # 计算枢轴值
            pivot_value = get_pivot_value(attr, pivot, attr_keys)
            
            # 缩放关键帧
            try:
                cmds.scaleKey(
                    attr,
                    time=(attr_keys[0], attr_keys[-1]),
                    valueScale=multiplier,
                    valuePivot=pivot_value,
                    timeScale=1,
                    timePivot=0
                )
            except:
                # 备用方案：逐个关键帧处理
                for kf_time in attr_keys:
                    cmds.scaleKey(
                        attr,
                        time=(kf_time, kf_time),
                        valueScale=multiplier,
                        valuePivot=pivot_value,
                        timeScale=1,
                        timePivot=0
                    )
            
            processed_count += len(attr_keys)
            processed_info.append(f"{attr}: {len(attr_keys)}个关键帧")
            
        print(f"✅ 已处理 {processed_count} 个关键帧")
        result_msg = f"处理了 {processed_count} 个关键帧\n"
        result_msg += "\n".join(processed_info[:3])
        if len(processed_info) > 3:
            result_msg += f"\n...等 {len(processed_info)} 个属性"
        
    else:
        # ===== 模式2: 处理整条动画曲线 =====
        print("🔧 处理整条动画曲线...")
        
        # 确定要处理的属性
        if highlighted_attrs:
            # 只处理高亮的属性
            anim_attrs = []
            for obj in selected:
                for attr in highlighted_attrs:
                    full_attr = f"{obj}.{attr}"
                    if cmds.objExists(full_attr):
                        if cmds.getAttr(full_attr, keyable=True):
                            if cmds.keyframe(full_attr, query=True, keyframeCount=True):
                                anim_attrs.append(full_attr)
        else:
            # 默认处理平移和旋转
            anim_attrs = []
            for obj in selected:
                for attr in ['tx', 'ty', 'tz', 'rx', 'ry', 'rz']:
                    full_attr = f"{obj}.{attr}"
                    if cmds.objExists(full_attr):
                        if cmds.getAttr(full_attr, keyable=True):
                            if cmds.keyframe(full_attr, query=True, keyframeCount=True):
                                anim_attrs.append(full_attr)
        
        if not anim_attrs:
            raise Exception("所选物体没有找到可动画的属性！\n请确保物体有关键帧。")
        
        for attr in anim_attrs:
            # 检查是否有关键帧
            if not cmds.keyframe(attr, query=True, keyframeCount=True):
                continue
                
            # 计算枢轴值
            pivot_value = get_pivot_value(attr, pivot)
            
            # 缩放整条曲线
            try:
                cmds.scaleKey(
                    attr,
                    time=(time_min, time_max),
                    valueScale=multiplier,
                    valuePivot=pivot_value,
                    timeScale=1,
                    timePivot=0
                )
            except:
                # 备用方案：使用 index 范围
                key_count = cmds.keyframe(attr, query=True, keyframeCount=True)
                if key_count:
                    cmds.scaleKey(
                        attr,
                        index=(0, key_count - 1),
                        valueScale=multiplier,
                        valuePivot=pivot_value,
                        timeScale=1,
                        timePivot=0
                    )
            
            processed_count += 1
            processed_info.append(attr)
            
        print(f"✅ 已处理 {processed_count} 条动画曲线")
        result_msg = f"处理了 {processed_count} 条曲线\n"
        result_msg += "\n".join(processed_info[:5])
        if len(processed_info) > 5:
            result_msg += f"\n...等 {len(processed_info)} 个属性"
    
    if processed_count == 0:
        result_msg = "⚠️ 没有找到可处理的内容"
    
    return result_msg


def get_pivot_value(attr, pivot, keys=None):
    """
    计算枢轴值
    """
    try:
        if pivot == "zero":
            return 0.0
            
        elif pivot == "start":
            # 使用第一个关键帧的值
            if keys:
                key_values = cmds.keyframe(attr, query=True, valueChange=True, time=(keys[0], keys[0]))
            else:
                key_values = cmds.keyframe(attr, query=True, valueChange=True, index=(0, 0))
            return key_values[0] if key_values else 0.0
            
        elif pivot == "end":
            # 使用最后一个关键帧的值
            if keys:
                key_values = cmds.keyframe(attr, query=True, valueChange=True, time=(keys[-1], keys[-1]))
            else:
                last_time = cmds.findKeyframe(attr, which='last')
                key_values = cmds.keyframe(attr, query=True, valueChange=True, time=(last_time, last_time))
            return key_values[0] if key_values else 0.0
            
        elif pivot == "current":
            # 使用当前值
            try:
                return cmds.getAttr(attr)
            except:
                return 0.0
                
        elif pivot == "midpoint":
            # 使用所有关键帧值的中间值
            if keys:
                key_values = cmds.keyframe(attr, query=True, valueChange=True, 
                                          time=(keys[0], keys[-1]))
            else:
                # 获取整条曲线的值
                key_values = cmds.keyframe(attr, query=True, valueChange=True)
                
            if key_values and len(key_values) > 0:
                sorted_values = sorted(key_values)
                return (sorted_values[0] + sorted_values[-1]) / 2.0
            return 0.0
            
    except Exception as e:
        print(f"⚠️ 计算枢轴值时出错 ({attr}): {e}")
        return 0.0
        
    return 0.0


# 运行
if __name__ == "__main__":
    exaggerate_anim_ui()

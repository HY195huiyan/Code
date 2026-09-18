# -*- coding: utf-8 -*-
import maya.cmds as mc
import maya.mel as mel
import re
import operator

try:
    import anim_layers
except ImportError:
    class AnimLayersMock:
        def buildAnimLayerArray(self):
            layers = mc.ls(type='animLayer')
            return layers if layers else []
    anim_layers = AnimLayersMock()

class AnimCurveOffsetUI:
    def __init__(self):
        self.window_name = "animCurveOffsetWin"
        self.progress_control = None
        self.status_text = None
        self.create_ui()
    
    def create_ui(self):
        """创建主UI界面"""
        if mc.window(self.window_name, exists=True):
            mc.deleteUI(self.window_name)
        
        window = mc.window(
            self.window_name,
            title="动画曲线偏移工具",
            widthHeight=(400, 320),
            sizeable=True,
            minimizeButton=True,
            maximizeButton=False
        )
        
        main_layout = mc.scrollLayout(horizontalScrollBarThickness=0)
        
        # ===== 标题 =====
        mc.frameLayout(label="工具说明", collapsable=True, collapse=False)
        mc.text(label="调整控制器到新位置，然后点击偏移", align="left")
        mc.text(label="工具会自动计算差值并应用到所有关键帧", align="left")
        mc.setParent('..')
        
        mc.separator(height=10)
        
        # ===== 选择模式 =====
        mc.frameLayout(label="选择设置", collapsable=True, collapse=False)
        self.selection_mode = mc.radioButtonGrp(
            label="选择模式:",
            numberOfRadioButtons=2,
            labelArray2=["手动选择", "自动查找控制器"],
            select=1
        )
        mc.setParent('..')
        
        mc.separator(height=10)
        
        # ===== 偏移模式 =====
        mc.frameLayout(label="偏移模式", collapsable=True, collapse=False)
        self.blend_mode = mc.radioButtonGrp(
            label="偏移方式:",
            numberOfRadioButtons=2,
            labelArray2=["全局偏移", "混合偏移"],
            select=1
        )
        mc.setParent('..')
        
        mc.separator(height=10)
        
        # ===== 属性过滤 =====
        mc.frameLayout(label="属性过滤", collapsable=True, collapse=False)
        self.include_scale = mc.checkBox(
            label="包含缩放属性 (Scale)",
            value=False
        )
        self.include_visibility = mc.checkBox(
            label="包含可见性属性 (Visibility)",
            value=False
        )
        mc.setParent('..')
        
        mc.separator(height=10)
        
        # ===== 状态显示 =====
        mc.frameLayout(label="状态信息", collapsable=True, collapse=False)
        self.status_text = mc.text(
            label="就绪 - 选择控制器并调整位置",
            align="center",
            backgroundColor=[0.2, 0.2, 0.2]
        )
        mc.setParent('..')
        
        mc.separator(height=10)
        
        # ===== 按钮 =====
        mc.rowColumnLayout(numberOfColumns=2, columnWidth=[(1, 180), (2, 180)])
        mc.button(
            label="偏移动画",
            command=self.on_offset_clicked,
            backgroundColor=[0.3, 0.6, 0.3],
            height=35
        )
        mc.button(
            label="重置",
            command=self.on_reset_clicked,
            backgroundColor=[0.6, 0.3, 0.3],
            height=35
        )
        mc.setParent('..')
        
        mc.separator(height=5)
        
        # 进度条
        self.progress_control = mc.progressBar(
            width=380,
            maxValue=100,
            visible=False
        )
        
        mc.showWindow()
        self.update_time_display()
    
    def on_offset_clicked(self, *args):
        """执行偏移操作"""
        if mc.autoKeyframe(q=True, state=True):
            mc.confirmDialog(
                title="警告",
                message="自动关键帧处于开启状态！\n请先关闭自动关键帧再执行操作。",
                button=["确定"]
            )
            self.update_status("错误: 自动关键帧开启", [1, 0.3, 0.3])
            return
        
        objects = self.get_selected_objects()
        if not objects:
            mc.confirmDialog(
                title="提示",
                message="没有找到要处理的对象！",
                button=["确定"]
            )
            return
        
        blend = mc.radioButtonGrp(self.blend_mode, query=True, select=True) == 2
        
        self.update_status("正在处理...", [0.3, 0.3, 0.8])
        self.update_progress(0, len(objects))
        
        try:
            for i, node in enumerate(objects):
                self.update_status("处理: {}".format(node), [0.2, 0.4, 0.6])
                self.do_offset_anim_curve(node, blend)
                self.update_progress(i + 1, len(objects))
            
            self.update_status("偏移完成！处理了 {} 个对象".format(len(objects)), [0.2, 0.8, 0.2])
            mc.confirmDialog(
                title="完成",
                message="动画曲线偏移完成！\n处理了 {} 个对象。".format(len(objects)),
                button=["确定"]
            )
            
        except Exception as e:
            self.update_status("错误: {}".format(str(e)), [1, 0.3, 0.3])
            mc.confirmDialog(
                title="错误",
                message="偏移过程中发生错误：\n{}".format(str(e)),
                button=["确定"]
            )
    
    def do_offset_anim_curve(self, node, blend):
        """执行动画曲线偏移 - 原始逻辑"""
        attrs = self.filter_attributes(node)
        if not attrs:
            return
        
        try:
            anim_layers_list = anim_layers.buildAnimLayerArray() if hasattr(anim_layers, 'buildAnimLayerArray') else []
        except:
            anim_layers_list = mc.ls(type='animLayer')
        
        # 存储属性值
        attrs_and_values = []
        for attr in attrs:
            try:
                attr_value = mc.getAttr(node + '.' + attr)
                attrs_and_values.append([attr, attr_value])
            except:
                continue
        
        for attr, attr_value in attrs_and_values:
            anim_curves = self.get_anim_curves(node, [attr])
            if not anim_curves:
                continue
            
            # 分类曲线
            additive_curves = []
            override_curves = []
            other_curves = []
            curve_layer_position = {}
            
            for curve in anim_curves:
                try:
                    outputs = mc.listConnections(curve, s=False, d=True, scn=True)
                    if outputs:
                        output = outputs[0]
                        if re.search('animBlendNode', mc.nodeType(output)):
                            anim_layer = mc.listConnections(output, s=True, d=False, scn=True, type='animLayer')
                            if anim_layer:
                                anim_layer = anim_layer[0]
                                lock_state = mc.animLayer(anim_layer, q=True, lock=True)
                                if anim_layer and not lock_state:
                                    if mc.getAttr(anim_layer + '.override'):
                                        override_curves.append(curve)
                                    else:
                                        additive_curves.append(curve)
                                    
                                    for n in range(len(anim_layers_list)):
                                        if mc.animLayer(anim_layers_list[n], q=True, animCurves=True):
                                            per_layer_curves = mc.animLayer(anim_layers_list[n], q=True, anc=True)
                                            if per_layer_curves and curve in per_layer_curves:
                                                curve_layer_position[curve] = n
                                                break
                        else:
                            other_curves.append(curve)
                except:
                    other_curves.append(curve)
            
            # 排序覆盖曲线
            sorted_positions = sorted(iter(curve_layer_position.items()), key=operator.itemgetter(1))
            
            new_override_curves = []
            for pos in sorted_positions:
                for override in override_curves:
                    if pos[0] == override:
                        new_override_curves.append(pos[0])
            new_override_curves.reverse()
            
            # 处理覆盖曲线分组
            for override in new_override_curves:
                override_grouping = [override]
                for additive in additive_curves[:]:
                    if curve_layer_position[additive] > curve_layer_position[override]:
                        override_grouping.append(additive)
                        additive_curves.remove(additive)
                self.perform_curve_offset(attr_value, override_grouping, blend)
            
            # 处理剩余的叠加曲线
            if additive_curves:
                self.perform_curve_offset(attr_value, additive_curves, blend)
            
            # 处理其他曲线
            if other_curves:
                self.perform_curve_offset(attr_value, other_curves, blend)
    
    def perform_curve_offset(self, attr_value, anim_curves, blend):
        """执行曲线偏移 - 原始逻辑"""
        start_time = mc.playbackOptions(q=True, min=True)
        end_time = mc.playbackOptions(q=True, max=True)
        
        # 计算总值
        total_value = 0.0
        valid_curves = []
        for curve in anim_curves:
            try:
                if mc.referenceQuery(curve, inr=True):
                    continue
                temp_value = mc.keyframe(curve, q=True, eval=True)
                if temp_value:
                    total_value += temp_value[0]
                    valid_curves.append(curve)
            except:
                continue
        
        if not valid_curves:
            return
        
        # 偏移曲线
        for curve in valid_curves:
            try:
                curve_value = mc.keyframe(curve, q=True, eval=True)
                if not curve_value:
                    continue
                curve_value = curve_value[0]
                
                # 计算百分比
                if abs(total_value) > 0.0:
                    percentage = curve_value / total_value
                else:
                    percentage = 1.0 / len(valid_curves)
                
                offset_value = (attr_value - total_value) * percentage
                
                if abs(offset_value) < 0.0001:
                    continue
                
                # 保存锁定状态
                curve_ktv_states = []
                try:
                    ktvs = mc.listAttr(curve + '.ktv', multi=True)
                    if ktvs:
                        for k in range(0, len(ktvs), 3):
                            curve_ktv_states.append(mc.getAttr(curve + '.' + ktvs[k], lock=True))
                        mc.setAttr(curve + '.ktv[*]', lock=False)
                except:
                    pass
                
                # 执行偏移
                if blend:
                    # 混合偏移
                    current_time = mc.currentTime(q=True)
                    blend_range = 30
                    blend_in_start = max(start_time, current_time - blend_range)
                    blend_in_end = current_time
                    blend_out_start = current_time
                    blend_out_end = min(end_time, current_time + blend_range)
                    
                    # 入混合
                    if blend_in_end > blend_in_start:
                        valid_indices = self.get_valid_keys(curve, blend_in_start, blend_in_end)
                        for i in valid_indices:
                            this_time = mc.keyframe(curve, q=True, index=(i, i))[0]
                            if (blend_in_end - blend_in_start) > 0:
                                key_offset = ((this_time - blend_in_start) / (blend_in_end - blend_in_start)) * offset_value
                                mc.keyframe(curve, e=True, relative=True, index=(i, i), valueChange=key_offset)
                    
                    # 出混合
                    if blend_out_end > blend_out_start:
                        valid_indices = self.get_valid_keys(curve, blend_out_start, blend_out_end)
                        for i in valid_indices:
                            this_time = mc.keyframe(curve, q=True, index=(i, i))[0]
                            if (blend_out_end - blend_out_start) > 0:
                                key_offset = ((blend_out_end - this_time) / (blend_out_end - blend_out_start)) * offset_value
                                mc.keyframe(curve, e=True, relative=True, index=(i, i), valueChange=key_offset)
                else:
                    # 全局偏移
                    mc.keyframe(curve, e=True, relative=True, valueChange=offset_value, time=(start_time, end_time))
                
                # 恢复锁定状态
                try:
                    if curve_ktv_states:
                        for x in range(len(curve_ktv_states)):
                            mc.setAttr(curve + '.ktv[' + str(x) + ']', lock=curve_ktv_states[x])
                except:
                    pass
                    
            except Exception as e:
                continue
    
    def get_valid_keys(self, curve, start_time, end_time):
        try:
            key_count = mc.keyframe(curve, q=True, keyframeCount=True)
            if not key_count:
                return []
            key_count = key_count[0]
            
            valid_indices = []
            for i in range(key_count):
                key_time = mc.keyframe(curve, q=True, index=(i, i))
                if key_time and start_time <= key_time[0] <= end_time:
                    valid_indices.append(i)
            return valid_indices
        except:
            return []
    
    def get_selected_objects(self):
        selection_mode = mc.radioButtonGrp(self.selection_mode, query=True, select=True)
        
        if selection_mode == 1:
            sel = mc.ls(sl=True, type=['transform', 'joint'])
            if not sel:
                self.update_status("警告: 没有选中任何对象!", [1, 0.5, 0])
                return []
            self.update_status("找到 {} 个选中的对象".format(len(sel)), [0.2, 0.8, 0.2])
            return sel
        else:
            controls = self.list_controls()
            if not controls:
                self.update_status("警告: 没有找到任何控制器!", [1, 0.5, 0])
                return []
            self.update_status("找到 {} 个控制器".format(len(controls)), [0.2, 0.8, 0.2])
            return controls
    
    def list_controls(self):
        transforms = mc.ls(type=('transform', 'joint'))
        controls = []
        for transform in transforms:
            attrs = mc.listAttr(transform, ud=True)
            if attrs:
                for attr in attrs:
                    if attr == 'controlType':
                        controls.append(transform)
                        break
        return controls
    
    def filter_attributes(self, node):
        attrs = mc.listAttr(node, keyable=True, visible=True)
        if not attrs:
            return []
        
        if not mc.checkBox(self.include_scale, query=True, value=True):
            scale_attrs = [attr for attr in attrs if re.search('scale', attr, re.IGNORECASE)]
            attrs = list(set(attrs) - set(scale_attrs))
        
        if not mc.checkBox(self.include_visibility, query=True, value=True):
            vis_attrs = [attr for attr in attrs if re.search('visibility', attr, re.IGNORECASE)]
            attrs = list(set(attrs) - set(vis_attrs))
        
        return attrs
    
    def get_anim_curves(self, obj, attrs):
        anim_curves = []
        for attr in attrs:
            try:
                connections = mc.listConnections(obj + '.' + attr, s=1, d=0, scn=True, plugs=True)
                if connections:
                    for conn in connections:
                        node = conn.split('.', 1)[0]
                        node_type = mc.nodeType(node)
                        if re.search('animCurve', node_type):
                            anim_curves.append(node)
            except:
                continue
        return list(set(anim_curves))
    
    def update_status(self, text, color=None):
        if mc.text(self.status_text, exists=True):
            if color:
                mc.text(self.status_text, edit=True, label=text, backgroundColor=color)
            else:
                mc.text(self.status_text, edit=True, label=text)
    
    def update_progress(self, value, max_value):
        if mc.progressBar(self.progress_control, exists=True):
            if value == 0:
                mc.progressBar(self.progress_control, edit=True, visible=True, maxValue=max_value)
            mc.progressBar(self.progress_control, edit=True, progress=value)
            if value >= max_value:
                mc.progressBar(self.progress_control, edit=True, visible=False)
    
    def create_time_display(self):
        self.time_field = "time_display_field"
        return self.time_field
    
    def update_time_display(self, *args):
        try:
            current_time = mc.currentTime(q=True)
            mc.textField(self.time_field, edit=True, text="{} 帧".format(int(current_time)))
        except:
            pass
        mc.scriptJob(event=("timeChanged", self.update_time_display), runOnce=True)
    
    def on_reset_clicked(self, *args):
        mc.radioButtonGrp(self.selection_mode, edit=True, select=1)
        mc.radioButtonGrp(self.blend_mode, edit=True, select=1)
        mc.checkBox(self.include_scale, edit=True, value=False)
        mc.checkBox(self.include_visibility, edit=True, value=False)
        mc.select(clear=True)
        self.update_status("UI已重置", [0.5, 0.5, 0.5])
        self.update_progress(0, 100)

# 显示UI
def show_ui():
    global anim_curve_offset_ui
    try:
        anim_curve_offset_ui = AnimCurveOffsetUI()
    except:
        if 'anim_curve_offset_ui' in globals():
            del anim_curve_offset_ui
        anim_curve_offset_ui = AnimCurveOffsetUI()

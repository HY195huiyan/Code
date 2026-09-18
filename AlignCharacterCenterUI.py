"""
角色对齐工具 UI - 稳定版
彻底解决控件引用问题
"""

import maya.cmds as cmds
import importlib


# ===== 全局变量存储 UI 状态 =====
_ui_instance = None


class AlignCharacterUI:
    """角色对齐工具 UI"""
    
    WINDOW_NAME = "alignCharacterUI"
    
    def __init__(self):
        self.pick_job = None
        self.rig_menu = None
        self.target_field = None
        self.x_field = None
        self.z_field = None
        self.contributors_field = None
        self.movers_field = None
        self.layer_field = None
        self.status_text = None
        
    def get_all_rigs(self):
        """获取场景中所有角色"""
        namespaces = cmds.namespaceInfo(listOnlyNamespaces=True, recurse=True)
        rigs = []
        for ns in namespaces:
            if ns not in ['UI', 'shared', 'default']:
                if cmds.objExists(f"{ns}:zeroJointControl1") or cmds.objExists(f"{ns}:Root_CTRL"):
                    rigs.append(ns)
        return sorted(rigs)
    
    def validate_rig_and_target(self, rig_name, target):
        """验证角色和目标控制器是否一致"""
        if not rig_name or rig_name == "未找到角色":
            return False, "请先选择一个有效的角色！", None
        
        if not target:
            return False, "请先选择一个目标控制器！", None
        
        if ':' not in target:
            return False, f"目标控制器 '{target}' 不包含命名空间！", None
        
        target_namespace = target.split(':')[0]
        target_name = target.split(':')[-1]
        
        if target_namespace != rig_name:
            return False, (
                f"❌ 角色与目标控制器不匹配！\n"
                f"当前角色: {rig_name}\n"
                f"目标控制器属于: {target_namespace}\n"
                f"请选择 {rig_name} 下的控制器！"
            ), None
        
        if not cmds.objExists(target):
            return False, f"目标控制器 '{target}' 不存在！", None
        
        if not cmds.objExists(f"{target}.translateX"):
            return False, f"'{target}' 不是有效的控制器", None
        
        full_path = f"{rig_name}:{target_name}"
        if not cmds.objExists(full_path):
            return False, f"角色 '{rig_name}' 下没有 '{target_name}' 控制器！", None
        
        return True, "验证通过", target_name
    
    def on_pick_controller(self):
        """进入拾取模式"""
        if not cmds.window(self.WINDOW_NAME, exists=True):
            return
        
        print("\n🎯 请在视口中点击选择目标控制器")
        
        # 隐藏窗口
        cmds.window(self.WINDOW_NAME, e=True, visible=False)
        
        cmds.selectMode(component=False)
        cmds.selectType(allObjects=True)
        cmds.select(clear=True)
        
        # 清除旧 job
        if self.pick_job:
            try:
                cmds.scriptJob(kill=self.pick_job)
            except:
                pass
            self.pick_job = None
        
        # 创建新 job
        self.pick_job = cmds.scriptJob(
            event=("SelectionChanged", self.on_selection_changed)
        )
        
        cmds.inViewMessage(
            msg='🎯 点击选择一个控制器',
            position='midCenter',
            fade=True,
            fadeStayTime=2000
        )
    
    def on_selection_changed(self, *args):
        """选择变化时触发"""
        # 检查窗口是否存在
        if not cmds.window(self.WINDOW_NAME, exists=True):
            if self.pick_job:
                try:
                    cmds.scriptJob(kill=self.pick_job)
                except:
                    pass
                self.pick_job = None
            return
        
        selection = cmds.ls(sl=True)
        if not selection:
            return
        
        selected = selection[0]
        
        # 检查是否有效
        if not cmds.objExists(selected) or not cmds.objExists(f"{selected}.translateX"):
            return
        
        print(f"✅ 已选择: {selected}")
        
        # 更新目标字段
        if self.target_field and cmds.textField(self.target_field, exists=True):
            cmds.textField(self.target_field, e=True, text=selected)
            cmds.textField(self.target_field, e=True, backgroundColor=(0.2, 0.4, 0.2))
        
        # 自动检测角色
        if ':' in selected:
            rig_name = selected.split(':')[0]
            all_rigs = self.get_all_rigs()
            if rig_name in all_rigs:
                if self.rig_menu and cmds.optionMenu(self.rig_menu, exists=True):
                    cmds.optionMenu(self.rig_menu, e=True, value=rig_name)
                self._update_status(f"✅ 已选择: {selected}", (0.1, 0.5, 0.1))
        
        # 清除 job
        if self.pick_job:
            try:
                cmds.scriptJob(kill=self.pick_job)
            except:
                pass
            self.pick_job = None
        
        # 显示窗口
        if cmds.window(self.WINDOW_NAME, exists=True):
            cmds.window(self.WINDOW_NAME, e=True, visible=True)
    
    def _update_status(self, text, color=(0.2, 0.2, 0.2)):
        """更新状态栏"""
        if self.status_text and cmds.text(self.status_text, exists=True):
            try:
                cmds.text(self.status_text, e=True, label=text, backgroundColor=color)
            except:
                pass
    
    def _safe_text_field(self, field, **kwargs):
        """安全操作 textField"""
        if field and cmds.textField(field, exists=True):
            try:
                return cmds.textField(field, **kwargs)
            except:
                pass
        return None
    
    def _safe_float_field(self, field, **kwargs):
        """安全操作 floatField"""
        if field and cmds.floatField(field, exists=True):
            try:
                return cmds.floatField(field, **kwargs)
            except:
                pass
        return None
    
    def create_ui(self):
        """创建 UI 窗口"""
        
        # 清除旧窗口
        self.close_ui()
        
        if cmds.window(self.WINDOW_NAME, exists=True):
            cmds.deleteUI(self.WINDOW_NAME)
        
        rigs = self.get_all_rigs()
        
        # 创建窗口
        window = cmds.window(
            self.WINDOW_NAME,
            title="🎯 角色对齐工具",
            widthHeight=(480, 500),
            sizeable=False
        )
        
        main_layout = cmds.columnLayout(adj=True, rowSpacing=6, columnAttach=('both', 12))
        
        # 标题
        cmds.text(
            label="角色对齐工具",
            align="center",
            height=30,
            backgroundColor=(0.2, 0.3, 0.4)
        )
        cmds.separator(height=8)
        
        # ===== 角色选择 =====
        cmds.text(label="【角色选择】", align="left")
        
        rig_row = cmds.rowLayout(numberOfColumns=3, columnWidth3=(60, 230, 80))
        cmds.text(label="角色:", align="right", width=50)
        
        self.rig_menu = cmds.optionMenu(
            width=230,
            backgroundColor=(0.1, 0.1, 0.1)
        )
        
        if rigs:
            for rig in rigs:
                cmds.menuItem(label=rig)
        else:
            cmds.menuItem(label="未找到角色")
        
        cmds.button(
            label="刷新",
            width=70,
            command=lambda x: self.refresh_rigs()
        )
        cmds.setParent('..')
        
        cmds.separator(height=8)
        
        # ===== 目标控制器 =====
        cmds.text(label="【目标控制器】", align="left")
        
        ctrl_row = cmds.rowLayout(numberOfColumns=3, columnWidth3=(60, 230, 80))
        cmds.text(label="目标:", align="right", width=50)
        
        self.target_field = cmds.textField(
            text="",
            width=230,
            backgroundColor=(0.1, 0.1, 0.1)
        )
        
        cmds.button(
            label="🎯 拾取",
            width=70,
            backgroundColor=(0.2, 0.5, 0.2),
            command=lambda x: self.on_pick_controller()
        )
        cmds.setParent('..')
        
        cmds.text(
            label="💡 点击 '拾取' 后在视口中点击控制器",
            align="center",
            height=18,
            backgroundColor=(0.05, 0.05, 0.05)
        )
        
        cmds.separator(height=8)
        
        # ===== 目标位置 =====
        cmds.text(label="【目标位置】", align="left")
        
        pos_row = cmds.rowLayout(numberOfColumns=4, columnWidth4=(35, 110, 35, 110))
        cmds.text(label="X:", align="right")
        self.x_field = cmds.floatField(value=15.0, width=90)
        cmds.text(label="Z:", align="right")
        self.z_field = cmds.floatField(value=8.0, width=90)
        cmds.setParent('..')
        
        cmds.button(
            label="📌 读取当前位置",
            width=180,
            backgroundColor=(0.2, 0.3, 0.4),
            command=lambda x: self.read_target_position()
        )
        
        cmds.separator(height=8)
        
        # ===== 高级选项 =====
        frame = cmds.frameLayout(
            label="展开高级选项 ▼",
            collapsable=True,
            collapse=True,
            backgroundColor=(0.1, 0.1, 0.1)
        )
        
        cmds.text(label="贡献者:", align="left")
        self.contributors_field = cmds.textField(
            text="HeadControl1, BackControl3, PelvisControlA1",
            width=380,
            backgroundColor=(0.05, 0.05, 0.05)
        )
        
        cmds.text(label="移动对象:", align="left")
        self.movers_field = cmds.textField(
            text="PelvisControlA1, BackControlIk3, LeftFootControl1, RightFootControl1, LeftHandControl1, RightHandControl1",
            width=380,
            backgroundColor=(0.05, 0.05, 0.05)
        )
        
        cmds.text(label="动画层:", align="left")
        self.layer_field = cmds.textField(
            text="AlignToCenter",
            width=380,
            backgroundColor=(0.05, 0.05, 0.05)
        )
        
        cmds.setParent('..')
        
        cmds.separator(height=12)
        
        # ===== 按钮 =====
        btn_row = cmds.rowLayout(numberOfColumns=3, columnWidth3=(145, 145, 145))
        
        cmds.button(
            label="▶ 执行对齐",
            height=35,
            backgroundColor=(0.2, 0.6, 0.2),
            command=lambda x: self.execute_align()
        )
        
        cmds.button(
            label="📐 测试对齐",
            height=35,
            backgroundColor=(0.4, 0.4, 0.2),
            command=lambda x: self.test_align()
        )
        
        cmds.button(
            label="关闭",
            height=35,
            backgroundColor=(0.3, 0.3, 0.3),
            command=lambda x: self.close_ui()
        )
        cmds.setParent('..')
        
        cmds.separator(height=8)
        
        # 状态栏
        self.status_text = cmds.text(
            label="就绪",
            align="center",
            height=22,
            backgroundColor=(0.1, 0.1, 0.1)
        )
        
        cmds.showWindow(window)
        
        if rigs:
            cmds.optionMenu(self.rig_menu, e=True, value=rigs[0])
    
    def refresh_rigs(self):
        """刷新角色列表"""
        if not self.rig_menu or not cmds.optionMenu(self.rig_menu, exists=True):
            return
        
        rigs = self.get_all_rigs()
        
        # 清空
        items = cmds.optionMenu(self.rig_menu, q=True, itemListLong=True) or []
        for item in items:
            try:
                cmds.deleteUI(item)
            except:
                pass
        
        if rigs:
            for rig in rigs:
                cmds.menuItem(label=rig, parent=self.rig_menu)
            cmds.optionMenu(self.rig_menu, e=True, value=rigs[0])
            self._update_status("✅ 已刷新", (0.1, 0.5, 0.1))
        else:
            cmds.menuItem(label="未找到角色", parent=self.rig_menu)
            self._update_status("⚠️ 未找到角色", (0.5, 0.3, 0.1))
    
    def read_target_position(self):
        """读取目标控制器的当前位置"""
        if not self.target_field:
            return
        
        target = self._safe_text_field(self.target_field, q=True, text=True)
        if not target:
            self._update_status("⚠️ 请先选择目标控制器", (0.5, 0.3, 0.1))
            return
        
        if cmds.objExists(target):
            pos = cmds.xform(target, q=True, ws=True, t=True)
            if self.x_field and cmds.floatField(self.x_field, exists=True):
                cmds.floatField(self.x_field, e=True, value=pos[0])
            if self.z_field and cmds.floatField(self.z_field, exists=True):
                cmds.floatField(self.z_field, e=True, value=pos[2])
            self._update_status(f"📍 位置: ({pos[0]:.2f}, {pos[2]:.2f})", (0.1, 0.4, 0.1))
        else:
            self._update_status(f"❌ 目标不存在", (0.5, 0.1, 0.1))
    
    def execute_align(self):
        """执行对齐"""
        if not cmds.window(self.WINDOW_NAME, exists=True):
            return
        
        # 获取值
        rig_name = None
        if self.rig_menu and cmds.optionMenu(self.rig_menu, exists=True):
            rig_name = cmds.optionMenu(self.rig_menu, q=True, value=True)
        
        target = None
        if self.target_field and cmds.textField(self.target_field, exists=True):
            target = cmds.textField(self.target_field, q=True, text=True)
        
        # 验证
        is_valid, error_msg, target_name = self.validate_rig_and_target(rig_name, target)
        
        if not is_valid:
            self._update_status(f"❌ {error_msg[:40]}", (0.5, 0.1, 0.1))
            cmds.confirmDialog(title="❌ 验证失败", message=error_msg, button=["确定"], icon="critical")
            return
        
        # 获取位置
        if not self.x_field or not self.z_field:
            return
        
        target_x = cmds.floatField(self.x_field, q=True, value=True)
        target_z = cmds.floatField(self.z_field, q=True, value=True)
        
        # 获取高级选项
        contributors_text = ""
        movers_text = ""
        layer_name = "AlignToCenter"
        
        if self.contributors_field and cmds.textField(self.contributors_field, exists=True):
            contributors_text = cmds.textField(self.contributors_field, q=True, text=True)
        if self.movers_field and cmds.textField(self.movers_field, exists=True):
            movers_text = cmds.textField(self.movers_field, q=True, text=True)
        if self.layer_field and cmds.textField(self.layer_field, exists=True):
            layer_name = cmds.textField(self.layer_field, q=True, text=True)
        
        contributors = [c.strip() for c in contributors_text.split(',') if c.strip()]
        movers = [m.strip() for m in movers_text.split(',') if m.strip()]
        
        # 执行
        import AlignCharacterCenter as align_tool
        importlib.reload(align_tool)
        
        try:
            self._update_status(f"⏳ 正在处理 {rig_name}...", (0.2, 0.4, 0.1))
            cmds.refresh()
            
            # 移动目标
            target_obj = f"{rig_name}:{target_name}"
            if cmds.objExists(target_obj):
                cmds.xform(target_obj, ws=True, t=(target_x, 0, target_z))
            
            align_tool.AlignObjectsToTargetForTimeline(
                layerName=layer_name,
                targetObjectName=target_name,
                contributors=contributors,
                movers=movers,
                rigName=rig_name,
                showProgress=True,
                verbose=False
            )
            
            if cmds.objExists(layer_name):
                cmds.setAttr(f"{layer_name}.weight", 1.0)
            
            self._update_status(f"✅ {rig_name} 对齐完成！", (0.1, 0.5, 0.1))
            cmds.confirmDialog(
                title="✅ 完成",
                message=f"{rig_name} 对齐完成！\n目标: ({target_x}, {target_z})",
                button=["确定"]
            )
            
        except Exception as e:
            self._update_status(f"❌ 错误: {str(e)[:40]}", (0.5, 0.1, 0.1))
            cmds.confirmDialog(title="错误", message=str(e), button=["确定"], icon="critical")
    
    def test_align(self):
        """测试对齐"""
        if not cmds.window(self.WINDOW_NAME, exists=True):
            return
        
        # 获取值
        rig_name = None
        if self.rig_menu and cmds.optionMenu(self.rig_menu, exists=True):
            rig_name = cmds.optionMenu(self.rig_menu, q=True, value=True)
        
        target = None
        if self.target_field and cmds.textField(self.target_field, exists=True):
            target = cmds.textField(self.target_field, q=True, text=True)
        
        is_valid, error_msg, target_name = self.validate_rig_and_target(rig_name, target)
        
        if not is_valid:
            self._update_status(f"❌ {error_msg[:40]}", (0.5, 0.1, 0.1))
            cmds.confirmDialog(title="❌ 验证失败", message=error_msg, button=["确定"], icon="critical")
            return
        
        if not self.x_field or not self.z_field:
            return
        
        target_x = cmds.floatField(self.x_field, q=True, value=True)
        target_z = cmds.floatField(self.z_field, q=True, value=True)
        
        contributors_text = ""
        movers_text = ""
        
        if self.contributors_field and cmds.textField(self.contributors_field, exists=True):
            contributors_text = cmds.textField(self.contributors_field, q=True, text=True)
        if self.movers_field and cmds.textField(self.movers_field, exists=True):
            movers_text = cmds.textField(self.movers_field, q=True, text=True)
        
        contributors = [c.strip() for c in contributors_text.split(',') if c.strip()]
        movers = [m.strip() for m in movers_text.split(',') if m.strip()]
        
        contributors_qualified = [f"{rig_name}:{c}" for c in contributors]
        movers_qualified = [f"{rig_name}:{m}" for m in movers]
        
        import AlignCharacterCenter as align_tool
        importlib.reload(align_tool)
        
        try:
            self._update_status(f"⏳ 测试 {rig_name}...", (0.2, 0.4, 0.1))
            cmds.refresh()
            
            target_obj = f"{rig_name}:{target_name}"
            if cmds.objExists(target_obj):
                cmds.xform(target_obj, ws=True, t=(target_x, 0, target_z))
            
            result = align_tool.AlignCenterXzOverTarget(
                contributors=contributors_qualified,
                targetObject=f"{rig_name}:{target_name}",
                movers=movers_qualified,
                verbose=True
            )
            
            self._update_status(f"✅ 测试完成！偏移: {result['appliedDelta']}", (0.1, 0.5, 0.1))
            
        except Exception as e:
            self._update_status(f"❌ 错误: {str(e)[:40]}", (0.5, 0.1, 0.1))
            cmds.confirmDialog(title="错误", message=str(e), button=["确定"], icon="critical")
    
    def close_ui(self):
        """关闭 UI"""
        if self.pick_job:
            try:
                cmds.scriptJob(kill=self.pick_job)
            except:
                pass
            self.pick_job = None
        
        if cmds.window(self.WINDOW_NAME, exists=True):
            cmds.deleteUI(self.WINDOW_NAME)


# ===== 启动函数 =====
def launch():
    """启动工具"""
    global _ui_instance
    
    # 关闭旧实例
    if _ui_instance:
        try:
            _ui_instance.close_ui()
        except:
            pass
    
    _ui_instance = AlignCharacterUI()
    _ui_instance.create_ui()
    return _ui_instance


def close():
    """关闭工具"""
    global _ui_instance
    if _ui_instance:
        _ui_instance.close_ui()
        _ui_instance = None


if __name__ == "__main__":
    launch()
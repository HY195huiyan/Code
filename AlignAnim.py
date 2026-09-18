"""
alignAnim_ui.py
动画对齐工具 - Maya Python UI
自动加载同目录下的 alignAnim.mel 文件
"""

import maya.cmds as cmds
import maya.mel as mel
import functools
import os

class AlignAnimUI:
    """动画对齐工具的UI类"""
    
    WINDOW_NAME = "alignAnimWindow"
    
    def __init__(self):
        # 加载MEL文件
        self.load_mel_file()
        self.create_ui()
    
    def load_mel_file(self):
        """加载同目录下的 alignAnim.mel 文件"""
        try:
            # 获取当前脚本的目录
            script_path = os.path.dirname(__file__)
            mel_file_path = os.path.join(script_path, "alignAnim.mel")
            
            # 如果文件存在，加载它
            if os.path.exists(mel_file_path):
                print("正在加载 MEL 文件: " + mel_file_path)
                mel.eval('source "' + mel_file_path.replace('\\', '/') + '";')
                print("✓ MEL 文件加载成功！")
            else:
                # 如果找不到，尝试在Maya脚本路径中搜索
                print("警告: 未找到 alignAnim.mel 文件，尝试从Maya路径加载...")
                mel.eval('source "alignAnim.mel";')
                print("✓ MEL 文件从Maya路径加载成功！")
                
        except Exception as e:
            cmds.warning("加载 alignAnim.mel 失败: " + str(e))
            cmds.warning("请确保 alignAnim.mel 文件位于脚本目录或Maya脚本路径中")
    
    def create_ui(self):
        """创建主UI界面"""
        # 如果窗口已存在，删除它
        if cmds.window(self.WINDOW_NAME, exists=True):
            cmds.deleteUI(self.WINDOW_NAME)
        
        # 创建窗口
        window = cmds.window(
            self.WINDOW_NAME,
            title="动画对齐工具",
            widthHeight=(400, 380),
            sizeable=True
        )
        
        # 主布局
        main_layout = cmds.columnLayout(
            adjustableColumn=True,
            rowSpacing=5,
            columnAttach=('both', 20)
        )
        
        # 标题
        cmds.text(label="动画对齐工具", font="boldLabelFont", align="center")
        cmds.text(label="基于 alignAnim MEL 函数", font="smallPlainLabelFont", align="center")
        
        cmds.separator(height=10, style="in")
        
        # 说明文字
        cmds.text(label="选择两个物体：先选源物体，再选目标物体", align="center", font="smallPlainLabelFont")
        cmds.text(label="源物体 → 目标物体（动画将被复制）", align="center", font="smallPlainLabelFont")
        
        cmds.separator(height=10, style="in")
        
        # 对齐选项区域
        cmds.frameLayout(label="对齐选项", collapsable=False)
        
        cmds.columnLayout(adjustableColumn=True, rowSpacing=10, columnAttach=('both', 20))
        
        # 三个对齐按钮
        cmds.button(
            label="只对齐位移",
            command=functools.partial(self.on_align, [1, 0]),
            backgroundColor=[0.3, 0.6, 0.9],
            height=35
        )
        
        cmds.button(
            label="只对齐旋转",
            command=functools.partial(self.on_align, [0, 1]),
            backgroundColor=[0.3, 0.9, 0.6],
            height=35
        )
        
        cmds.button(
            label="同时对齐位移和旋转",
            command=functools.partial(self.on_align, [1, 1]),
            backgroundColor=[0.9, 0.6, 0.3],
            height=35
        )
        
        cmds.setParent('..')
        
        cmds.separator(height=10, style="in")
        
        # 状态信息区域
        cmds.frameLayout(label="状态信息", collapsable=False)
        self.status_text = cmds.text(
            label="选择两个物体后点击按钮执行对齐操作。",
            align="left",
            font="smallPlainLabelFont"
        )
        cmds.text(
            label="先选源物体（带动画），再选目标物体（将被覆盖动画）",
            align="left",
            font="smallPlainLabelFont"
        )
        cmds.setParent('..')
        
        cmds.separator(height=10, style="in")
        
        # 底部按钮
        cmds.rowLayout(
            numberOfColumns=3,
            columnWidth=[(1, 100), (2, 100), (3, 100)],
            columnAttach=[(1, 'both', 5), (2, 'both', 5), (3, 'both', 5)]
        )
        cmds.button(label="刷新选择", command=self.on_refresh)
        cmds.button(label="帮助", command=self.on_help)
        cmds.button(label="关闭", command=lambda x: cmds.deleteUI(self.WINDOW_NAME))
        cmds.setParent('..')
        
        # 显示窗口
        cmds.showWindow(window)
    
    def on_align(self, options, *args):
        """
        对齐按钮的回调函数
        Args:
            options: [位移开关, 旋转开关] 例如 [1, 0] 只对齐位移
        """
        # 获取选中的物体
        selected = cmds.ls(selection=True)
        
        if len(selected) != 2:
            cmds.warning("请恰好选择两个物体！先选源物体，再选目标物体。")
            return
        
        source = selected[0]
        target = selected[1]
        
        print("\n========== 执行对齐动画 ==========")
        print("源物体: " + source)
        print("目标物体: " + target)
        
        # 构建MEL命令字符串
        mel_command = 'alignAnim({' + str(options[0]) + ', ' + str(options[1]) + '});'
        
        # 调用MEL函数
        try:
            # 先选择源物体和目标物体（确保顺序正确）
            cmds.select(source, target)
            # 执行MEL命令
            mel.eval(mel_command)
            
            # 更新状态
            if options[0] == 1 and options[1] == 0:
                mode = "只对齐位移"
            elif options[0] == 0 and options[1] == 1:
                mode = "只对齐旋转"
            else:
                mode = "同时对齐位移和旋转"
            
            status = "✓ 完成：" + mode + " - 源: " + source + " → 目标: " + target
            cmds.text(self.status_text, edit=True, label=status)
            print(status)
            print("========================================\n")
            
        except Exception as e:
            cmds.warning("执行 alignAnim 时出错：" + str(e))
            print("错误: " + str(e))
            cmds.text(self.status_text, edit=True, label="✗ 执行失败，请检查MEL函数是否正确加载")
    
    def on_refresh(self, *args):
        """刷新选择状态"""
        selected = cmds.ls(selection=True)
        
        if len(selected) == 2:
            status = "当前选择：源物体 [" + selected[0] + "] → 目标物体 [" + selected[1] + "]"
            cmds.warning(status)
            cmds.text(self.status_text, edit=True, label=status)
        elif len(selected) == 0:
            cmds.warning("未选择任何物体，请选择两个物体")
            cmds.text(self.status_text, edit=True, label="未选择任何物体，请选择两个物体")
        else:
            status = "当前选择了 " + str(len(selected)) + " 个物体，请恰好选择两个物体"
            cmds.warning(status)
            cmds.text(self.status_text, edit=True, label=status)
    
    def on_help(self, *args):
        """显示帮助信息"""
        help_text = """
===========================================
动画对齐工具 - 帮助
===========================================
功能说明：
  将源物体的动画数据复制到目标物体

使用方法：
  1. 在场景中选择两个物体
  2. 先点击选择【源物体】（包含动画的物体）
  3. 再点击选择【目标物体】（将要接收动画的物体）
  4. 点击相应的对齐按钮

三个按钮的区别：
  【只对齐位移】- 只复制位置动画，保留目标物体的旋转
  【只对齐旋转】- 只复制旋转动画，保留目标物体的位置
  【同时对齐位移和旋转】- 同时复制位置和旋转动画

注意事项：
  1. 目标物体原有的关键帧将被覆盖
  2. 支持不同的旋转顺序 (rotateOrder)
  3. 操作前建议保存场景或创建备份
===========================================
"""
        print(help_text)
        cmds.confirmDialog(
            title="帮助",
            message=help_text,
            button=["确定"],
            defaultButton="确定"
        )


#===============================================================================
# 创建UI的快捷函数
#===============================================================================

def align_anim_ui():
    """创建并显示UI"""
    global align_anim_ui_instance
    align_anim_ui_instance = AlignAnimUI()


# 如果脚本被直接执行
if __name__ == "__main__":
    align_anim_ui()
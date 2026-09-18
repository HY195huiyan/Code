import maya.cmds as cmds
import maya.mel as mel

def follow_object():
    start_time = cmds.playbackOptions(q=True, min=True)
    end_time = cmds.playbackOptions(q=True, max=True)
    follow_object_proc(start_time, end_time, 1)

def follow_object_from_ui():
    try:
        s_time = float(cmds.textField('txtStart', q=True, text=True))
        e_time = float(cmds.textField('txtEnd', q=True, text=True))
        sample = float(cmds.textField('txtSample', q=True, text=True))
        follow_object_proc(s_time, e_time, sample)
    except ValueError:
        cmds.error("所有字段必须输入数字值。")

def follow_object_ui():
    win = "followObjectWin"
    if cmds.window(win, q=True, exists=True):
        cmds.deleteUI(win, window=True)
    
    cmds.window(win, title="物体跟随工具", widthHeight=(260, 180), menuBar=True, sizeable=True)
    
    # 主列布局，带间距
    cmds.columnLayout(adj=True, rowSpacing=5, columnOffset=['both', 10])
    
    # 起始帧
    cmds.rowLayout(numberOfColumns=2, adj=2, columnAlign=(1, 'right'), columnWidth=[(1, 70), (2, 130)])
    cmds.text(label="起始帧：")
    cmds.textField('txtStart', text=str(int(cmds.playbackOptions(q=True, min=True))))
    cmds.setParent('..')
    
    # 结束帧
    cmds.rowLayout(numberOfColumns=2, adj=2, columnAlign=(1, 'right'), columnWidth=[(1, 70), (2, 130)])
    cmds.text(label="结束帧：")
    cmds.textField('txtEnd', text=str(int(cmds.playbackOptions(q=True, max=True))))
    cmds.setParent('..')
    
    # 采样间隔
    cmds.rowLayout(numberOfColumns=2, adj=2, columnAlign=(1, 'right'), columnWidth=[(1, 70), (2, 130)])
    cmds.text(label="采样间隔：")
    cmds.textField('txtSample', text="1")
    cmds.setParent('..')
    
    # 间距
    cmds.separator(height=10, style='none')
    
    # 按钮行
    cmds.rowLayout(numberOfColumns=2, adj=2, columnWidth=[(1, 150), (2, 150)], columnAlign=(1, 'center'))
    cmds.button(label="确 定", width=150, height=35, command=lambda *args: follow_object_from_ui())
    cmds.button(label="取 消", width=150, height=35, command=lambda *args: cmds.deleteUI(win))
    cmds.setParent('..')
    
    cmds.setParent('..')
    
    cmds.showWindow(win)

def follow_object_proc(start_time, end_time, sample_by):
    selection = cmds.ls(selection=True)
    if len(selection) < 2:
        cmds.error("请先选择参考物体，再选择要跟随的物体。")
    
    # 关闭并行评估
    mel.eval('evaluationManager -mode "off";')
    locators = []
    
    try:
        # 为每个需要跟随的物体创建定位器
        for i in range(1, len(selection)):
            obj = selection[i]
            
            # 检查是否有约束
            constraints = cmds.listRelatives(obj, children=True, type='constraint') or []
            for con in constraints:
                if cmds.objectType(con) != 'poleVectorConstraint':
                    cmds.error(f"物体 {obj} 存在约束，无法处理。")
            
            # 创建定位器
            loc = cmds.spaceLocator()[0]
            locators.append(loc)
            
            # 获取物体位置和旋转
            pos = cmds.xform(obj, q=True, ws=True, translation=True)
            rot = cmds.xform(obj, q=True, ws=True, rotation=True)
            
            # 定位器对齐到物体
            cmds.xform(loc, ws=True, translation=pos, rotation=rot)
            
            # 定位器父级到参考物体
            cmds.parent(loc, selection[0])
        
        # 逐帧采样
        t = start_time
        while t <= end_time:
            cmds.currentTime(t)
            
            for i, loc in enumerate(locators):
                obj = selection[i + 1]
                
                # 获取定位器位置和旋转
                pos = cmds.xform(loc, q=True, ws=True, translation=True)
                rot = cmds.xform(loc, q=True, ws=True, rotation=True)
                
                # 物体对齐到定位器
                cmds.xform(obj, ws=True, translation=pos, rotation=rot)
                
                # 打关键帧
                cmds.setKeyframe(obj, at='translate')
                cmds.setKeyframe(obj, at='rotate')
            
            t += sample_by
    
    finally:
        # 删除定位器
        for loc in locators:
            if cmds.objExists(loc):
                cmds.delete(loc)
        
        # 重新选中物体
        cmds.select(selection, replace=True)
        
        # 恢复并行评估
        mel.eval('evaluationManager -mode "parallel";')

# 运行 UI
follow_object_ui()
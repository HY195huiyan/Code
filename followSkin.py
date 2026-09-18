# -*- coding: utf-8 -*-
"""
followSkin.py - 表面跟随工具（完整版）
功能：让选中的物体跟随曲面/网格表面运动，带法线对齐和向上方向控制
完全还原原始 MEL 脚本功能
作者：MEL to Python 转换
"""

import maya.cmds as cmds
import maya.mel as mel
import re


def follow_skin_full():
    """
    完整版：让物体跟随表面，带法线对齐和向上方向控制
    使用方法：
        1. 选择表面物体（或表面的顶点/边/面/曲面点）
        2. 选择要跟随的物体
        3. 运行 follow_skin_full()
    """
    
    # ============================================================
    # 1. 获取选择
    # ============================================================
    
    selected = cmds.ls(sl=True, flatten=True)
    if len(selected) < 2:
        cmds.error("请至少选择2个物体：第一个是表面参考，其余是要跟随的物体")
    
    # 获取原始的物体选择（不含子元素路径）
    raw_selected = cmds.ls(sl=True)
    
    # ============================================================
    # 2. 解析选择类型
    # ============================================================
    
    vertices = cmds.filterExpand(sm=31) or []
    edges = cmds.filterExpand(sm=32) or []
    faces = cmds.filterExpand(sm=34) or []
    surface_points = cmds.filterExpand(sm=41) or []
    
    # 初始化
    surface = raw_selected[0] if raw_selected else ""
    obj_type = ""
    shapes = []
    target_pos = []
    face_index = 0
    surface_point_uv = []
    up_object = ""
    use_hair = False
    current_uv_set = ""
    
    # --- 检查是否选中了子元素 ---
    has_subcomponent = len(vertices) + len(edges) + len(faces) + len(surface_points) > 0
    
    # --- 处理顶点 ---
    if len(vertices) == 1:
        parts = re.split(r'[.\[\]]', vertices[0])
        if len(parts) > 2:
            target_pos = cmds.xform(vertices[0], ws=True, q=True, t=True)
            surface = parts[0]
            obj_type = "mesh"
            shapes = cmds.listRelatives(surface, s=True) or []
            up_objects = cmds.ls(sl=True)
            up_object = up_objects[0] if up_objects else ""
            print("选中顶点: " + vertices[0])
    
    # --- 处理边 ---
    elif len(edges) == 1:
        parts = re.split(r'[.\[\]]', edges[0])
        if len(parts) > 2:
            target_pos = cmds.xform(edges[0], ws=True, q=True, t=True)
            surface = parts[0]
            obj_type = "mesh"
            shapes = cmds.listRelatives(surface, s=True) or []
            up_objects = cmds.ls(sl=True)
            up_object = up_objects[0] if up_objects else ""
            print("选中边: " + edges[0])
    
    # --- 处理面 ---
    elif len(faces) == 1:
        parts = re.split(r'[.\[\]]', faces[0])
        if len(parts) > 2:
            target_pos = cmds.xform(faces[0], ws=True, q=True, t=True)
            surface = parts[0]
            face_index = int(parts[2]) if len(parts) > 2 else 0
            obj_type = "mesh"
            shapes = cmds.listRelatives(surface, s=True) or []
            up_objects = cmds.ls(sl=True)
            up_object = up_objects[0] if up_objects else ""
            print("选中面: " + faces[0])
    
    # --- 处理 NURBS 曲面点 ---
    elif len(surface_points) == 1:
        match = re.search(r'([^\[]+)\[([^\]]+)\]\[([^\]]+)\]', surface_points[0])
        if match:
            surface = match.group(1)
            surface_point_uv = [float(match.group(2)), float(match.group(3))]
            obj_type = "nurbsSurface"
            shapes = cmds.listRelatives(surface, s=True) or []
            up_objects = cmds.ls(sl=True)
            up_object = up_objects[0] if up_objects else ""
            print("选中曲面点: " + surface_points[0])
    
    # --- 没有子元素，使用物体本身 ---
    else:
        obj_type = cmds.objectType(raw_selected[0])
        if obj_type == "transform":
            shapes = cmds.listRelatives(raw_selected[0], s=True) or []
            if not shapes:
                cmds.error("第一个选中的物体必须是多边形网格或NURBS曲面")
            obj_type = cmds.objectType(shapes[0])
            surface = raw_selected[0]
        else:
            shapes = [raw_selected[0]]
            surface = raw_selected[0]
        
        # 使用第一个物体作为向上参考
        up_object = raw_selected[0]
        print("使用物体本身: " + surface)
    
    # 验证
    if obj_type not in ["mesh", "nurbsSurface"]:
        cmds.error("表面必须是多边形网格(mesh)或NURBS曲面")
    
    if not shapes:
        cmds.error("无法获取表面形状节点")
    
    # 获取 UV 集
    if obj_type == "mesh" and shapes:
        uv_sets = cmds.polyUVSet(shapes[0], q=True, currentUVSet=True)
        current_uv_set = uv_sets[0] if uv_sets else ""
        print("UV集: " + current_uv_set)
    
    # ============================================================
    # 3. 处理每个跟随物体
    # ============================================================
    
    # 获取要跟随的物体列表（排除表面物体）
    followers = []
    for item in raw_selected:
        if item != surface:
            followers.append(item)
    
    if not followers:
        cmds.error("没有找到要跟随的物体")
    
    print("\n表面: " + surface)
    print("跟随物体: " + ", ".join(followers))
    print("="*50)
    
    # 用于清理的列表
    to_be_deleted = []
    
    for i, follower in enumerate(followers):
        print("\n处理: " + follower)
        
        # 获取物体当前的位置和旋转
        pos = cmds.xform(follower, ws=True, q=True, t=True)
        rot = cmds.xform(follower, ws=True, q=True, ro=True)
        
        # --- 主 Follicle ---
        param_u = 0.5
        param_v = 0.5
        follicle_transform = None
        
        if obj_type == "mesh":
            # 创建 closestPointOnMesh
            cpom = cmds.createNode('closestPointOnMesh')
            
            # 设置输入位置
            if target_pos:
                cmds.setAttr(cpom + '.inPositionX', target_pos[0])
                cmds.setAttr(cpom + '.inPositionY', target_pos[1])
                cmds.setAttr(cpom + '.inPositionZ', target_pos[2])
            else:
                cmds.setAttr(cpom + '.inPositionX', pos[0])
                cmds.setAttr(cpom + '.inPositionY', pos[1])
                cmds.setAttr(cpom + '.inPositionZ', pos[2])
            
            # 连接网格
            cmds.connectAttr(shapes[0] + '.worldMesh[0]', cpom + '.inMesh', f=True)
            
            # 获取参数
            param_u = cmds.getAttr(cpom + '.parameterU')
            param_v = cmds.getAttr(cpom + '.parameterV')
            if not face_index:
                face_index = cmds.getAttr(cpom + '.closestFaceIndex')
            
            # 创建 follicle
            follicle = cmds.createNode('follicle')
            if follicle.startswith('unknown'):
                cmds.delete(follicle, cpom)
                cmds.error("需要 Maya Hair 插件")
            
            # 设置
            if current_uv_set:
                cmds.setAttr(follicle + '.mapSetName', current_uv_set, type='string')
            
            follicle_transform = cmds.listRelatives(follicle, p=True)
            if follicle_transform:
                follicle_transform = follicle_transform[0]
            
            cmds.connectAttr(shapes[0] + '.outMesh', follicle + '.inputMesh')
            cmds.connectAttr(shapes[0] + '.worldMatrix[0]', follicle + '.inputWorldMatrix')
            
            if follicle_transform:
                cmds.connectAttr(follicle + '.outTranslate', follicle_transform + '.translate')
                cmds.connectAttr(follicle + '.outRotate', follicle_transform + '.rotate')
            
            cmds.setAttr(follicle + '.parameterU', param_u)
            cmds.setAttr(follicle + '.parameterV', param_v)
            
            # 保存用于清理
            to_be_deleted.append(follicle)
            if follicle_transform:
                to_be_deleted.append(follicle_transform)
            
            cmds.delete(cpom)
            
        elif obj_type == "nurbsSurface":
            if not surface_point_uv:
                cpom = cmds.createNode('closestPointOnSurface')
                cmds.connectAttr(shapes[0] + '.worldSurface[0]', cpom + '.inSurface')
                
                cmds.setAttr(cpom + '.inPositionX', pos[0])
                cmds.setAttr(cpom + '.inPositionY', pos[1])
                cmds.setAttr(cpom + '.inPositionZ', pos[2])
                
                surface_point_uv = [
                    cmds.getAttr(cpom + '.parameterU'),
                    cmds.getAttr(cpom + '.parameterV')
                ]
                cmds.delete(cpom)
            
            follicle = cmds.createNode('follicle')
            if not follicle.startswith('unknown'):
                follicle_transform = cmds.listRelatives(follicle, p=True)
                if follicle_transform:
                    follicle_transform = follicle_transform[0]
                
                cmds.connectAttr(shapes[0] + '.local', follicle + '.inputSurface')
                cmds.connectAttr(shapes[0] + '.worldMatrix[0]', follicle + '.inputWorldMatrix')
                
                if follicle_transform:
                    cmds.connectAttr(follicle + '.outTranslate', follicle_transform + '.translate')
                    cmds.connectAttr(follicle + '.outRotate', follicle_transform + '.rotate')
                
                cmds.setAttr(follicle + '.parameterU', surface_point_uv[0])
                cmds.setAttr(follicle + '.parameterV', surface_point_uv[1])
                
                to_be_deleted.append(follicle)
                if follicle_transform:
                    to_be_deleted.append(follicle_transform)
        
        # --- 创建约束定位器 ---
        const_loc = cmds.spaceLocator(p=(0,0,0))[0]
        up_loc = cmds.spaceLocator(p=(0,0,0))[0]
        
        # --- 法线约束 ---
        if shapes and follicle_transform:
            normal_constraint = cmds.normalConstraint(
                shapes[0], const_loc,
                worldUpType='object',
                worldUpObject=up_loc,
                aimVector=(0,1,0),
                upVector=(0,0,1)
            )
            if normal_constraint:
                to_be_deleted.append(normal_constraint[0])
        
        # 连接 follicle 变换到定位器
        if follicle_transform:
            cmds.connectAttr(follicle_transform + '.translate', const_loc + '.translate')
        
        # --- 向上方向控制（第二个 follicle）---
        # 这是原始 MEL 脚本的关键功能
        if up_object and shapes and obj_type == "mesh":
            new_follicle = cmds.createNode('follicle')
            
            if not new_follicle.startswith('unknown'):
                if current_uv_set:
                    cmds.setAttr(new_follicle + '.mapSetName', current_uv_set, type='string')
                
                new_follicle_trans = cmds.listRelatives(new_follicle, p=True)
                if new_follicle_trans:
                    new_follicle_trans = new_follicle_trans[0]
                
                # 获取 up_object 的位置
                if cmds.objExists(up_object):
                    up_pos = cmds.xform(up_object, ws=True, q=True, t=True)
                    
                    # 创建 cpom 获取 UV
                    new_cpom = cmds.createNode('closestPointOnMesh')
                    cmds.connectAttr(shapes[0] + '.worldMesh[0]', new_cpom + '.inMesh', f=True)
                    
                    cmds.setAttr(new_cpom + '.inPositionX', up_pos[0])
                    cmds.setAttr(new_cpom + '.inPositionY', up_pos[1])
                    cmds.setAttr(new_cpom + '.inPositionZ', up_pos[2])
                    
                    new_u = cmds.getAttr(new_cpom + '.parameterU')
                    new_v = cmds.getAttr(new_cpom + '.parameterV')
                    
                    cmds.connectAttr(shapes[0] + '.outMesh', new_follicle + '.inputMesh')
                    cmds.connectAttr(shapes[0] + '.worldMatrix[0]', new_follicle + '.inputWorldMatrix')
                    
                    if new_follicle_trans:
                        cmds.connectAttr(new_follicle + '.outTranslate', new_follicle_trans + '.translate')
                        cmds.connectAttr(new_follicle + '.outRotate', new_follicle_trans + '.rotate')
                    
                    cmds.setAttr(new_follicle + '.parameterU', new_u)
                    cmds.setAttr(new_follicle + '.parameterV', new_v)
                    
                    # 约束 up_loc 到新的 follicle 变换
                    if new_follicle_trans:
                        point_constraint = cmds.pointConstraint(new_follicle_trans, up_loc)[0]
                        to_be_deleted.append(point_constraint)
                    
                    cmds.delete(new_cpom)
                    to_be_deleted.append(new_follicle)
                    if new_follicle_trans:
                        to_be_deleted.append(new_follicle_trans)
        
        # --- 创建对齐定位器 ---
        loc = cmds.spaceLocator(p=(0,0,0))[0]
        cmds.xform(loc, ws=True, t=pos, ro=rot)
        cmds.parent(loc, const_loc)
        
        to_be_deleted.append(const_loc)
        to_be_deleted.append(up_loc)
        to_be_deleted.append(loc)
        
        # --- 烘焙动画 ---
        start = cmds.playbackOptions(q=True, min=True)
        end = cmds.playbackOptions(q=True, max=True)
        
        # 创建约束
        parent_constraint = cmds.parentConstraint(loc, follower)[0]
        to_be_deleted.append(parent_constraint)
        
        # 烘焙
        cmds.paneLayout('viewPanes', e=True, manage=False)
        cmds.bakeResults(
            follower,
            t=(start, end),
            simulation=True,
            attribute=['tx', 'ty', 'tz', 'rx', 'ry', 'rz']
        )
        cmds.paneLayout('viewPanes', e=True, manage=True)
        
        # 清理
        for node in to_be_deleted:
            if node and cmds.objExists(node):
                try:
                    cmds.delete(node)
                except:
                    pass
        
        to_be_deleted = []
        print("  ✓ " + follower + " 已附着")
    
    print("\n" + "="*50)
    print("✅ 完成！所有物体已附着到表面")
    print("="*50)


# ============================================================
# 不烘焙版本（保持约束，物体实时跟随）
# ============================================================

def follow_skin_no_bake():
    """
    让物体跟随表面（不烘焙，保持约束）
    适用于需要实时跟随的场景
    """
    sel = cmds.ls(sl=True)
    if len(sel) < 2:
        cmds.error("请选择：表面物体 + 要跟随的物体")
    
    surface = sel[0]
    followers = sel[1:]
    
    shapes = cmds.listRelatives(surface, s=True)
    if not shapes:
        cmds.error("第一个物体不是有效的表面")
    
    shape = shapes[0]
    shape_type = cmds.objectType(shape)
    
    if shape_type not in ['mesh', 'nurbsSurface']:
        cmds.error("表面必须是多边形网格(mesh)或NURBS曲面")
    
    # 清理旧的 follicle
    old_follicles = cmds.ls(type='follicle')
    if old_follicles:
        for f in old_follicles:
            try:
                # 先断开连接再删除
                cmds.delete(f)
            except:
                pass
        print("清理了旧 Follicle")
    
    for follower in followers:
        # 清除物体的变换
        try:
            cmds.setAttr(follower + '.translateX', 0)
            cmds.setAttr(follower + '.translateY', 0)
            cmds.setAttr(follower + '.translateZ', 0)
            cmds.setAttr(follower + '.rotateX', 0)
            cmds.setAttr(follower + '.rotateY', 0)
            cmds.setAttr(follower + '.rotateZ', 0)
        except:
            pass
        
        # 创建 follicle
        follicle = cmds.createNode('follicle')
        
        # 获取 UV 集
        uv_set = ""
        if shape_type == 'mesh':
            uv_sets = cmds.polyUVSet(surface, q=True, currentUVSet=True)
            if uv_sets:
                uv_set = uv_sets[0]
                cmds.setAttr(follicle + '.mapSetName', uv_set, type='string')
        
        # 连接表面
        if shape_type == 'mesh':
            cmds.connectAttr(shape + '.outMesh', follicle + '.inputMesh')
        else:
            cmds.connectAttr(shape + '.local', follicle + '.inputSurface')
        
        cmds.connectAttr(shape + '.worldMatrix[0]', follicle + '.inputWorldMatrix')
        
        # 获取变换节点
        follicle_trans = cmds.listRelatives(follicle, p=True)
        if follicle_trans:
            follicle_trans = follicle_trans[0]
            cmds.setAttr(follicle + '.parameterU', 0.5)
            cmds.setAttr(follicle + '.parameterV', 0.5)
            
            cmds.connectAttr(follicle + '.outTranslate', follicle_trans + '.translate')
            cmds.connectAttr(follicle + '.outRotate', follicle_trans + '.rotate')
            
            # 创建父子约束（保持连接，不烘焙）
            cmds.parentConstraint(follicle_trans, follower, mo=True)
            print("✅ " + follower + " -> " + surface + " (保持约束)")
    
    print("\n完成！约束已建立，物体将实时跟随")
    print("移动 " + surface + " 测试效果")


# ============================================================
# 快速附着版本（最简单）
# ============================================================

def attach_follower():
    """
    快速附着物体到表面
    使用方法：选择表面物体，再选择要跟随的物体
    """
    sel = cmds.ls(sl=True)
    if len(sel) < 2:
        cmds.error("请选择：表面 + 跟随物体")
    
    surface = sel[0]
    followers = sel[1:]
    
    shapes = cmds.listRelatives(surface, s=True)
    if not shapes:
        cmds.error("表面没有形状节点")
    
    shape = shapes[0]
    shape_type = cmds.objectType(shape)
    
    if shape_type not in ['mesh', 'nurbsSurface']:
        cmds.error("表面必须是多边形网格(mesh)或NURBS曲面")
    
    # 清理旧的 follicle
    old_follicles = cmds.ls(type='follicle')
    if old_follicles:
        for f in old_follicles:
            try:
                cmds.delete(f)
            except:
                pass
        print("清理了旧 Follicle")
    
    for follower in followers:
        # 清除物体变换
        try:
            cmds.setAttr(follower + '.translateX', 0)
            cmds.setAttr(follower + '.translateY', 0)
            cmds.setAttr(follower + '.translateZ', 0)
            cmds.setAttr(follower + '.rotateX', 0)
            cmds.setAttr(follower + '.rotateY', 0)
            cmds.setAttr(follower + '.rotateZ', 0)
        except:
            pass
        
        # 创建 follicle
        follicle = cmds.createNode('follicle')
        
        # 获取 UV 集
        if shape_type == 'mesh':
            uv_sets = cmds.polyUVSet(surface, q=True, currentUVSet=True)
            if uv_sets:
                cmds.setAttr(follicle + '.mapSetName', uv_sets[0], type='string')
        
        # 连接表面
        if shape_type == 'mesh':
            cmds.connectAttr(shape + '.outMesh', follicle + '.inputMesh')
        else:
            cmds.connectAttr(shape + '.local', follicle + '.inputSurface')
        
        cmds.connectAttr(shape + '.worldMatrix[0]', follicle + '.inputWorldMatrix')
        
        # 获取变换
        follicle_trans = cmds.listRelatives(follicle, p=True)
        if follicle_trans:
            follicle_trans = follicle_trans[0]
            cmds.setAttr(follicle + '.parameterU', 0.5)
            cmds.setAttr(follicle + '.parameterV', 0.5)
            
            cmds.connectAttr(follicle + '.outTranslate', follicle_trans + '.translate')
            cmds.connectAttr(follicle + '.outRotate', follicle_trans + '.rotate')
            
            # 创建约束
            cmds.parentConstraint(follicle_trans, follower, mo=True)
            print("✅ " + follower + " 已附着到 " + surface)
    
    print("\n完成！移动 " + surface + " 测试效果")


# ============================================================
# 简单约束版本（仅位置跟随）
# ============================================================

def follow_simple():
    """
    最简单版本：仅位置跟随，不依赖 follicle
    使用方法：选择表面物体，再选择要跟随的物体
    """
    sel = cmds.ls(sl=True)
    if len(sel) < 2:
        cmds.error("请选择：表面物体 + 要跟随的物体")
    
    surface = sel[0]
    followers = sel[1:]
    
    for follower in followers:
        # 清除变换
        try:
            cmds.setAttr(follower + '.translateX', 0)
            cmds.setAttr(follower + '.translateY', 0)
            cmds.setAttr(follower + '.translateZ', 0)
        except:
            pass
        
        # 创建位置约束
        cmds.pointConstraint(surface, follower, mo=True)
        print("✅ " + follower + " 位置跟随 " + surface)
    
    print("\n完成！")


# ============================================================
# 工具函数：查看场景信息
# ============================================================

def scene_info():
    """查看当前场景的 follicle 和约束信息"""
    print("="*50)
    print("场景信息")
    print("="*50)
    
    follicles = cmds.ls(type='follicle')
    print("\nFollicle 节点 (" + str(len(follicles)) + " 个):")
    for f in follicles:
        u = cmds.getAttr(f + '.parameterU')
        v = cmds.getAttr(f + '.parameterV')
        trans = cmds.listRelatives(f, p=True)
        print("  " + f + "  UV=(" + str(u) + ", " + str(v) + ")  -> " + str(trans))
    
    constraints = cmds.ls(type='constraint')
    print("\n约束节点 (" + str(len(constraints)) + " 个):")
    for c in constraints:
        print("  " + c)
    
    sel = cmds.ls(sl=True)
    print("\n当前选中: " + str(sel))


# ============================================================
# 工具函数：清理场景
# ============================================================

def clean_follicles():
    """清理场景中所有 follicle 节点"""
    follicles = cmds.ls(type='follicle')
    if follicles:
        cmds.delete(follicles)
        print("已删除 " + str(len(follicles)) + " 个 Follicle")
    else:
        print("没有找到 Follicle")


# ============================================================
# 主入口
# ============================================================

if __name__ == "__main__":
    # 默认执行完整版
    # 如果需要不烘焙版本，改为 follow_skin_no_bake()
    follow_skin_full()
'''
Maya工具模块：处理IK切换控制器的关键帧
'''

import maya.cmds as mc
import sys

VALID_TANGENT_TYPES = ['spline', 'clamped', 'linear', 'flat', 'step', 'auto']

def get_min_max_attrs_to_clamp(obj):
    '''获取带有最小/最大值且已被关键帧的浮点/双精度/枚举类型属性'''
    
    obj_attrs = mc.listAttr(obj, keyable=True) or []
    attrs_to_clamp = []
    
    for attr in obj_attrs:
        is_keyed = mc.keyframe(obj + '.' + attr, query=True)
        attr_type = mc.attributeQuery(attr, node=obj, attributeType=True)
        
        if is_keyed:
            if attr_type in ['float', 'double']:
                has_min = mc.attributeQuery(attr, node=obj, minExists=True)
                has_max = mc.attributeQuery(attr, node=obj, maxExists=True)
                if has_min and has_max:
                    attrs_to_clamp.append(attr)
            elif attr_type in ['enum', 'bool']:
                attrs_to_clamp.append(attr)
    
    return attrs_to_clamp

def set_key_tangent(nodes=[], attrs=[], in_type='', out_type=''):
    '''设置指定节点属性的关键帧切线类型'''
    
    if not nodes:
        return
    
    if in_type and in_type in VALID_TANGENT_TYPES:
        mc.keyTangent(nodes, attribute=attrs, inTangentType=in_type)
    
    if out_type and out_type in VALID_TANGENT_TYPES:
        mc.keyTangent(nodes, attribute=attrs, outTangentType=out_type)

def clamp_min_max_values(nodes=[], attrs=[], min_val=0.0, max_val=1.0):
    '''将指定属性的关键帧值钳制到最小/最大范围'''
    
    if max_val < min_val:
        raise ValueError('最大值不能小于最小值')
    
    if not nodes or not attrs:
        return
    
    median = (max_val + min_val) / 2
    
    for node in nodes:
        for attr in attrs:
            if not mc.objExists(node + '.' + attr):
                continue
            
            times = mc.keyframe(node, query=True, timeChange=True, attribute=attr)
            if not times:
                continue
            
            values = mc.keyframe(node, query=True, valueChange=True, absolute=True, attribute=attr)
            
            for i in range(len(times)):
                value = min_val if values[i] < median else max_val
                mc.keyframe(node, edit=True, time=(times[i], times[i]), 
                           valueChange=value, absolute=True, attribute=attr)

def clamp_all_ik_switch_attrs():
    '''处理场景中所有IK切换控制器的关键帧'''
    
    data_node_switch_attrs = mc.ls('*.switchControl', recursive=True)
    ik_switch_controls = mc.ls('*.IKSwitch', recursive=True, objectsOnly=True)
    ik_switch_ctrls_and_attrs = {}
    
    # 通过dataNode查找IK切换控制器
    for data_node_switch_attr in data_node_switch_attrs:
        ik_switch_control = mc.listConnections(data_node_switch_attr, source=False)
        if ik_switch_control:
            ik_switch_control = ik_switch_control[0]
            attrs = get_min_max_attrs_to_clamp(ik_switch_control)
            if attrs:
                ik_switch_ctrls_and_attrs[ik_switch_control] = attrs
    
    # 直接通过IKSwitch属性查找（旧版rig）
    for ik_switch_control in ik_switch_controls:
        if ik_switch_control not in ik_switch_ctrls_and_attrs:
            attrs = get_min_max_attrs_to_clamp(ik_switch_control)
            if attrs:
                ik_switch_ctrls_and_attrs[ik_switch_control] = attrs
    
    if not ik_switch_ctrls_and_attrs:
        mc.warning('场景中未找到已设置关键帧的IK切换控制器')
        return
    
    # 处理每个控制器
    for control, attrs in ik_switch_ctrls_and_attrs.items():
        for attr in attrs:
            attr_type = mc.attributeQuery(attr, node=control, attributeType=True)
            
            # 枚举类型只处理包含0和1两个选项的
            if attr_type == 'enum':
                enum_list = mc.attributeQuery(attr, node=control, listEnum=True)
                if enum_list and len(enum_list[0].split(':')) != 2:
                    continue
            
            attr_min = mc.attributeQuery(attr, node=control, minimum=True)[0]
            attr_max = mc.attributeQuery(attr, node=control, maximum=True)[0]
            
            clamp_min_max_values([control], [attr], attr_min, attr_max)
        
        set_key_tangent([control], attrs, out_type='step')
    
    print('已处理以下IK切换控制器及其属性：')
    for control, attrs in ik_switch_ctrls_and_attrs.items():
        print('  {}: {}'.format(control, attrs))
    
    sys.stdout.write('所有已设置关键帧的IK切换控制器属性已处理完毕\n')
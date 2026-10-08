import maya.cmds as cmds
from maya.api import OpenMaya as om


def addingFlags(flagName, attrType, defValue=None, minVal=None, maxVal=None,
                keyable=True, recursive=True):
    """
    给选中的节点（可选：连同其 DAG 层级下的所有节点）添加一个自定义属性。

    flagName  : 属性名
    attrType  : double / float / long / short / byte / bool / string / enum / message / matrix ...
    defValue  : 默认值（None = 不设）
    minVal    : 最小值（仅数值类型有效，None = 不设）
    maxVal    : 最大值（仅数值类型有效，None = 不设）
    keyable   : 是否 keyable
    recursive : True = 连同层级下所有子节点都加；False = 只加在选中节点上
    """
    selected = cmds.ls(selection=True, long=True)
    if not selected:
        print("Nothing selected.")
        return

    numeric_types = {"double", "float", "long", "short", "byte",
                     "doubleAngle", "doubleLinear"}
    string_types  = {"string"}
    no_default    = {"message", "matrix", "compound",
                     "double3", "float3", "long3", "short3"}

    for nodeObj in selected:
        if not cmds.objExists(nodeObj):
            continue

        # 收集要处理的节点
        if recursive:
            # 用 Maya 命令收集层级下所有节点（比 MItDag 更省事）
            targets = cmds.listRelatives(nodeObj, allDescendents=True,
                                         fullPath=True) or []
            targets.append(nodeObj)
        else:
            targets = [nodeObj]

        for target in targets:
            if cmds.attributeQuery(flagName, node=target, exists=True):
                print("Flag '{}' already exists in {}".format(flagName, target))
                continue

            kwargs = {"longName": flagName, "keyable": keyable}

            if attrType in string_types:
                kwargs["dataType"] = "string"
                if defValue is not None:
                    kwargs["defaultValue"] = defValue
            else:
                kwargs["attributeType"] = attrType
                if attrType not in no_default and defValue is not None:
                    kwargs["defaultValue"] = defValue
                if attrType in numeric_types:
                    if minVal is not None:
                        kwargs["minValue"] = minVal
                    if maxVal is not None:
                        kwargs["maxValue"] = maxVal

            print("Adding flag '{}' to {}".format(flagName, target))
            cmds.addAttr(target, **kwargs)
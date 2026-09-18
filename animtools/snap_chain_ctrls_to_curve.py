

import maya.cmds as mc

from CharacterDefinitions import character_definitions as cd
from RigBuild import config

kratosChainsConfig = config.kratosChainsSetupDict


def snapTransformsToCVs(curve, transforms):
    points = mc.ls(curve + '.controlPoints[:]', flatten=True)

    if len(points) - 2 != len(transforms):
        mc.error('wrong number of CVs and controls, should have [CVs - 2 = Transforms]')
        return False

    for i in range(1, len(points)-1, 1):
        if mc.objExists(transforms[i - 1]):
            loc = mc.xform(points[i], q=True, ws=True, t=True)
            mc.undoInfo(swf=0)
            mc.xform(transforms[i - 1], ws=True, absolute=True, translation=loc)
            mc.undoInfo(swf=1)
        else:
            mc.warning('%s does not have corresponding transform') % points[i]


def doIt(dataNode, setKey=False):
    data = cd.KratosChain(dataNode)

    # Get shape of rebuilt curve.
    rebuiltCurveShape = mc.listRelatives(data.rebuiltCurve, type='nurbsCurve')[0]

    # Snap middle controls to CVs.
    snapTransformsToCVs(rebuiltCurveShape, data.hiResControls)

    if setKey:
        mc.setKeyframe(data.hiResControls, attribute=('tx', 'ty', 'tz'))


def main(setKey=False):
    dataNodes = []
    chainDataType = kratosChainsConfig['DataType']

    for sel in mc.ls(sl=True):
        dataNode = cd.getDataParent(sel)
        if not dataNode:
            continue

        data = cd.Data(dataNode)
        if not data.dataType:
            continue

        if data.dataType == 'weapon':
            childDataNode = cd.getDataChild(dataNode, dataType=chainDataType)
            if childDataNode and dataNode not in dataNodes:
                dataNodes.append(childDataNode)
        elif data.dataType == kratosChainsConfig['DataType']:
            if dataNode not in dataNodes:
                dataNodes.append(dataNode)
        elif data.dataType == 'Chain':
            if dataNode not in dataNodes:
                dataNodes.append(dataNode)

    for temp in dataNodes:
        print(temp)
        doIt(temp, setKey=setKey)

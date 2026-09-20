
import math
import os
import time
import traceback

import maya.api.OpenMaya as OpenMaya
import maya.cmds as mc

import dag as dagUtils;
import toggle_maya_ui
import importlib

importlib.reload(dagUtils)
import rig as rigUtils;
import attributes as attrUtils;
import character_definitions as cd

importlib.reload(rigUtils)

import snap_chain_ctrls_to_curve
importlib.reload(snap_chain_ctrls_to_curve)

import iterateToZero as itz
importlib.reload(itz)

import ikfk_match_ribbon
importlib.reload(ikfk_match_ribbon)


def run(key=False, snap=False, playbackRange=False, subCtrlSnap=False):
    '''
    :param key: set to True will run for all keys on the playback range
    :param snap: set to True will keep the IK switch in the same space (IK or FK ) , False will switch the value
    :param playbackRange: evaluates only the playback range - False operates on the full animation curve
    :param subCtrlSnap: if True - additional controls (like movable knee/elbow) are snapped to their markers,
        False means they will simply be zeroed out
    :return: True if successful
    '''

    currentTime = mc.currentTime(q=True)

    startTime = time.perf_counter()
    sel = mc.ls(sl=True)

    if len(sel) < 1:
        mc.warning('Select character control(s) first')
        return False

    # Do not run code on one off controls like ToeTipIk control (int10 devourer00)
    # Redefine sel as only validSels after filtering out one-off controls.
    validSels = []
    for obj in sel:
        userDefinedAttrs = mc.listAttr(obj, userDefined=True) or []
        if 'oneOffControl' not in userDefinedAttrs:
            validSels.append(obj)
        else:
            mc.warning(f'{obj} will be skipped because it is a one-off unofficial control.')
    if validSels:
        sel = validSels
    else:
        mc.warning('Select at least one official control of an IK system.')
        return False

    # call the RibbonIkFkMatch module if ribbonIkFkMatch attr exists on the first selection
    if mc.objExists(sel[0] + '.ribbonIkFkMatch'):
        return ikfk_match_ribbon.RibbonIkFkMatch(key, snap, playbackRange).run()

    # split the selections into namespace groups and operate on those
    selNamespaces = {}
    for node in sel:
        ns = dagUtils.getNamespace(node, asList=True)[0]
        if not ns in selNamespaces:
            selNamespaces[ns] = []
        selNamespaces[ns].append(node)
    # print 'the Sel namespaces are', selNamespaces

    emMode = mc.evaluationManager(q=True, mode=True)[0]
    newSel = []
    for selNS in selNamespaces:

        oppositeSystemControls = []

        try:
            # turning off Parallel DG temporarily to avoid a nasty crash in Maya 2018.5
            if key:
                mc.evaluationManager(mode='off')

            mc.undoInfo(openChunk=True)
            autoKeyState = mc.autoKeyframe(q=True, state=True)
            mc.autoKeyframe(e=True, state=False)

            thisSel = selNamespaces[selNS]

            if mc.objExists(thisSel[0] + '.IKSwitch'):
                if mc.objExists(thisSel[0] + '.switchControlMessage'):
                    controls = mc.listConnections(thisSel[0] + '.switchControlMessage', d=True, s=False, scn=True)
                    if len(controls) > 1:
                        if mc.getAttr(thisSel[0] + '.IKSwitch') < .5:
                            for ctrl in controls:
                                if not ctrl.find('FKControl') > -1:
                                    thisSel[0] = ctrl
                                    break
                        else:
                            for ctrl in controls:
                                if not ctrl.find('FKControl') > -1:
                                    thisSel[0] = ctrl
                                    break

            if key:
                toggle_maya_ui.toggleMayaUI(False)
                oppositeSystemControls = doKeyAllIKFK(thisSel, keepSwitch=snap, playback=playbackRange, key=key,
                                                      subSnap=subCtrlSnap)
            else:
                if autoKeyState is True:
                    key = True
                oppositeSystemControls = doIkFkSwitch(thisSel, keepSwitch=snap, key=key, subSnap=subCtrlSnap)
        except:
            traceback.print_exc()
            mc.warning('IKFK switch failed')
        finally:
            mc.autoKeyframe(e=True, state=autoKeyState)
            if key:
                mc.currentTime(currentTime)
                toggle_maya_ui.toggleMayaUI(True)

            # select the opposing system controller or reselect selection (in case of non-system sel)
            selSystems = sel
            if oppositeSystemControls is not False:
                selSystems = list(set(oppositeSystemControls) & set(sel))

            if len(selSystems) > 0 and snap is False:
                selFlip = []
                for node in selSystems:
                    if mc.attributeQuery('IkFkSwitchMessage', node=node, exists=1) == True:
                        otherNode = mc.listConnections(node + '.IkFkSwitchMessage')
                        if otherNode:
                            selFlip.append(otherNode[0])

                if len(selFlip):
                    mc.select(selFlip, r=True)
            else:
                mc.select(sel)

            mc.undoInfo(closeChunk=True)

            print(time.perf_counter() - startTime)

            # doing this to avoid a nasty crash in Maya 2018.5
            if key:
                mc.evaluationManager(mode=emMode)

        newSel.extend(mc.ls(sl=True))

    mc.select(newSel)

    return True


def matchTransform(marker, control):
    zLegPV = False
    if mc.objExists(marker + '.ZLegAngleBuffer'):
        angleBuffer = mc.listConnections(marker + '.ZLegAngleBuffer', d=True, s=False, scn=True)
        if angleBuffer:
            itz.main(control + '.rotateY', angleBuffer[0] + '.angle', angleBuffer[0] + '.angle', attrCycle=None)
            zLegPV = True

        if mc.objExists(marker + '.ZLegPVScaleResultant'):
            scaleRes = mc.listConnections(marker + '.ZLegPVScaleResultant', d=True, s=False, scn=True)
            if scaleRes:
                scaleRes = scaleRes[0]
                mc.setAttr(control + '.scaleX', mc.getAttr(scaleRes + '.scaleX'))
                mc.setAttr(control + '.scaleZ', mc.getAttr(scaleRes + '.scaleZ'))
        return

    matrix = OpenMaya.MMatrix(mc.getAttr(marker + '.worldMatrix'))
    parentInverse = OpenMaya.MMatrix(mc.getAttr(control + '.parentInverseMatrix'))

    result = matrix * parentInverse

    mc.xform(control, os=True, matrix=result)

    return True


def oldRigCheck(control):
    oldRig = False
    temp = dagUtils.getTopNodesFromNodes(control)
    topNode = temp[control][0]
    if mc.objExists(topNode + '.characterLocation'):
        location = mc.getAttr(topNode + '.characterLocation')
        if location is not None and len(location) > 0:
            location = os.path.normpath(location)
            parts = location.split('\\')
            if parts[1].startswith('int'):
                projNum = int(parts[1].replace('int', ''))
                if projNum < 6:
                    oldRig = True
    return oldRig


def getKratosChains(topNode):
    systemControls = {}

    sel = mc.ls(sl=True)
    namespaces = dagUtils.getNamespace(topNode, asList=True)
    namespace = ''
    if namespaces[0] is not None:
        namespaces[0] += ':'

    chainSwitchers = mc.ls(namespace + '*.chainCtrls', objectsOnly=True, recursive=True)
    # print 'chain switchers', chainSwitchers

    selChainNodes = []
    for switcher in chainSwitchers:
        for boolean in (True, False):
            thisControl = switcher
            while thisControl is not None:
                thisControl = mc.listConnections(thisControl + '.IkFkChildParentMessage', d=boolean, s=1 - boolean,
                                                 scn=True)
                if thisControl:
                    if thisControl[0] in sel:
                        selChainNodes.append(thisControl[0])
                    thisControl = thisControl[0]

    # print 'the sel chain nodes are', selChainNodes

    # hunt down the switchers - objects with "chainCtrls" attr
    chainCtrls = []
    for chainControl in selChainNodes:
        for boolean in (True, False):
            thisControl = chainControl
            while thisControl is not None:
                if mc.objExists(thisControl + '.chainCtrls') and thisControl not in systemControls:
                    systemControls[thisControl] = []
                    break

                thisControl = mc.listConnections(thisControl + '.IkFkChildParentMessage', d=boolean, s=1 - boolean,
                                                 scn=True)
                if thisControl:
                    thisControl = thisControl[0]

    # now that we have the switchers - collect the per switcher controls
    for switcher in systemControls:
        for boolean in (True, False):
            thisControl = switcher
            while thisControl is not None:
                thisControl = mc.listConnections(thisControl + '.IkFkChildParentMessage', d=boolean, s=1 - boolean,
                                                 scn=True)
                if thisControl:
                    if thisControl[0] not in chainCtrls:
                        systemControls[switcher].append(thisControl[0])
                    thisControl = thisControl[0]

    return systemControls


def getOpposites(topControl):
    ''' gets either the IK from the FK or vice versa '''
    thisControl = None
    if mc.objExists(topControl + '.IkFkSwitchMessage'):
        temp = mc.listConnections(topControl + '.IkFkSwitchMessage')
        if temp:
            thisControl = temp[0]
        else:
            return [], ''
    else:
        return [], ''

    systemControls = [thisControl]

    ikSwitch = None
    if mc.objExists(thisControl + '.switchControlMessage'):
        ikSwitch = mc.listConnections(thisControl + '.switchControlMessage', d=False, s=True, scn=True)[0]
    else:
        ikSwitch = mc.listConnections(topControl + '.switchControlMessage', d=False, s=True, scn=True)[0]

    while thisControl is not None:
        thisControl = mc.listConnections(thisControl + '.IkFkChildParentMessage', d=True, s=False, scn=True)
        if thisControl:
            systemControls.append(thisControl[0])
            thisControl = thisControl[0]

    return systemControls, ikSwitch


def getCameraNodes(sel):
    cameraNodes = []
    for aStr in ('*CameraFreeControl*', '*CameraAimControl*', '*CameraGimbalControl*', '*CameraSwitchControl*'):
        cameraNodes.extend(mc.ls(aStr, recursive=True, objectsOnly=True, type='transform'))
    theseNodes = []
    for node in sel:
        if node in cameraNodes:
            theseNodes.append(node)
    return theseNodes


def getSystemControls(sel):
    # Start timer to remember total bake time.
    totalTime = mc.timerX()

    oldRig = oldRigCheck(sel[0])
    temp = dagUtils.getTopNodesFromNodes(sel[0])
    topNode = temp[sel[0]][0]

    namespaces = dagUtils.getNamespace(sel, asList=True, asString=False)

    totalTimeB = mc.timerX()
    tempIKSystems = rigUtils.getIKSystems(namespaces=namespaces)
    totalTimeB = mc.timerX(startTime=totalTimeB)
    # print 'Rig Systems Gather Took', totalTimeB
    # print 'te TEMP Ik systems are', tempIKSystems

    topNodeNS = dagUtils.getNamespace(topNode, asList=True)[0]
    # print 'the namespace is ', topNodeNS

    chainSystems = getKratosChains(topNode)
    # print 'the chain systems are', chainSystems

    # from all the scenes ik systems get those that share a top node with our selection
    ikSystems = []
    for system in tempIKSystems:

        temp = dagUtils.getTopNodesFromNodes(system[0])
        # print' teh TEMP top node is', temp

        thisTopNode = temp[system[0]][0]
        # print 'Checkign this top node', thisTopNode

        # if the namespace of thisTopNode matches namespace of topNode
        thisTopNodeNS = dagUtils.getNamespace(thisTopNode, asList=True)[0]

        if thisTopNodeNS == topNodeNS:
            ikSystems.append(system)
            if mc.objExists(system[0] + '.switchControlMessage'):
                switcher = mc.listConnections(system[0] + '.switchControlMessage', s=True, d=False, scn=True) or None
                if switcher:
                    # system.append(switcher[0])
                    ikSystems[-1].append(switcher[0])

    # print 'the IK Systems are', ikSystems

    # determine if we are going to operate on every system or just the actively selected system
    validControls = []
    for system in ikSystems:
        for node in sel:

            if not mc.objExists(node + '.IkFkSwitchMessage'):
                continue

            otherControl = mc.listConnections(node + '.IkFkSwitchMessage', s=True, d=False, scn=True)

            if node in system:
                validControls.append(system[0])
            elif otherControl:
                if otherControl[0] in system:
                    validControls.append(system[0])

    # print 'the Valid controls first check is %s' %validControls

    # check for selected camera
    validControls.extend(getCameraNodes(sel))

    # if no valid systems from selection we will operate on all of them
    if len(validControls) == 0 and len(list(chainSystems.keys())) < 1:
        for system in ikSystems:
            validControls.append(system[0])

    allSystemControls = []
    for control in validControls:
        if not mc.objExists(control + '.IkFkSwitchMessage'):
            mc.warning('Control is not normal IK/FK system, checking for camera attrs')

            if not mc.objExists(control + '.switchGroupMessage'):
                mc.warning('Please select a control that is part of an IK/FK system')
                # toggle_maya_ui.toggleMayaUI(True)
                # return False
                continue
            else:
                topControl = control
                namespace = topControl.split(':')[0]

                cameraControls = [namespace + ':CameraFreeControl1', namespace + ':CameraAimControl1',
                                  namespace + ':CameraGimbalControl1']

                thisControl = mc.listConnections(topControl + '.switchGroupMessage')[0]
                ikSwitch = mc.listConnections(thisControl + '.switchAttributeMessage', d=False, s=True, scn=True)[0]
                systemControls = mc.listConnections(ikSwitch + '.pwSwitcherRight')
                systemControls.remove(topControl)

                if namespace + ':CameraAimControl1' == systemControls[0] or namespace + ':CameraAimControl1' == \
                        systemControls[1]:
                    systemControls.append(namespace + ':AimControl1')
                    systemControls.append(namespace + ':UpVectorControl1')

                oppositeSystemControls = list(set(cameraControls) - set(systemControls))
        else:
            topControl = control
            while mc.objExists(topControl + '.IkFkChildParentMessage'):
                try:
                    topControl = \
                        mc.listConnections(topControl + '.IkFkChildParentMessage', source=True, destination=False)[0]
                except:
                    break

            if oldRig is True:
                topControl = mc.listConnections(topControl + '.IkFkChildParentMessage', source=False, destination=True)[
                    0]

            # print 'the TOP control is', topControl

            systemControls, ikSwitch = getOpposites(topControl)
            systemControls.append(ikSwitch)
            # print 'teh system controls are', systemControls
            oppositeSystemControls, ikSwitch = getOpposites(systemControls[0])
            oppositeSystemControls.append(ikSwitch)
            # print 'tjhe opposite systme controls are', oppositeSystemControls

        allSystemControls.append([systemControls, oppositeSystemControls, ikSwitch])
        # print 'all the system controls are %s' %allSystemControls

    if len(chainSystems) and len(validControls) == 0:
        for switcher in chainSystems:
            allSystemControls.append([chainSystems[switcher], [], switcher])

    totalTime = mc.timerX(startTime=totalTime)
    # print 'GEL SEL CONTROLS Took', totalTime

    return allSystemControls


def doKeyAllIKFK(sel, keepSwitch=False, playback=False, key=True, subSnap=True):
    if not isinstance(sel, list):
        sel = [sel]

    timeMin = mc.playbackOptions(q=True, min=True)
    timeMax = mc.playbackOptions(q=True, max=True)

    ctrlData = getSystemControls(sel)
    # print 'the control data is %s' %ctrlData

    if not ctrlData:
        mc.warning('Please select a control that is part of an IK/FK system')
        toggle_maya_ui.toggleMayaUI(True)
        return False

    # collect IK FK systems per frame
    everyControl = []
    keyTimes = {}
    for data in ctrlData:
        # print 'Doing data %s' %data

        systemControls, oppositeSystemControls, ikSwitch = data

        allSystemControls = systemControls[:]
        allSystemControls.extend(oppositeSystemControls)

        everyControl.extend(allSystemControls)

        for ctrl in allSystemControls:
            # ctrlKeys = mc.keyframe(ctrl, q=True, time=(timeMin,timeMax), tc=True)
            ctrlKeys = mc.keyframe(ctrl, q=True, tc=True)

            if not ctrlKeys:
                continue

            for frame in ctrlKeys:

                if playback is True and (frame < timeMin or frame > timeMax):
                    continue

                if not frame in keyTimes:
                    keyTimes[frame] = []
                if not data in keyTimes[frame]:
                    keyTimes[frame].append(data)

    opposingControls = []

    for aTime in sorted(keyTimes.keys()):
        # print aTime, keyTimes[aTime]
        mc.currentTime(aTime)

        # perform the switch on all systems for this frame
        oppositeSystemControls = doIkFkSwitch(sel, keepSwitch=keepSwitch, ctrlData=keyTimes[aTime], key=key,
                                              subSnap=subSnap)
        opposingControls.extend(oppositeSystemControls)

    mc.filterCurve(everyControl, filter='euler')

    return opposingControls


def doIkFkSwitch(sel, keepSwitch=False, ctrlData=None, key=False, subSnap=False):
    if ctrlData is None:
        ctrlData = getSystemControls(sel)
        # print 'THE CTRL DATA is', ctrlData

    if not ctrlData:
        toggle_maya_ui.toggleMayaUI(True)
        mc.warning('Please select a control that is part of an IK/FK system')
        return False

    oppositeSystemControls = []
    for data in ctrlData:
        marker = None
        ikCtrls, fkCtrls, ikSwitch = data

        # Find the main ikSwitch, at the start of the dependancy graph for this current ikSwitch.IKSwitch
        if mc.attributeQuery('IKSwitch',  node=ikSwitch, exists=True) and not mc.getAttr(ikSwitch + '.IKSwitch', settable=True):
            tempSrcObj = mc.listConnections(ikSwitch + '.IKSwitch', s=True, d=False, type='transform')
            while tempSrcObj:
                srcObj = mc.listConnections(tempSrcObj[0] + '.IKSwitch', s=True, d=False, type='transform')
                if srcObj:
                    tempSrcObj = srcObj
                else:
                    ikSwitch = tempSrcObj[0]
                    break

        # Look to see if there are chained IK/FK Switches
        # if there are, add the controls from their system
        testedSwitches = []
        if mc.objExists(ikSwitch + '.IKSwitch'):
            connections = mc.listConnections(ikSwitch + '.IKSwitch', s=True, d=True, type='transform')
            if connections:
                connections = [i for i in connections if mc.objExists(i + '.IKSwitch')] or None
                while connections:
                    # Loop through the ikSwitches
                    for nextSwitch in connections:
                        if mc.attributeQuery('switchControlMessage', node=nextSwitch, exists=True):
                            thisCtrl = mc.listConnections(nextSwitch + '.switchControlMessage', d=True, s=False)
                            if thisCtrl:
                                otherCtrlData = getSystemControls([thisCtrl[0]])[0]
                                ikCtrls.extend(otherCtrlData[0])
                                fkCtrls.extend(otherCtrlData[1])

                        testedSwitches.append(nextSwitch)

                        connections = mc.listConnections(nextSwitch + '.IKSwitch', s=True, d=True, type='transform')
                        connections = list(set(connections) - set(testedSwitches))
                        connections = [i for i in connections if mc.objExists(i + '.IKSwitch')]

                        if connections is None:
                            break

        systemControls = ikCtrls
        theseOpposingControls = fkCtrls
        if mc.objExists(ikSwitch + '.IKSwitch'):
            if mc.getAttr(ikSwitch + '.IKSwitch') < .5:
                systemControls = fkCtrls
                theseOpposingControls = ikCtrls
        oppositeSystemControls.extend(theseOpposingControls)

        # sort FK controls in case of multiple systems chained via IKSwitcher.IKSwitch attribute
        if mc.objExists(ikSwitch+'.IKSwitch') and mc.getAttr(ikSwitch + '.IKSwitch') < .5:
            oppositeSystemControls = dagUtils.sortHierarchical(oppositeSystemControls)

        # detect a scale value over/under 1.0
        scaled = False
        for node in oppositeSystemControls:
            if mc.objExists(node + '.scale'):
                for value in mc.getAttr(node + '.scale')[0]:
                    if math.fabs(1.0 - math.fabs(value)) > 0.0001:
                        scaled = True
                        break

        # if going from FK to IK - zero out foot controls user-defined attrs
        if mc.objExists(ikSwitch + '.IKSwitch'):
            if mc.getAttr(ikSwitch + '.IKSwitch') < .5:
                if scaled:
                    if mc.objExists(ikSwitch + '.stretchBlend') and scaled is True:
                        mc.setAttr(ikSwitch + '.stretchBlend', 1.0)

                    if mc.objExists(ikSwitch + '.lengthVolume') and scaled is True:
                        mc.setAttr(ikSwitch + '.lengthVolume', 0.0)

                for node in systemControls:
                    if node.find('FootControl') > -1:
                        for attr in ['metPivot', 'ballPivot', 'toeWiggle', 'toeLift', 'toeTwist', 'metaRoll',
                                     'MetaRoll', 'ballTwist']:
                            if mc.objExists(node + '.' + attr):
                                mc.setAttr(node + '.' + attr, 0.0)

                        # Detect and zero out rotation on ToeTipIKControl on this ikSwitch associated leg rig
                        #  *ToeTipIKControl is a custom control for int10 devourer00
                        legDataNode = cd.getDataParent(ikSwitch)
                        dataToeTipIK = cd.getDataChild(legDataNode, dataType='toeTipIK')
                        if dataToeTipIK:
                            print('\n\ndataToeTipIK detected, zeroing out rotations for its control.')
                            toeTipIKCtrl = cd.getObjectFromDataAttr(dataToeTipIK, 'toeTipIK')
                            attrUtils.setObjsAttrs([toeTipIKCtrl], ['rotateX', 'rotateY', 'rotateZ'], value=0)

                        break
            else:
                for node in oppositeSystemControls:
                    if node.find('SubIKControl') > -1 and subSnap is False:
                        try:
                            # print 'zeroing out %s' %node
                            for tAttr in ('tx', 'ty', 'tz'):
                                mc.setAttr(node + '.' + tAttr, 0)
                            for sAttr in ('sx', 'sz'):
                                mc.setAttr(node + '.' + sAttr, 1.0)
                        except:
                            traceback.print_exc()
                            mc.warning('Could not reset %s before switching to FK') % node

        # if this is a kratos chain system - do something unique for this and skip the regular stuff
        if mc.objExists(ikSwitch + '.chainCtrls'):
            mc.select(ikCtrls[3])
            snap_chain_ctrls_to_curve.main(setKey=True)

            if keepSwitch is False:
                chainSwitchValue = mc.getAttr(ikSwitch + '.chainCtrls')
                chainSwitchValue = max(min(chainSwitchValue, 1.0), 0.0)
                chainSwitchValue = 1.0 - chainSwitchValue
                try:
                    mc.setAttr(ikSwitch + '.chainCtrls', chainSwitchValue)
                except:
                    traceback.print_exc()
                    mc.warning('Could not set IK switch on %s') % ikSwitch + '.chainCtrls'
            continue

        for node in systemControls:
            if not mc.objExists(node + '.IkFkSwitchMessage') and not mc.objExists(
                    node + '.switchGroupMessage') and not mc.objExists(node + '.IkFkChildParentMessage'):
                continue
            if mc.objExists(node + '.IkFkSwitchMessage'):
                marker = mc.listConnections(node + '.markerMessage', d=True, s=False, scn=True)
                if marker is None:
                    continue
            else:
                markers = mc.listConnections(sel[0] + '.markerModeMessage', s=1)
                if markers is None:
                    continue
                for each in markers:
                    if mc.listConnections(each + '.markerMessage', d=True)[0] == node:
                        marker = [each]

            # print '....................> Matching %s to %s' %(marker[0], node)
            matchTransform(marker[0], node)

            # Copy user-defined attribute values.
            udAttrs = mc.listAttr(marker[0], userDefined=True, keyable=True, visible=True, unlocked=True) or []
            for attr in udAttrs:
                if mc.objExists(marker[0] + '.' + attr):
                    try:
                        mc.setAttr(node + '.' + attr, mc.getAttr(marker[0] + '.' + attr))
                    except:
                        continue

        if mc.objExists(ikSwitch + '.IKSwitch') and keepSwitch is False:
            if not mc.getAttr(ikSwitch + '.IKSwitch', lock=True):
                switchValue = mc.getAttr(ikSwitch + '.IKSwitch')
                switchValue = max(min(switchValue, 1.0), 0.0)
                switchValue = 1.0 - switchValue
                try:
                    if rigUtils.animInputTypeCheck(ikSwitch + '.IKSwitch'):
                        mc.setAttr(ikSwitch + '.IKSwitch', switchValue)
                except:
                    traceback.print_exc()
                    mc.warning('Could not set IK switch on %s') % ikSwitch + '.IKSwitch'

        if key:
            # key the switcher
            for attr in ('IKSwitch', 'chainCtrls'):
                if mc.objExists(ikSwitch + '.' + attr):
                    mc.setKeyframe(ikSwitch + '.' + attr)
                    break

            # key the switched ik or fk system
            mc.setKeyframe(systemControls)

    return oppositeSystemControls

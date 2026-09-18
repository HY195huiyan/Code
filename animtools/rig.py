
import sys

import character_definitions as cd
import dag as dagUtils
import maya.cmds as mc
import mesh as meshUtils
from RigBuild import config
import importlib

importlib.reload(dagUtils)


SKIP_ATTRS = ['IKPlanted', 'visibility', 'IKSwitch', 'controlVisibility', 'thighTwistIntrpType', 'legAutoTwist',
                 'thighAutoTwist', 'armAutoTwist', 'forearmAutoTwist', 'forearmTwistIntrpType',
                 'shoulderTwistIntrpType']


def getBakeNodes(precisionBake: bool = False) -> list[str]:
    """Return scene nodes participating in bake/inject based on presence of the `_bake` attr.

    This is a lightweight discovery method used for Scene-mode boundary checks before running the
    expensive bake (bake.doBake).

    Args:
        precisionBake: If True, only return nodes where `<node>._bake` evaluates True.
                       If False, return nodes that simply have the attribute.

    Returns:
        List of node names (unique, in scene order).
    """
    plugs = mc.ls("*._bake") or []
    nodes: list[str] = []
    seen = set()

    for plug in plugs:
        node = plug.split(".", 1)[0]
        if not node or node in seen:
            continue
        if precisionBake:
            try:
                if not bool(mc.getAttr(f"{node}._bake")):
                    continue
            except Exception:
                continue
        seen.add(node)
        nodes.append(node)

    return nodes

def zeroControl(ctrl, direction=1):

    def setAndMuteAttr(controlAndAttr, value):
        if not mc.getAttr(controlAndAttr, settable=True):
            return False
        try:
            mc.setAttr(controlAndAttr, value)
            mc.mute(controlAndAttr)
        except Exception:
            return False
        return True

    global SKIP_ATTRS

    keyable = mc.listAttr(ctrl, keyable=True, unlocked=True, visible=True)
    userDefined = mc.listAttr(ctrl, ud=True)

    if keyable and userDefined:
        userDefined = list(set(keyable) & set(userDefined))

    if keyable:
        for attr in keyable:
            # Skip blade control enum attrs.
            if ctrl.lower().find('bladecontrol1') > -1 and mc.getAttr(ctrl + '.' + attr, type=True) == 'enum':
                continue

            # Set keyframes on keyable attrs that have no keys for source character.
            if direction == 0:
                keyCount = mc.keyframe(ctrl + '.' + attr, q=True, keyframeCount=True)
                if keyCount < 1:
                    try:
                        animLayers = mc.ls(type='animLayer')
                        rootLayer = mc.animLayer(q=True, root=True)
                        if rootLayer:
                            if rootLayer in animLayers:
                                animLayers.remove(rootLayer)

                        if not animLayers:
                            if not mc.getAttr(ctrl + '.' + attr, lock=True):
                                mc.setKeyframe(ctrl + '.' + attr, time=0.0)

                    except Exception as e:
                        print(("Exception {}".format(e)))

            if attr not in SKIP_ATTRS:
                if attr.find('scale') > -1:
                    setAndMuteAttr(ctrl + '.' + attr, 1.0)
                else:
                    if attr not in userDefined or attr in ['toeLift', 'ballPivot', 'ballTwist']:
                        setAndMuteAttr(ctrl + '.' + attr, 0.0)
    return True


def zeroControls(topNode):
    controls = getControls(topNode)
    for ctrl in controls:
        ctrlParent = mc.listRelatives(ctrl, parent=True)
        if ctrlParent:
            if ctrlParent[0].find('PinCushion') > -1:
                zeroControl(ctrlParent[0])
        zeroControl(ctrl)

def unmuteControls(topNode):

    global SKIP_ATTRS

    controls = getControls(topNode)
    for ctrl in controls:
        keyable = mc.listAttr(ctrl, keyable=True, unlocked=True, visible=True)
        if not keyable:
            continue

        for attr in keyable:
            if attr in SKIP_ATTRS:
                continue
            try:
                mc.mute(ctrl + '.' + attr, disable=True)
            except Exception as e:
                print('Exception occurred:', e)


def sortControlsByHierPath(charName):
    """For any character specified, sort all the hier-path controls"""

    topNodes = getCharTopNodes(charName)

    allTopNodes = [topNodes[0]]
    if topNodes[1]:
        allTopNodes.append(topNodes[1])
    allTopNodes.extend(topNodes[2])

    topControls = []
    for topNode in allTopNodes:
        topControls.extend(returnTopHierPathControls(topNode))
    hierObjs = topControls[:]
    hier = hierObjs[:]
    while hierObjs:
        temp = mc.listConnections(hierObjs.pop(0) + '.hierarchyPath', d=True, s=False, scn=True) or []
        temp = list(set(temp) - set(hierObjs))
        hierObjs.extend(temp)
        hier.extend(temp)

    return hier


def returnTopHierPathControls(topNode):
    """ Returns all top start-of-the-road hierarchyPath/multiPoseRigControl controls. """

    objs = mc.ls('*.' + config.returnToPoseDict['HierPathAttr'], r=True, objectsOnly=True, long=True)
    objs = [obj for obj in objs if obj.startswith('|' + topNode)]
    if not objs:
        return []

    topControls = []
    for obj in dagUtils.sortHierarchical(objs, longName=True):
        if not mc.listConnections(obj + '.' + config.returnToPoseDict['HierPathAttr'], s=True, d=False):
            topControls.append(mc.ls(obj)[0])

    return topControls


def getCharTopNodes(charName):
    """ returns a list of three items: coreRig, mesh-LOD, list of subRigs """

    topNodes = mc.ls(assemblies=True)

    coreRig = None
    meshLODTopNode = None
    subRigTopNodes = []

    references = mc.ls(type='reference')

    for ref in references:
        #print('testing ref node', ref)
        if '_UNKNOWN_REF_NODE_' in ref or 'sharedReferenceNode' in ref:
            continue
        try:
            if not mc.referenceQuery(ref, isLoaded=True):
                continue
        except:
            continue

        try:
            namespace = mc.referenceQuery(ref, namespace=True)[1:]
        except:
            continue

        if charName in ('None', None):
            continue

        if namespace != charName:
            continue

        nodes = mc.referenceQuery(ref, nodes=True)
        refTopNodes = list(set(topNodes) & set(nodes))

        if mc.objExists(ref + '.rigAddOns'):
            coreRig = dagUtils.getNodeWithMostChildren(refTopNodes)
        elif mc.objExists(ref + '.rigParent') and not mc.objExists(ref + '.subRig'):
            meshLODTopNode = dagUtils.getNodeWithMostChildren(refTopNodes)
        elif mc.objExists(ref + '.rigParent') and mc.objExists(ref + '.subRig'):
            subRigTopNodes.append(dagUtils.getNodeWithMostChildren(refTopNodes))
        else:
            coreRig = dagUtils.getNodeWithMostChildren(refTopNodes)

    # if nothing was found, and the charName is not an existing object - take top node that starts w/ charName
    if coreRig is None and not mc.objExists(charName):
        stringMatches = []
        for top in topNodes:
            if top.startswith(charName):
                stringMatches.append(top)

        coreRig = dagUtils.getNodeWithMostChildren(stringMatches)

    elif mc.objExists(charName):
        coreRig = charName

    return [coreRig, meshLODTopNode, subRigTopNodes]


def removeFromListByName(controls, strSearch='Slider', attrSearch=None):
    """ creates two lists from one by separating those that match a string or attribute search """

    popped = []
    for ctrl in controls[:]:
        if ctrl.find(strSearch) > -1 and not attrSearch:
            popped.append(controls.pop(controls.index(ctrl)))
        elif attrSearch:
            if mc.attributeQuery(attrSearch, node=ctrl, exists=True):
                popped.append(controls.pop(controls.index(ctrl)))
    if popped:
        popped = dagUtils.sortHierarchical(popped)
    return controls, popped


def getControls(charName, includeSliders=True):
    """
    SMS standard function for returning rig controls
    returns list of controllers as hier ordered list from char top nodes: core rig, meshLOD, subRigs
    :param charName: ordered search priority -> namespace, transform, or start string match
    :param includeSliders: bool
    :return: properly sorted list of controls
    """

    topNodes = getCharTopNodes(charName)
    if not topNodes[0]:
        return []

    controls = []

    for topNode in topNodes:
        allChildren = mc.listRelatives(topNode, ad=True, type='transform', f=True)
        if not allChildren:
            continue
        theseControls = [ctrl for ctrl in allChildren if
                         mc.objExists(ctrl + '.controlType') or mc.objExists(ctrl + '.faceTweaker')]

        if theseControls:
            theseControls = dagUtils.sortHierarchical(theseControls, longName=True)
            controls.extend(theseControls)

    if not controls:
        return []

    # separate out sliders, fingers and weapons w/out disrupting order
    controls, sliders = removeFromListByName(controls, strSearch='Slider')
    if not includeSliders:
        sliders = []
    controls, fingers = removeFromListByName(controls, attrSearch='fingerGroup')
    controls, weaponControls = removeFromListByName(controls, strSearch='WeaponControl')

    # reset the ordering
    controls = sliders + controls + fingers + weaponControls

    # order the controllers by hierarchPath attribute and move to front of list
    hierPathControls = sortControlsByHierPath(charName)
    for ctrl in controls[:]:
        if ctrl in hierPathControls:
            controls.pop(controls.index(ctrl))
    controls = hierPathControls + controls

    # re-slot the ik contorllers in so that they are in proper order
    ikControls = list(set(controls) & set(getIKControls(charName)))
    ikControls = getIKSystems(ikControls=ikControls)
    # print 'The ik controls are %s' %ikControls

    # case of 'Sub-IK controls' - every other ik control should be swapped
    for ikSystem in ikControls:
        if ikSystem[0] in controls:
            index = controls.index(ikSystem[0])
            controls = [k for k in controls if k not in ikSystem]
            for i, ik in enumerate(ikSystem):
                controls.insert(index + i, ik)

    # slot in 'RootControl' at the very top - case of (old rigs)
    namespace = ''
    if ':' in controls[0]:
        namespace = controls[0].split(':', 1)[0] + ':'
    rootControl = namespace + 'RootControl1'
    if mc.objExists(rootControl) and rootControl not in controls:
        controls.insert(0, rootControl)

    # remove long names and set to shortest-available
    finalControls = []
    for control in mc.ls(controls):
        if control not in finalControls and mc.listRelatives(control, shapes=True) or mc.objExists(
                control + '.faceTweaker'):
            finalControls.append(control)

    return finalControls


def sortHierByResultants(topNode, controls):
    """#order by hierarchy - use resultants
     more accurate as to true location in hierarchy?"""

    descendants = mc.listRelatives(topNode, ad=1, ni=True, type='transform')
    descendantControls = list(set(controls) & set(descendants))

    resultants = {}
    for control in descendantControls:
        temp = cd.getControlResultantAndDrivers(control)

        if mc.objExists(temp[0]):
            resultants[control] = temp[0]
        else:
            resultants[control] = control

    remainder = list(set(resultants.keys()) - set(descendants))
    descendants.extend(remainder)
    theseControls = sorted(list(resultants.keys()), key=lambda x: descendants.index(resultants[x]), reverse=True)

    return theseControls


def isConstrained(node):
    """ checks if the node is being controlled by a constraint """

    allCons = mc.ls(type='constraint', l=True)
    children = mc.listRelatives(node, c=True, f=True)

    if allCons is None or children is None:
        return False

    theseCons = list(set(allCons) & set(children))
    for con in theseCons:
        output = mc.listConnections(con, d=True, s=False, scn=True) or []
        for out in output:
            if mc.ls(out, l=True)[0] == con:
                return True
    return False


def animInputTypeCheck(nodeAndAttr):
    """
    checks that node and attribute can be toggled without error - either driven by an "animNode" type or None
    :param nodeAndAttr:
    :return: True or False
    """
    animNodeTypePrefixes = ('animCurve', 'blendWeighted', 'pairBlend', 'animBlend')
    toAttrInput = mc.listConnections(nodeAndAttr, s=True, d=False)
    if toAttrInput is None:
        return True
    for prefix in animNodeTypePrefixes:
        if mc.nodeType(toAttrInput[0]).startswith(prefix):
            return True
    return False


def getAllChildParentControls(control):
    """returns all child parent controls in order"""

    allControls = [control]
    tempControl = control

    while mc.objExists(tempControl + '.IkFkChildParentMessage'):
        try:
            tempControl = mc.listConnections(tempControl + '.IkFkChildParentMessage', source=False, destination=True)[0]
            allControls.append(tempControl)
        except:
            break
    return allControls


def getIKControls(namespace=''):
    """ returns all ik controls in the scene """

    ikCtrlKeywords = ('ElbowControl',
                      'HandControl',
                      'FootControl',
                      'KneeControl',
                      'ToeControl',
                      'AnkleControl',
                      'FingerIKControl',
                      'ToeIKControl')

    if namespace is None:
        namespace = ''

    if len(namespace):
        namespace += ':'

    ikControls = mc.ls(namespace + '*.ikControl', r=True, objectsOnly=True)
    otherIKs = []
    for keyword in ikCtrlKeywords:
        temp = mc.ls(namespace + '*' + keyword + '*', r=True, type='transform')
        for item in temp:

            if not mc.nodeType(item) in ('transform', 'joint'):
                continue

            if not mc.objExists(item + '.controlType'):
                continue

            keywordSplit = item.rsplit(keyword, 1)

            if len(keywordSplit[-1]):
                if item.split(keyword)[-1][0].isdigit():
                    otherIKs.append(item)
            else:
                otherIKs.append(item)

    # otherIKs = mc.ls('*.IkFkSwitchMessage', r=True, objectsOnly=True)
    oldIKSystems = [i for i in mc.ls(namespace + '*ControlIk*', r=True, transforms=True) \
                    if mc.nodeType(i) in ('transform', 'joint') and not i.find('Marker') > -1]

    ikControls.extend(oldIKSystems)
    ikControls.extend(otherIKs)

    ikControls = list(set(ikControls))
    return ikControls


def getIKSystems(ikControls=None, ikSystems=None, namespaces=None):
    """ recursive sort of ik controls to be in a proper order for IK FK matching"""

    if ikControls is None:
        ikControls = []
        if namespaces:
            for ns in namespaces:
                ikControls.extend(getIKControls(namespace=ns))
        else:
            ikControls = getIKControls()
    # print' the ik Controls are', ikControls

    if not ikSystems:
        ikSystems = []

    if len(ikControls) < 1:
        return ikSystems

    topControl = ikControls[0]
    while topControl is not None:
        if not mc.objExists(topControl + '.IkFkChildParentMessage'):
            ikControls.pop(ikControls.index(topControl))

            if len(ikControls):
                topControl = ikControls[0]
            else:
                return ikSystems

            continue

        temp = mc.listConnections(topControl + '.IkFkChildParentMessage', source=True, destination=False, scn=True)
        if temp is not None:
            topControl = temp[0]
        else:
            break

    thisSystem = getAllChildParentControls(topControl)
    # print' THis system is %s' %thisSystem

    ikSystems.append(thisSystem)
    # ikControls = list(set(ikControls) - set(thisSystem))
    remainingIKCtrls = list(set(ikControls) - set(thisSystem))

    # if the passed in control list is the same as the remainingIKCtrls
    setTest = list(set(ikControls) - set(remainingIKCtrls))

    if len(ikControls) and len(setTest):
        # print 'the ik controls ARE %s' % remainingIKCtrls
        getIKSystems(remainingIKCtrls, ikSystems)

    return ikSystems


def dictionary_Connection_Plugs(connectionPLugs, doSourceConPlugs, doDestinationConPlugs):
    """ Convert a list of connection plugs into a dictionary.
        Reorders the key, value if the object connections are source or destination.
        Returns {source.attr: [destination.attr, destination.attr, etc]} """

    conIterRange = len(connectionPLugs) // 2
    startIndex = 0
    endIndex = 2
    aDict = {}

    # Iterate a couple of connection and plugs
    for conIter in range(conIterRange):
        connectionCouple = connectionPLugs[startIndex:endIndex]
        srcCon = None
        desCon = None

        if doSourceConPlugs:
            srcCon = connectionCouple[1]
            desCon = connectionCouple[0]
        elif doDestinationConPlugs:
            srcCon = connectionCouple[0]
            desCon = connectionCouple[1]

        if srcCon not in aDict:
            aDict[srcCon] = [desCon]
        else:
            aDict[srcCon].append(desCon)

        startIndex += 2
        endIndex += 2

    return aDict


def get_Obj_Connections(nodes, doSource=False, doDestination=False):
    """ Get a list of connection plugs, source or destination, then make it a dictionary.
        Returns {source.attr: [destination.attr, destination.attr, etc]}"""

    connections = {}

    for node in nodes:
        if doSource:
            sourceConPlugs = mc.listConnections(node, destination=False, plugs=True, connections=True,
                                                skipConversionNodes=True, shapes=True) or []
            sourceConnections = dictionary_Connection_Plugs(sourceConPlugs, True, False)

            for key, value in sourceConnections.items():
                if key in list(connections.keys()):
                    connections[key] += value
                else:
                    connections.update({key: value})

        if doDestination:
            destinationConPlugs = mc.listConnections(node, source=False, plugs=True, connections=True,
                                                     skipConversionNodes=True, shapes=True) or []
            destinationConnections = dictionary_Connection_Plugs(destinationConPlugs, False, True)

            for key, value in destinationConnections.items():
                if key in list(connections.keys()):
                    connections[key] += value
                else:
                    connections.update({key: value})

    return connections


def disconnect_Obj_Connections(objConnections):
    """ Takes a dictionary of {source.attr: [destination.attr, destination.attr, etc]}
        Disconnects the source.attr with each destination.attr """

    for objSrcAttr, objDstAttrs in objConnections.items():
        for objDstAttr in objDstAttrs:
            isLocked = mc.getAttr(objDstAttr, lock=True)

            if isLocked:
                mc.setAttr(objDstAttr, lock=False)

            try:
                mc.disconnectAttr(objSrcAttr, objDstAttr)
            except Exception:
                pass

            if isLocked:
                mc.setAttr(objDstAttr, lock=True)


def storeObjectAttrValues(objects, attrs):
    """"""

    if isinstance(objects, str) or isinstance(objects, str):
        objects = [objects]

    objAndAttrValues = {}

    for obj in objects:
        if obj not in list(objAndAttrValues.keys()):
            objAndAttrValues[obj] = []

        for attr in attrs:
            value = mc.getAttr(obj + '.' + attr)

            objAndAttrValues[obj].append([attr, value])

    return objAndAttrValues


def setObjectAttrValues(objAndAttrValues):
    """"""

    for obj, attrValues in objAndAttrValues.items():
        for attrValue in attrValues:
            attr = attrValue[0]
            value = attrValue[1]

            if mc.objExists(obj):
                if mc.getAttr(obj + '.' + attr, settable=True) and mc.getAttr(obj + '.' + attr) != value:
                    mc.setAttr(obj + '.' + attr, value)


def createManipulatorLocator():
    """ Create a locator where the manipulator is in Maya viewport. """

    userSels = mc.ls(selection=True)

    if not userSels:
        midPointLocator = mc.spaceLocator()[0]
        sys.stdout.write('%s has been created at [0, 0, 0]' % midPointLocator)
        return

    for sel in userSels:
        if mc.objectType(sel) not in ['transform', 'mesh', 'nurbsCurve']:
            mc.warning('Only transforms, meshes, and nurbsCurve allowed')
            return

    originalTool = mc.currentCtx()

    mc.setToolTo('moveSuperContext')

    manipPos = mc.manipMoveContext('Move', query=True, position=True)
    midPointLoc = mc.spaceLocator()[0]

    mc.setAttr(midPointLoc + '.t', manipPos[0], manipPos[1], manipPos[2])

    mc.setToolTo(originalTool)

    mc.select(midPointLoc, replace=True)

    sys.stdout.write('%s has been created at %s' % (midPointLoc, manipPos))


def moveAttrs(nodeAndAttrs, toObject, deleteOld=True):
    """
    :param nodeAndAttrs: list of node.attrs - (can also be a single node.attr string)
    :param toObject: object to move list of attrs to
    :param deleteOld: boolean to delete attributes from the objects in nodeAndAttrs
    :return: True/False
    """

    # Ensure nodeAndAttrs is a list
    if isinstance(nodeAndAttrs, str) or isinstance(nodeAndAttrs, str):
        nodeAndAttrs = [nodeAndAttrs]

    for nodeAndAttr in nodeAndAttrs:
        node, attr = nodeAndAttr.split('.', 1)
        attrType = mc.attributeQuery(attr, node=node, attributeType=True)
        niceName = mc.attributeQuery(attr, node=node, niceName=True)
        keyable = mc.attributeQuery(attr, node=node, keyable=True)
        visibleAttrs = mc.listAttr(node, visible=True)

        userDefinedAttrs = mc.listAttr(node, ud=True)
        inputs = mc.listConnections(nodeAndAttr, s=True, d=False, scn=True, p=True, c=True)
        outputs = mc.listConnections(nodeAndAttr, s=False, d=True, scn=True, p=True, c=True)

        if not mc.objExists(toObject + '.' + attr) and attr in userDefinedAttrs:
            if attrType == 'message':
                mc.addAttr(toObject, ln=attr, nn=niceName, at='message', k=keyable)
            else:
                if attrType == 'float':
                    mc.addAttr(toObject, ln=attr, nn=niceName, at="float", k=keyable)
                else:
                    mc.addAttr(toObject, ln=attr, nn=niceName, at=attrType, k=keyable)

                mc.setAttr(toObject + '.' + attr, mc.getAttr(nodeAndAttr))

                minValue = None
                maxValue = None
                if mc.attributeQuery(attr, node=node, minExists=True):
                    minValue = mc.attributeQuery(attr, node=node, minimum=True)
                if mc.attributeQuery(attr, node=node, maxExists=True):
                    maxValue = mc.attributeQuery(attr, node=node, maximum=True)

                if minValue:
                    mc.addAttr(toObject + '.' + attr, e=True, min=minValue[0])
                if maxValue:
                    mc.addAttr(toObject + '.' + attr, e=True, max=maxValue[0])
        else:
            mc.warning('An attribute with that name already exists')

            # check that the type is existing and if there's no in/out connections - use it
            existingInput = mc.listConnections(toObject + '.' + attr, s=True, d=False, scn=True, p=True, c=True)
            existingOutput = mc.listConnections(toObject + '.' + attr, s=False, d=True, scn=True, p=True, c=True)
            existingAttrType = mc.attributeQuery(attr, node=toObject, attributeType=True)

            if not (existingInput is None and existingOutput is None and existingAttrType == attrType):
                mc.warning('An attribute of that name exists and has input/outputs, or is not the correct type')
                return False

        if attr in visibleAttrs:
            mc.setAttr(toObject + '.' + attr, keyable=True)

        if outputs is not None:
            for i in range(0, len(outputs), 2):
                mc.connectAttr(toObject + '.' + attr, outputs[i + 1], f=True)

        if inputs is not None:
            mc.connectAttr(inputs[1], toObject + '.' + attr, f=True)
            if deleteOld:
                mc.disconnectAttr(inputs[1], inputs[0])

        if deleteOld:
            mc.deleteAttr(node, attribute=attr)

    return True


def getHolstersFromWeaponJoint(weaponJoint):
    """
    from a weapon joint (JOMeleeWeapon1) - this returns the rig's holster transforms
    :param weaponJoint:
    :return: targets - the weapon holster transforms
    """
    weaponResultant = cd.getSkeletonDriverFromDriven(weaponJoint)
    weaponCon = mc.listRelatives(weaponResultant, c=True, type='parentConstraint')[0]
    inputs = set(mc.listConnections(weaponCon, s=True, d=False, scn=True))
    weaponControl = list(inputs - {weaponResultant, weaponCon})[0]
    weaponControlGroup = weaponControl.replace('WeaponControl', 'MainWeaponControlGroup')
    controlGroupConstraint = mc.listRelatives(weaponControlGroup, c=True, type='parentConstraint')
    targets = mc.parentConstraint(controlGroupConstraint, q=True, targetList=True)
    return targets


def addTimeCodeAttrs(joint=None, control=None, resultant=None, connectAttrs=True):
    """
    Add time code attributes to a joint, control, or resultant. Connect joint, control, and resultant if possible.
    :param joint str, name of joint
    :param control str, name of control
    :param resultant str, name of resultant
    :param connectAttrs bool, tell the script to connect the attrs between the joint, control, and resultant
    :return:
    """

    # add timecode attrs to pelvis
    timeCodeAttrs = ['TCHour', 'TCMinute', 'TCSecond', 'TCFrame']

    allNodes = [joint, control, resultant]

    for node in allNodes:
        if node is not None and mc.objExists(node):
            for attr in timeCodeAttrs:
                if not mc.objExists('{0}.{1}'.format(node, attr)):
                    mc.addAttr(node, longName=attr, niceName=attr, attributeType='long', defaultValue=0)
        else:
            mc.warning("{} does not exists in the scene. Cannot add timecode attrs".format(node))

    if connectAttrs:
        for attr in timeCodeAttrs:
            try:
                controlAttr = '{0}.{1}'.format(control, attr)
                resultantAttr = '{0}.{1}'.format(resultant, attr)
                jointAttr = '{0}.{1}'.format(joint, attr)
                mc.connectAttr(controlAttr, resultantAttr, force=True)
                mc.connectAttr(resultantAttr, jointAttr, force=True)
            except Exception:
                mc.warning(
                    "Error trying to connect timecode attr {}. Please check what arguments you are passing in.".format(
                        attr))


def getPartedMeshes(topNode):
    """
    currently no data node association
    Inferring parted mesh as:
        *nameed "pmMesh..." or "partedMesh..."
        *not skinned
        *parented to skeletal joints
        *has no children
    """
    parted = []
    skinnedMeshes = meshUtils.getSkinnedMeshes()
    joints = mc.listRelatives(topNode, ad=True, type='joint')
    for jnt in joints:
        transforms = mc.listRelatives(jnt, c=True, type='transform')
        if not transforms:
            continue
        for transform in transforms:
            mesh = mc.ls(mc.listRelatives(transform, shapes=True), type='mesh')
            if not mesh or mesh[0] in skinnedMeshes:
                continue

            meshTransform = mc.listRelatives(mesh[0], parent=True)[0]
            for prefix in ('pmMesh', 'partedMesh'):
                if meshTransform.startswith(prefix) and not mc.listRelatives(meshTransform, c=True, type='transform'):
                    parted.append(meshTransform)
                    break
    return parted


def returnConstraintsInScene(returnReferencedNodes=False):
    """
    List all the constraints in the scene filtered out by if the constraints are referenced. Returns both the short name
    and the full dag path.

    @return: dict(), {shortName: 'fullDAGPath': longName}
    """

    if returnReferencedNodes:
        constraintsInScene = dict()
        for constraint, longName in zip(mc.ls(type='constraint'), mc.ls(type='constraint', long=True)):
            constraintsInScene.update({constraint: {'fullDAGPath': longName}})
        return constraintsInScene
    else:
        constraintsInScene = dict()
        for constraint, longName in zip(mc.ls(type='constraint'), mc.ls(type='constraint', long=True)):
            if not mc.referenceQuery(longName, isNodeReferenced=True):
                constraintsInScene.update({constraint: {'fullDAGPath': longName}})

        return constraintsInScene

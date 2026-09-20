
import dag as dagUtils;
import maya.cmds as mc
import maya.mel as mel
import string_lib
import importlib

importlib.reload(dagUtils)


def returnLegJoints(root, base):
    joints = [base]
    currentJoint = base
    while currentJoint != root:
        parent = mc.listRelatives(currentJoint, parent=True)[0]
        joints.append(parent)
        currentJoint = parent
    joints.reverse()
    return joints


def returnRigParentName():
    return 'rigParent'


def returnRigAddOnsName():
    return 'rigAddOns'


def returnSubRigName():
    return 'subRig'


def returnControlResultantName():
    return 'controlResultant'


def returnResultantDriversName():
    return 'resultantDrivers'


def returnRootName():
    return 'dataRoot'


def returnUniqueRootAttrName():
    return 'oneDataToRuleThemAll'


def returnFollowAttrName():
    return 'isAnimDataFollowsRoot'


def returnDataParentAttrName():
    return 'dataParent'


def returnDataTypeAttrName():
    return 'dataType'


def returnSideList():
    return ['Left', 'Right', 'Center']


def getSideFromIndex(index):
    try:
        return returnSideList()[index]
    except:
        return None


def getIsideFromSideName(sideName):
    try:
        return returnSideList().index(sideName)
    except:
        return None


def returnBipedArmName():
    return "bipedArm"


def returnBipedLegName():
    return "bipedLeg"


def returnSkeletonDriverName():
    return 'skeletonDriver'


def returnSkeletonDrivenName():
    return 'skeletonDriven'


def returnRigDrivenName():
    return 'rigDriven'


def returnRigDriverName():
    return 'rigDriver'


def returnMeshLODName():
    return 'meshLOD'


def returnMeshLODParentName():
    return 'meshLODParent'


def returnMeshLODChildrenName():
    return 'meshLODChildren'


def returnMeshLODDriverName():
    return 'meshLODDriver'


def returnMeshLODDrivenName():
    return 'meshLODDriven'


''' ------------------------------ '''


def isResultant(node):
    ''''''

    # LATER: This will fail with a resultant like Back2

    nodeAttrs = mc.listAttr(node, userDefined=True) or []

    if returnResultantDriversName() in nodeAttrs:
        return True
    else:
        return False


def isControl(node):
    if mc.objExists(node + '.controlType'):
        return True
    else:
        return False


def isDataNode(node):
    ''''''

    nodeAttrs = mc.listAttr(node, userDefined=True) or []

    if returnDataTypeAttrName() in nodeAttrs:
        return True
    else:
        return False


def isJoint(node):
    if mc.objExists(node + '._bake') and \
            mc.objExists(node + '.dataSkeletonDriven'):
        return True
    else:
        return False


def queryDataNodeName(name, dataNode):
    '''
    Check if the name provided matches the dataNode.name value.
    :param name:        string
    :param dataNode:    string
    :return:            bool
    '''

    if not mc.attributeQuery('name', node=dataNode, exists=True):
        mc.warning('Attribute, name, does not exist on {}'.format(dataNode))
        return False

    dataNodeName = mc.getAttr('{}.name'.format(dataNode))
    if dataNodeName.lower() == name.lower():
        return True
    else:
        return False


''' ------------------------------ '''


def getDataControls(dataNode):
    ''' get controls connected to dataNode.'''
    if not isDataNode(dataNode):
        mc.warning(dataNode, 'is not a DataNode.')
        return
    controls = []
    ctrlPlugs = [plug for plug in mc.listAttr(dataNode, ud=1) if 'control' in plug.lower()]
    for i, plug in enumerate(ctrlPlugs):
        if mc.objExists(dataNode + '.' + plug):
            ctrls = mc.listConnections(dataNode + '.' + plug)
            if ctrls:
                ctrl = ctrls[-1]
                controls.append(ctrl)
    return controls


def getParentControls(ctrl):
    ''' get parent control(s) from a control.'''
    if isControl(ctrl):
        dataNode = getDataParent(ctrl)
    elif isDataNode(ctrl):
        dataNode = ctrl
    dataPrnt = getDataParent(dataNode)
    if not dataPrnt: return
    dataCtrls = getDataControls(dataPrnt)
    return dataCtrls


def returnAllDataNodes():
    networks = mc.ls(type='network')

    for network in list(networks):
        data = Data(network)
        if not data.dataType:
            networks.remove(network)

    return networks


def getNextNumber(dataType, side=None):
    '''
    This will return the lowest available number for this data type.
    (e.g. If 1 and 3 exist, it will return 2, not 4.)
    '''
    dataNodes = returnAllDataNodes()
    numbers = []

    for dataNode in dataNodes:
        if dataType != mc.getAttr(dataNode + '.' + returnDataTypeAttrName()):
            continue
        if side is not None and mc.objExists(dataNode + '.side'):
            # if type(side) == type(0): <-- linted to line below
            if isinstance(side, int):
                side = getSideFromIndex(side)
            if side.lower() != getSideFromIndex(mc.getAttr(dataNode + '.side')).lower():
                continue
        numbers.append(mc.getAttr(dataNode + '.number'))

    number = 1
    while True:
        if number not in numbers:
            break
        number += 1

    return number


def findParentControlByJoint(childJoint):
    control = ''

    try:
        joint = mc.listRelatives(childJoint, parent=True)[0]
    except:
        return control

    resultant = getSkeletonDriverFromDriven(joint)
    if mc.objExists(resultant + '.controlType'):
        control = resultant
    else:
        control = getDriverFromResultant(resultant)

    return control


def getCharRoots():
    '''returns dictionary of top node as key and value as root data node'''
    charRoots = {}
    dataRoots = []
    dataNodes = returnAllDataNodes()
    for dataNode in dataNodes:
        if mc.objExists(dataNode + '.oneDataToRuleThemAll'):
            dataRoots.append(dataNode)

    for root in dataRoots:
        char = getDestination(root, 'topNode')
        charRoots[char] = root

    return charRoots


def getControlAttrs(dataNode):
    '''returns all attrs of dataNode that have the word 'control' in them'''

    excludeList = ('Group', 'PinCushion', 'Const', 'Blend')

    if not dataNode:
        return False

    if not mc.objExists(dataNode):
        return False

    controlAttrs = []
    udAttrs = mc.listAttr(dataNode, ud=True)
    for attr in udAttrs:
        if attr.lower().find('control') > -1 or attr.lower().find('slider') > -1:

            # make sure it doesn't contain one of the "exclude" strings
            exclude = False
            for exclude in excludeList:
                if attr.find(exclude) > -1:
                    exclude = True
                    break

                if exclude is not True:
                    controlAttrs.append(attr)

    return controlAttrs


def getAllControls():
    '''returns dict of character top nodes names and controllers'''
    allControls = {}
    charRootDict = getCharRoots()
    for char in charRootDict:
        allControls[char] = []
        allData = getAllDataChildren(charRootDict[char])
        for data in allData:
            controlAttrs = getControlAttrs(data)

            # dataType = mc.getAttr(data+'.dataType')
            for attr in controlAttrs:
                dest = mc.listConnections(data + '.' + attr, d=True, s=False, scn=True)
                if dest:
                    dest = [x for x in dest if mc.objExists(x + '.controlType')]

                    allControls[char].extend(dest)

    return allControls


def returnRootNode(namespace='', refNode=''):
    rootNode = None
    rootNodes = mc.ls('*.' + returnUniqueRootAttrName(), recursive=True, objectsOnly=True)

    if mc.objExists(refNode):
        nodesPerRef = mc.referenceQuery(refNode, nodes=True)
        if nodesPerRef:
            for rNode in rootNodes:
                if rNode in nodesPerRef:
                    rootNode = rNode
                    break
    elif rootNodes:
        rootNode = rootNodes[0]

    return rootNode


def returnDriverDrivenRoots():
    rootNodes = mc.ls('*.' + returnUniqueRootAttrName(), recursive=True, objectsOnly=True)

    driverRootNode = returnRootNode()
    drivenRootNode = returnRootNode()

    for rNode in rootNodes:
        rootData = Root(rNode)
        topNode = rootData.topNode
        if mc.objExists(topNode + '.characterLocation'):
            driverRootNode = rNode
        else:
            drivenRootNode = rNode

    return driverRootNode, drivenRootNode


def returnDataNode(dataType, dataParent=None):
    dataNode = ''
    dataNodes = returnDataNodes(dataType, dataParent=dataParent)
    if dataNodes:
        dataNode = dataNodes[0]
    return dataNode


def returnDataNodes(dataType, dataParent=None):
    dataNodes = []
    attrName = returnDataTypeAsName(dataType)

    if dataParent:
        try:
            dataNodes = mc.listConnections(dataParent + '.' + attrName, s=0, d=1) or []
        except:
            pass
    else:
        allDataNodes = returnAllDataNodes()
        for dataNode in allDataNodes:
            data = Data(dataNode)
            if data.dataType == dataType:
                dataNodes.append(dataNode)

    return dataNodes


def returnDataTypeAsName(dataType, sideName='', name=''):
    suffix = string_lib.capitalizeFirstCharacter(name)
    if dataType.lower() != name.lower():
        suffix += string_lib.capitalizeFirstCharacter(dataType)

    return 'data' + string_lib.capitalizeFirstCharacter(sideName) + suffix


def selectRootNode():
    try:
        mc.select(returnRootNode(), replace=True)
    except:
        pass


def createRootNode():
    root = returnRootNode()

    if not root:
        root = mc.createNode('network', name=returnRootName())

        uniqueAttr = returnUniqueRootAttrName()
        createAttr(root, uniqueAttr, 'bool')
        createAttr(root, 'dataType', 'string')
        createAttr(root, 'side', 'enum', enumName=':'.join(returnSideList()))
        mc.setAttr(root + '.side', 2)

        mc.setAttr(root + '.dataType', 'root', type='string')

    return root


def createDataNode(dataType, parent=None, allowMultiple=False, iSide=2, number=0, name='', createRigAttrs=True,
                   isNextNumber=False):
    if not parent:
        parent = createRootNode()

    if isNextNumber:
        number = getNextNumber(dataType, side=iSide)

    sNumber = str(number)
    if number < 1:
        sNumber = ''

    dataNode = returnDataNode(dataType, dataParent=parent)
    # dataTypeName = returnDataTypeAsName(dataType)
    sideList = returnSideList()
    sideName = sideList[iSide]
    if sideName.lower() == 'center':
        sideName = ''

    if not dataNode or allowMultiple:
        dataNode = mc.createNode('network', name=returnDataTypeAsName(dataType, sideName=sideName, name=name) + sNumber)
    elif dataNode:
        data = Data(dataNode)
        if data.iSide is not None and data.number is not None:
            if iSide != data.iSide or number != data.number:
                dataNode = mc.createNode('network',
                                         name=returnDataTypeAsName(dataType, sideName=sideName, name=name) + sNumber)

    createAttr(dataNode, 'dataType', 'string')
    mc.setAttr(dataNode + '.dataType', dataType, type='string')

    if createRigAttrs:
        createAttr(dataNode, 'name', 'string')
        createAttr(dataNode, 'number', 'long')
        createAttr(dataNode, 'side', 'enum', enumName=':'.join(returnSideList()))

        if name:
            mc.setAttr(dataNode + '.name', name, type='string')
        mc.setAttr(dataNode + '.number', number)
        mc.setAttr(dataNode + '.side', iSide)

    if not mc.referenceQuery(parent, inr=True):
        connectData(parent, dataNode)

    return dataNode


def getObjectFromDataAttr(dataNode, dataAttr, longName=False, conSide=False, warningOutput=True, returnList=False):
    dst = True
    src = False
    objects = None

    if not mc.objExists(dataNode):
        if warningOutput:
            mc.warning('The provided data node does not exist')
        if conSide is False:
            return False
        else:
            return False, False, False

    elif not mc.objExists(dataNode + '.' + dataAttr):
        if warningOutput:
            mc.warning('The data attr: %s does not exist on node %s' % (dataAttr, dataNode))
        if conSide is False:
            return False
        else:
            return False, False, False

    multiAttrs = mc.attributeInfo(dataNode, multi=True)

    objects = mc.listConnections(dataNode + '.' + dataAttr, d=dst, s=src, scn=True, sh=True)
    if not objects:
        dst = False
        src = True
        objects = mc.listConnections(dataNode + '.' + dataAttr, d=dst, s=src, scn=True, sh=True)

    if not objects:
        if warningOutput:
            mc.warning('Data attr: %s does not have a connected object' % dataAttr)
        if conSide is False:
            return False
        else:
            return False, False, False

    else:

        if dataAttr in multiAttrs:
            if longName:
                for x in range(len(objects)):
                    objects[x] = mc.ls(objects[x], l=True)[0]

        else:
            if not returnList:
                # Single destination objects, like its normally used elsewhere
                if longName:
                    objects = mc.ls(objects[0], l=True)[0]
                else:
                    objects = objects[0]
            else:
                # Multiple destination objects
                if longName:
                    for x in range(len(objects)):
                        objects[x] = mc.ls(objects[x], l=True)[0]

        # Check if this should return sides
        if conSide is False:
            return objects
        else:
            return objects, dst, src


def createAttr(node, attr, attrType, enumName=None):
    if mc.attributeQuery(attr, node=node, ex=1):
        return

    if attrType == 'enum':
        mc.addAttr(node, ln=attr, nn=attr, at=attrType, enumName=enumName)
    elif attrType == 'string':
        mc.addAttr(node, ln=attr, nn=attr, dt='string')
    elif attrType == 'multi':
        mc.addAttr(node, ln=attr, nn=attr, multi=True, indexMatters=True)
    else:
        mc.addAttr(node, ln=attr, nn=attr, at=attrType)


def createSkeletonDataConnections(drivers, drivens):
    dataDriver = createDataNode(returnSkeletonDriverName(), createRigAttrs=False)
    dataDriven = createDataNode(returnSkeletonDrivenName(), createRigAttrs=False)
    for i in range(len(drivers)):
        connectData(dataDriver, drivers[i], srcAttr=drivers[i], useSrcType=True)
        connectData(dataDriven, drivens[i], srcAttr=drivers[i], useSrcType=True)
    return dataDriver, dataDriven


def createDrivenSkeletonDataConnections(nodes, names):
    dataDriven = createDataNode(returnSkeletonDrivenName(), createRigAttrs=False)
    for i in range(len(nodes)):
        connectData(dataDriven, nodes[i], srcAttr=names[i], useSrcType=True)


def getNextMultiIndex(nodeAndAttr):
    nextNum = 0

    try:
        currentIndices = mc.getAttr(nodeAndAttr, multiIndices=True) or []
    except:
        print(("I TRIED {0}".format(nodeAndAttr)))
        return

    while True:
        if nextNum not in currentIndices:
            break
        nextNum += 1

    return nextNum


def getMultConnections(nodeAndAttr):
    '''
    Returns a dictionary with multiIndex as keys and connected node as value.
    ex:
    :param nodeAndAttr:
    :return:
    '''
    iterator = 0
    multiAttrDict = {}
    currentIndices = mc.getAttr(nodeAndAttr, multiIndices=True) or []
    while True:
        if iterator not in currentIndices:
            break
        connection = mc.listConnections(nodeAndAttr + '[' + str(iterator) + ']')
        if connection != None:
            multiAttrDict[iterator] = connection[0]
        else:
            multiAttrDict[iterator] = mc.listConnections(nodeAndAttr + '[' + str(iterator) + ']')
        iterator += 1

    return multiAttrDict


def connectData(src, dst, srcAttr=None, useSrcType=False, dstAttr=None):
    '''
    This function makes attribute connections from source to destination. If attr does not exist, it will create it.
    Easiest way to use this function is to define src, dst, scrAttr, and dstAttr. However, extra conditions exist
    for handling data node connections across our code bass. Here is what we know:

    1) Providing src, dst, srcAttr, and dstAttr is easiest way to use!
    2) If srcAttr = None, will attempt to get dst 'dataType' as srcAttr.
    3) If dstAttr = None, will attempt to give you 'dataParent' as dstAttr. Unless useSrcType is defined in which case
       it will grab the src node's 'dataType' entry.
    4) If dst is not a dataNode, must provide srcAttr.
    5) Passing src or dst as a list of nodes will force creation of a multi attr for the opposite connection:
       src(list) --> dst.multi
       src.multi --> dst(list)
    '''
    dataTypeAttr = returnDataTypeAttrName()
    if not dstAttr:
        dstAttr = returnDataParentAttrName()
        if useSrcType:
            dstAttr = returnDataTypeAsName(mc.getAttr(src + '.' + dataTypeAttr))

    if not srcAttr:
        if not mc.objExists(dst + '.' + dataTypeAttr):
            raise Exception('Please specify srcAttr if dstAttr is not a data node.')
        else:
            srcAttr = returnDataTypeAsName(mc.getAttr(dst + '.' + dataTypeAttr))

    # if type(dst) == type([]): <-- linted! Use isinstance instead
    if isinstance(dst, list):
        createAttr(src, srcAttr, 'multi')

        for i in range(len(dst)):
            createAttr(dst[i], dstAttr, 'message')

            # Find next available slot in the multi attr.
            nextNum = getNextMultiIndex(src + '.' + srcAttr)

            mc.connectAttr(src + '.%s[%s]' % (srcAttr, nextNum), dst[i] + '.' + dstAttr, force=True)
    elif isinstance(src, list):
        createAttr(dst, dstAttr, 'multi')

        for i in range(len(src)):
            createAttr(src[i], srcAttr, 'message')

            # Find next available slot in the multi attr.
            nextNum = getNextMultiIndex(dst + '.' + dstAttr)

            mc.connectAttr(src[i] + '.' + srcAttr, dst + '.%s[%s]' % (dstAttr, nextNum), force=True)
    else:
        if srcAttr.find('[') > -1:
            createAttr(src, srcAttr.rsplit('[', 1)[0], 'multi')
        else:
            createAttr(src, srcAttr, 'message')
        createAttr(dst, dstAttr, 'message')

        if not mc.isConnected(src + '.' + srcAttr, dst + '.' + dstAttr):
            mc.connectAttr(src + '.' + srcAttr, dst + '.' + dstAttr, force=True)


def connectNodeAttrToData(node, nodeAttr, dataNode, dataAttr):
    '''
    Created to connect control attrs to data node.
    e.g. switch control attr, blade control attrs.
    '''
    # Create data node attr.
    if not mc.objExists(dataNode + '.' + dataAttr):
        createAttr(dataNode, dataAttr, 'message')
    # Connect control atr to data node attr.
    if not mc.isConnected(node + '.' + nodeAttr, dataNode + '.' + dataAttr):
        mc.connectAttr(node + '.' + nodeAttr, dataNode + '.' + dataAttr, force=True)


def createControlResultantConnections(srcs, dst):
    '''
    This is used for resultant nodes that are driven by control(s).
    (e.g. BackControl1 and BackControlIk1 results in Back1. PelvisControlA1 results in Pelvis1.)
    '''
    resultantAttr = returnControlResultantName()
    driversAttr = returnResultantDriversName()

    if not srcs:
        return

    createAttr(dst, driversAttr, 'multi')

    for i in range(len(srcs)):
        createAttr(srcs[i], resultantAttr, 'message')

        currentDrivers = mc.listConnections(dst + '.' + driversAttr, s=0, d=1) or []

        if srcs[i] in currentDrivers:
            continue

        # Find next available slot in the multi attr.
        nextNum = getNextMultiIndex(dst + '.' + driversAttr)

        mc.connectAttr(dst + '.%s[%s]' % (driversAttr, nextNum), srcs[i] + '.' + resultantAttr, force=True)


def getResultantFromConstraint(bakeJoint):
    ''' created because it's 10X faster than getSkeletonDriverFromDriven() '''

    constraint = mc.listRelatives(bakeJoint, c=True, type='constraint', f=True)

    if not constraint:
        # try to find by direct connection
        keyable = mc.listAttr(bakeJoint, k=True, v=True)
        if not keyable:
            return False

        allInputs = []
        for attr in keyable:

            if not mc.objExists(bakeJoint + '.' + attr):
                continue

            inputs = mc.listConnections(bakeJoint + '.' + attr, s=True, d=False, scn=True)
            if inputs:
                allInputs.extend(inputs)
        allInputs = list(set(allInputs))
        nodes = mc.ls(allInputs, type='transform')

        if nodes:
            return nodes[0]

        return False

    if not mc.referenceQuery(constraint[0], inr=True):
        cmd = 'mc.' + mc.nodeType(constraint[0]) + '("' + constraint[0] + '", q=True, targetList=True)'
        targets = eval(cmd)

        if not targets is None:
            return targets[0]

    return False


def getSkeletonDriverFromDriven(bakeJoint):
    resultant = ''
    dataRoot = getTopDataParent(bakeJoint)

    namespace = ''
    if ':' in dataRoot:
        namespace = dataRoot.split(':', 1)[0]

    # make sure we're finding the proper dataRoot that has a dataSkeletonDriveR associated with it
    if not mc.objExists(dataRoot) or not mc.objExists(dataRoot + '.' + returnSkeletonDriverName()):
        rootNodes = mc.ls('*.' + returnUniqueRootAttrName(), recursive=True, objectsOnly=True)

        # filter root nodes by namespace and sort to try to get the non-numerical rig side "dataRoot"
        rootNodes = [i for i in rootNodes if i.startswith(namespace)]
        rootNodes.sort()

        for dRoot in rootNodes:
            if dRoot.startswith(namespace):
                if mc.objExists(
                        dRoot + '.data' + returnSkeletonDriverName()[0].upper() + returnSkeletonDriverName()[1:]):
                    dataRoot = dRoot
                    break

    dataDrivenAttr = returnDataTypeAsName(returnSkeletonDrivenName())

    if mc.objExists(bakeJoint + '.' + dataDrivenAttr):
        drivenPlugs = mc.listConnections(bakeJoint + '.' + dataDrivenAttr, s=1, d=0, plugs=True)

        if drivenPlugs:
            commonAttr = drivenPlugs[0].rsplit('.', 1)[-1]
            dataDriver = returnDataNode(returnSkeletonDriverName(), dataParent=dataRoot)

            if dataDriver and mc.objExists(dataDriver + '.' + commonAttr):
                temps = mc.listConnections(dataDriver + '.' + commonAttr, s=0, d=1)
                if temps:
                    resultant = temps[0]

    if not resultant:
        mc.warning(f'Unable to determine resultant driver from: {bakeJoint}')

    return resultant


def getSkeletonDrivenFromDriver(resultant):
    bakeJoint = ''
    rootNode = getTopDataParent(resultant)

    skelRootNode = None

    # try to find the skeletons root node
    if mc.referenceQuery(rootNode, isNodeReferenced=True):
        baseRef = mc.referenceQuery(rootNode, referenceNode=True)

        if not mc.objExists(baseRef + '.' + returnRigAddOnsName()):
            return False

        # get the rig add on that is not a "subRig"
        rigAddOns = mc.listConnections(baseRef + '.' + returnRigAddOnsName(), d=True, s=False, scn=True)

        thisAddOn = None
        for addOn in rigAddOns:
            if mc.objExists(addOn + '.' + returnRigParentName()):
                if not mc.objExists(addOn + '.' + returnSubRigName()):
                    thisAddOn = addOn
                    break

        if not thisAddOn:
            mc.warning('A mesh-LOD reference could not be found')
            return False

        # print 'THIS ADD ON is %s' %thisAddOn
        skelRootNode = getTopDataParent(dagUtils.getTopNodeFromRef(thisAddOn))
        if not skelRootNode:
            mc.warning('A dataRoot node could not be found for mesh-LOD reference: %s') % thisAddOn
            return False

    else:
        skelRootNode = returnDriverDrivenRoots()[1]

    dataDriverAttr = returnDataTypeAsName(returnSkeletonDriverName())

    if mc.objExists(resultant + '.' + dataDriverAttr):

        # print' the resultant attr is %s' % (resultant + '.' + dataDriverAttr)

        driverPlugs = mc.listConnections(resultant + '.' + dataDriverAttr, s=1, d=0, plugs=True)
        if driverPlugs:
            commonAttr = driverPlugs[0].rsplit('.', 1)[-1]

            dataDriven = returnDataNode(returnSkeletonDrivenName(), dataParent=skelRootNode)
            # print 'the data Driven node is %s' % dataDriven

            if not dataDriven:
                return

            if dataDriven and mc.objExists(dataDriven + '.' + commonAttr):
                temps = mc.listConnections(dataDriven + '.' + commonAttr, s=0, d=1)
                if temps:
                    bakeJoint = temps[0]

    return bakeJoint


def getDataChild(dataNode, dataType=None, number=-1, allDownstreams=False):
    '''
    Return one downstream data node.
    '''
    dataChild = ''
    dataChildren = getDataChildren(dataNode, dataType=dataType, number=number, allDownstreams=allDownstreams)

    if dataChildren:
        dataChild = dataChildren[0]

    return dataChild


def getDataChildren(dataNode, dataType=None, number=-1, allDownstreams=False):
    '''
    Return downstream data nodes.
    '''
    dataParentAttr = returnDataParentAttrName()
    dataTypeAttr = returnDataTypeAttrName()
    dataChildren = []

    if allDownstreams:
        dataChildren = getAllDataChildren(dataNode)
    else:
        plugs = mc.listConnections(dataNode, s=0, d=1, plugs=True) or []

        for plug in plugs:
            node, attr = plug.rsplit('.', 1)
            if attr == dataParentAttr and mc.objExists(node + '.' + dataTypeAttr):
                dataChildren.append(node)

    for dataChild in list(dataChildren):
        if dataType and dataType != mc.getAttr(dataChild + '.' + dataTypeAttr):
            dataChildren.remove(dataChild)

        if number > -1 and mc.objExists(dataChild + '.number') and number != mc.getAttr(
                dataChild + '.number') and dataChild in dataChildren:
            dataChildren.remove(dataChild)

    return dataChildren


def getAllDataChildren(dataNode, dataChildren=None):
    if not dataChildren:
        dataChildren = []
    dataParentAttr = returnDataParentAttrName()
    dataTypeAttr = returnDataTypeAttrName()

    plugs = mc.listConnections(dataNode, s=0, d=1, plugs=True) or []

    for plug in plugs:
        node, attr = plug.rsplit('.', 1)
        if attr == dataParentAttr and mc.objExists(node + '.' + dataTypeAttr):
            if node not in dataChildren:
                dataChildren.append(node)
                getAllDataChildren(node, dataChildren=dataChildren)
    return dataChildren


def getDataParent(node):
    '''
    Return data parent of this node.
    I'm adding dataSkeletonDriven and dataSkeletonDriver in here as a check because there are cases
    when a node might not have a data parent (e.g. RightWrist1 resultant).
    '''
    dataParent = ''
    dataParentAttr = returnDataParentAttrName()
    drivenAttr = returnDataTypeAsName(returnSkeletonDrivenName())
    driverAttr = returnDataTypeAsName(returnSkeletonDriverName())

    for attr in (dataParentAttr, drivenAttr, driverAttr):
        if mc.objExists(node + '.' + attr):
            try:
                dataParent = mc.listConnections(node + '.' + attr, s=1, d=0)[0]
                break
            except:
                continue

    return dataParent


def getTopDataParent(node):
    dataParent = getDataParent(node)

    if not dataParent:
        return node

    tempParent = dataParent

    while True:
        tempParent = getDataParent(tempParent)
        if not tempParent:
            break
        dataParent = tempParent

    return dataParent


def get_dataMeshLODs(dataRoot=None):
    ''' Get and return a list of dataMeshLODs under all dataRoots or the one provided..'''

    dataRoots = getCharRoots()
    dataMeshLODs = []

    if dataRoot:
        dataMeshLODs += getObjectFromDataAttr(dataRoot, returnDataTypeAsName(returnMeshLODName()),
                                              returnList=True) or []
    else:
        for dr in list(dataRoots.values()):
            dataMeshLODs += getObjectFromDataAttr(dr, returnDataTypeAsName(returnMeshLODName()), returnList=True) or []

    return dataMeshLODs


def get_objects_dataMeshLODs(node):
    ''' Return the dataMeshLODs an object is defined on. '''

    srcDataNodes = mc.listConnections(node, destination=False, type='network') or []
    dataMeshLODs = []

    for srcDataNode in srcDataNodes:
        dataType = mc.getAttr(srcDataNode + '.' + returnDataTypeAttrName())

        if returnMeshLODName() == dataType:
            dataMeshLODs.append(srcDataNode)

    return dataMeshLODs


def getControlResultantAndDrivers(src):
    try:
        resultant = mc.listConnections(src + '.' + returnControlResultantName())[0]
        drivers = mc.listConnections(resultant + '.' + returnResultantDriversName()) or []
        return [resultant, drivers]
    except:
        return ['', []]


def getDriverFromResultant(resultant):
    try:
        return getDriversFromResultant(resultant)[0]
    except:
        return ''


def getDriversFromResultant(resultant):
    try:
        return mc.listConnections(resultant + '.' + returnResultantDriversName()) or []
    except:
        return []


def getControlDriversFromResultant(resultant):
    ''' Get/return control(s) driver from a resultant.
        Resultant may be the control itself.
    '''

    resultantAttrs = mc.listAttr(resultant, userDefined=True) or []
    controlDrivers = []

    if returnResultantDriversName() in resultantAttrs:
        # resultant is a real resultant with multiple drivers
        controlDrivers = mc.listConnections(resultant + '.' + returnResultantDriversName()) or []
    elif 'controlType' in resultantAttrs:
        # resultant is the control
        controlDrivers.append(resultant)

    return controlDrivers


def getControls(dataType, attr, cd=None):
    result = ''

    if not cd:
        cd = returnRootNode()

    try:
        dataNode = mc.listConnections(cd + '.' + dataType, s=0, d=1)[0]
        controls = mc.listConnections(dataNode + '.' + attr, s=0, d=1)
        print(controls)
        if controls:
            if len(controls) > 1:
                controls = sorted(controls, key=lambda x: x.lower())
                result = controls
            else:
                result = controls[0]
    except Exception as e:
        print(e)
        pass

    return result


def getSource(node, attr, plugs=False):
    try:
        return getSources(node, attr, plugs=plugs)[0]
    except:
        if attr == 'bControlAndAttr':
            return '.'
        else:
            return ''


def getSources(node, attr, plugs=False):
    try:
        # Note: Not doing anything special for compound attributes at the moment because
        # Maya seems to return the list in the correct order (e.g. ikControls)
        return mc.listConnections(node + '.' + attr, s=1, d=0, plugs=plugs) or []
    except:
        return []


def getDestination(node, attr, plugs=False):
    try:
        return getDestinations(node, attr, plugs=plugs)[0]
    except:
        return ''


def getDestinations(node, attr, plugs=False):
    '''
    Make sure to return compound attrs in order.
    '''
    nodes = []

    if not mc.objExists(node + '.' + attr):
        return nodes

    if mc.getAttr(node + '.' + attr, type=True) == 'TdataCompound':
        numberedDic = {}

        allConns = mc.listConnections(node + '.' + attr, s=0, d=1, connections=True, plugs=plugs) or []

        for i in range(0, len(allConns), 2):
            if allConns[i].endswith(']'):
                index = int(allConns[i].rsplit('[', 1)[-1].split(']')[0])
                numberedDic[index] = allConns[i + 1]

        indices = list(numberedDic.keys())
        indices.sort()

        for index in indices:
            nodes.append(numberedDic[index])
    else:
        nodes = mc.listConnections(node + '.' + attr, s=0, d=1, plugs=plugs) or []

    return nodes


def getMarkers(controls):
    markers = []

    # Currently, hardcoding this name because i can't import ikfkSCEA into this module just yet.
    markerAttr = 'markerMessage'

    for control in controls:
        try:
            marker = mc.listConnections(control + '.' + markerAttr)[0]
        except:
            marker = ''
        markers.append(marker)

    return markers


def getAttr(node, attr):
    try:
        return mc.getAttr(node + '.' + attr)
    except:
        return None


def getDataNodeSkeletonDrivens(dataNode):
    """
    Pulls nodes from dataNode and then checks to see if they have a skeletonDriveN
    :param dataNode: dataNode to request nodes from
    :return:
    """
    bakeJoints = []

    def getBakeJoint(resultant):
        bakeJoint = getSkeletonDrivenFromDriver(resultant)
        if bakeJoint:
            bakeJoints.append(bakeJoint)

    nodeOutputs = mc.listConnections(dataNode, d=True, s=False, scn=True)
    for node in nodeOutputs:
        getBakeJoint(node)

    # older rigs that don't have all resultants marked up...
    if not bakeJoints:
        for node in nodeOutputs:
            resultantAndDrivers = getControlResultantAndDrivers(node)
            if resultantAndDrivers[0]:
                getBakeJoint(resultantAndDrivers[0])

    bakeJoints = list(set(bakeJoints))

    return bakeJoints


def get_MeshLOD_Ref(baseRef):
    ''' get mesh lod reference node based on base reference node'''

    subRefs = []
    if mc.objExists(baseRef + '.' + returnRigAddOnsName()):
        for temp in (mc.listConnections(baseRef + '.' + returnRigAddOnsName(), s=0, d=1) or []):
            if mc.objExists(temp + '.' + returnSubRigName()):
                continue
            subRefs.append(temp)
            break

    return subRefs


def compare_Add_Unique_Message_Attrs(sourceDataNode, targetDataNode):
    ''' Compare the source dataNOde message attrs with target data node.
        Create and connect unique messsage attrs.
        Intended for dataSkeletonDriver, driven, etc.'''

    srcDataNodeAttrs = mc.listAttr(sourceDataNode, userDefined=True)
    trgtDataNodeAttrs = mc.listAttr(targetDataNode, userDefined=True)
    dataNodeAttrObjs = {}

    for attr in srcDataNodeAttrs:
        if attr not in trgtDataNodeAttrs and mc.addAttr(sourceDataNode + '.' + attr, query=True,
                                                        attributeType=True) == 'message':
            objDstAttrs = mc.listConnections(sourceDataNode + '.' + attr, source=False, shapes=True, plugs=True) or []
            targetDataNodeAttr = targetDataNode + '.' + attr
            dataNodeAttrObjs[targetDataNodeAttr] = []

            mc.addAttr(targetDataNode, longName=attr, niceName=attr, attributeType='message')

            for objDstAttr in objDstAttrs:
                obj = objDstAttr.split('.')[0]
                dstAttr = objDstAttr.split('.')[1]

                connectData(targetDataNode, obj, srcAttr=attr, dstAttr=dstAttr)

                dataNodeAttrObjs[targetDataNodeAttr].append(obj)

    if dataNodeAttrObjs:
        print('Created unique attrs, reconnected unique objects: %s' % dataNodeAttrObjs)


def returnValidFromList(lst):
    return [x for x in lst if x is not None and x != '']


def reconnectDefinitions(dataNode='dataSkeletonDriven'):
    ''' attempts to find scene items that match the definition attrs and reconnect if there is no existing connection'''
    attrs = mc.listAttr(dataNode, ud=True)

    for attr in attrs:

        guesses = [attr, 'JO' + attr, 'JO' + attr[0].lower() + attr[1:], 'JO' + attr[0].upper() + attr[1:]]
        for guess in guesses:
            if 'Control' in guess:
                guesses.append(guess.replace('Control', ''))
            elif 'Resultant' in guess:
                guesses.append(guess.replace('Resultant', ''))

        obj = None
        for guess in guesses:
            if mc.objExists(guess):
                obj = guess
                break

        if obj is None:
            continue

        if not mc.listConnections(dataNode + '.' + attr, s=False, d=True, scn=True):
            print('Connecting %s to %s' % (dataNode + '.' + attr, obj))
            connectData(dataNode, obj, srcAttr=attr, useSrcType=False)

    return True


def getThreeJointLimbSrcAttrNames(dataType, version):
    '''
    Non-version bipedLeg datanodes have old names.
    1.0 version have new names.
    :param dataType:    string
    :return:            list of strings, list of strings
    '''

    if dataType == 'bipedLeg':
        oldFKSrcAttrNames = ['hipFkControl', 'kneeFkControl', 'footFkControl', 'toeFkControl']
        oldIKSrcAttrNames = ['kneeControl', 'kneeSubIkControl', 'footControl', 'toeControl']
        newFKSrcAttrNames = ['femurFKControl', 'fibulaTibiaFKControl',
                             'tarsalsFKControl', 'proximalPhalangesFKControls']
        newIKSrcAttrNames = ['femurIKControl', 'fibulaTibiaIKControl',
                             'tarsalsIKControl', 'proximalPhalangesIKControls']
    elif dataType == 'bipedArm':
        oldFKSrcAttrNames = ['shoulderFkControl', 'elbowFkControl', 'handFkControl']
        oldIKSrcAttrNames = ['elbowControl', 'elbowSubIkControl', 'handControl']
        newFKSrcAttrNames = ['humerusFKControl', 'radiusUlnaFKControl', 'carpalsFKControl']
        newIKSrcAttrNames = ['humerusIKControl', 'radiusUlnaIKControl', 'carpalsIKControl']

    if version and version >= 1.0:
        return newFKSrcAttrNames, newIKSrcAttrNames
    else:
        return oldFKSrcAttrNames, oldIKSrcAttrNames


# class CharacterDefinition:
#     def __init__(self):# , *args):
#         self.rootNode = None
#         self.bladeControl = None

#         self.populateData()

#     def populateData(self):
#         self.rootNode = returnRootNode()

#         try:
#             self.bladeControl = mc.listConnections(self.rootNode + '.bladeControl', source = True, destination = False)[0]
#         except:
#             pass


def addDataToRig():
    ''' adds character definitions to old rigs'''

    # get root controller

    # root
    rootDataNode = getTopDataParent('RootControl1')
    rootData = Root(rootDataNode)
    # jointsGroup = rootData.jointsGroup
    # controlsGroup = rootData.controlsGroup
    # meshGroup = rootData.meshGroup

    # pelvis
    pelvisControls = ['PelvisControlA1']
    # pelvisDataNode = getDataParent(pelvisControls[0])
    # pelvisData = Pelvis(pelvisDataNode)

    # spine
    fkControls = ['BackControl1', 'BackControl2', 'BackControl3']
    ikControls = ['BackControlIk1', 'BackControlIk2', 'BackControlIk3']
    switchControl = 'BackControlSwitch'
    dataNode = createDataNode('ikSpine', parent=getDataParent(pelvisControls[0]), iSide=2, name='Back')
    connectData(dataNode, fkControls, srcAttr='fkControls')
    connectData(dataNode, ikControls, srcAttr='ikControls')
    connectData(dataNode, switchControl, srcAttr='switchControl')
    connectNodeAttrToData(switchControl, 'IKSwitch', dataNode, 'switchControlAndAttr')

    # setting up neck
    neckControl = 'NeckControl1'
    parentDataNode = getDataParent(neckControl)
    # iSide = pm.mel.checkSideSCEA('JONeck1', rootData.topNode)
    iSide = mel.eval('checkSideSCEA("JONeck1", ' + rootData.topNode + ');')
    neckDataNode = createDataNode('neck', parent=parentDataNode, iSide=iSide, name='Neck', isNextNumber=True)
    # Generic(neckDataNode)
    connectData(neckDataNode, [neckControl], srcAttr='controls')
    createSkeletonDataConnections([neckControl], ['JONeck1'])

    # setting up head
    headControl = 'HeadControl1'
    parentDataNode = getDataParent(headControl)
    # iSide = pm.mel.checkSideSCEA('JOHead1', rootData.topNode)
    iSide = mel.eval('checkSideSCEA("JOHead1", ' + rootData.topNode + ');')
    headDataNode = createDataNode('head', parent=parentDataNode, iSide=iSide, name='Head', isNextNumber=True)
    # Generic(headDataNode)
    connectData(headDataNode, [headControl], srcAttr='controls')
    createSkeletonDataConnections([headControl], ['JOHead1'])

    # face
    faceDataNode = None

    parentDataNode = getDataParent(headControl)
    parentResultant = getControlResultantAndDrivers(headControl)[0]
    if not parentResultant:
        parentResultant = headControl

    if mc.getAttr(parentDataNode + '.' + returnDataTypeAttrName()) == 'face':
        faceDataNode = parentDataNode
    else:
        temp = getDataChild(parentDataNode, dataType='face', number=1, allDownstreams=True)
        if temp:
            faceDataNode = temp

    if not faceDataNode:
        faceDataNode = createDataNode('face', parent=parentDataNode, iSide=2, number=1)

    # faceData = Generic(faceDataNode)

    # setting up jaw
    jawControl = 'JawControl1'
    connectData(faceDataNode, jawControl, srcAttr='jawControl')
    createSkeletonDataConnections([jawControl], ['JOJaw1'])

    # LEG
    legJoints = ['JORightUpperLeg1', 'JORightToe1Tip', 'JOLeftUpperLeg1', 'JOLeftToe1Tip']

    for x in range(0, len(legJoints), 2):

        bindJoints = returnLegJoints(legJoints[x], legJoints[x + 1])

        hookUpPoints = []
        for jnt in bindJoints:
            hookUpPoints.append(jnt.replace('J0', ''))

        # 0 = left, 1 = right, 2= center
        sideNames = {0: 'Left', 1: 'Right', 2: 'Center'}
        # iSide = pm.mel.checkSideSCEA(bindJoints[x], 'PelvisControlA1')
        iSide = mel.eval('checkSideSCEA(' + bindJoints[x] + ', "PelvisControlA1");')

        side = sideNames[iSide]
        sNum = 1

        kneeControl = '%sKneeControl%s' % (side, sNum)
        footControl = '%sFootControl%s' % (side, sNum)
        toeControl = '%sToeControl%s' % (side, sNum)
        hipFkControl = '%sHipFKControl%s' % (side, sNum)
        kneeFkControl = '%sKneeFKControl%s' % (side, sNum)
        footFkControl = '%sFootFKControl%s' % (side, sNum)
        toeFkControl = '%sToeFKControl%s' % (side, sNum)
        switchControl = '%sFootIKFKSwitchControl%s' % (side, sNum)

        IKFKJointsBuffer = 'IKFK' + bindJoints[0] + 'Buffer'

        # Create resultant/drivers connections.
        createControlResultantConnections([kneeControl, hipFkControl], hookUpPoints[0])
        createControlResultantConnections([kneeFkControl], hookUpPoints[1])
        createControlResultantConnections([footControl, footFkControl], hookUpPoints[2])

        if len(bindJoints) == 5:
            createControlResultantConnections([toeControl, toeFkControl], hookUpPoints[3])

        # Meta data.
        dataNode = createDataNode('bipedLeg', parent=getDataParent('PelvisControlA1'), iSide=iSide, number=sNum)
        connectData(dataNode, kneeControl, srcAttr='kneeControl')
        connectData(dataNode, footControl, srcAttr='footControl')
        connectData(dataNode, hipFkControl, srcAttr='hipFkControl')
        connectData(dataNode, kneeFkControl, srcAttr='kneeFkControl')
        connectData(dataNode, footFkControl, srcAttr='footFkControl')
        connectData(dataNode, switchControl, srcAttr='switchControl')
        connectNodeAttrToData(switchControl, 'IKSwitch', dataNode, 'switchControlAndAttr')

        connectData(dataNode, IKFKJointsBuffer, srcAttr='bufferResultant')

        if mc.objExists(toeControl):
            connectData(dataNode, toeControl, srcAttr='toeControl')
        if mc.objExists(toeFkControl):
            connectData(dataNode, toeFkControl, srcAttr='toeFkControl')

        # meta data
        createSkeletonDataConnections(hookUpPoints, bindJoints)


class Root:
    def __init__(self, rootNode):
        self.dataType = getAttr(rootNode, returnDataTypeAttrName())
        self.node = rootNode
        self.mainControl = getDestination(rootNode, 'mainControl')
        self.rootControl = getDestination(rootNode, 'rootControl')
        self.topNode = getDestination(rootNode, 'topNode')

        # Groups.
        self.controlsGroup = getDestination(rootNode, 'controlsGroup')
        self.jointsGroup = getDestination(rootNode, 'jointsGroup')
        self.meshGroup = getDestination(rootNode, 'meshGroup')
        self.doNotTouchGroup = getDestination(rootNode, 'doNotTouchGroup')
        self.lodDoNotTouchGroup = getDestination(rootNode, "lodDoNotTouchGroup")

        # Anim joint controls.
        self.linkJointControl = getDestination(rootNode, 'linkJointControl')
        self.synchJointControl = getDestination(rootNode, 'synchJointControl')
        self.zeroJointControl = getDestination(rootNode, 'zeroJointControl')
        self.zeroJointMarkerControl = getDestination(rootNode, 'zeroJointMarkerControl')
        self.dataSkeletonDriver = getDestination(rootNode, 'dataSkeletonDriver')
        self.dataSkeletonDriven = getDestination(rootNode, 'dataSkeletonDriven')


class Data:
    def __init__(self, dataNode):
        self.dataType = getAttr(dataNode, returnDataTypeAttrName())
        self.name = getAttr(dataNode, 'name')
        self.node = dataNode
        self.number = getAttr(dataNode, 'number')
        self.iSide = getAttr(dataNode, 'side')
        self.side = getSideFromIndex(self.iSide)
        self.scalable = getAttr(dataNode, 'scalable')
        self.version = getAttr(dataNode, 'version')


class Pelvis(Data):
    def __init__(self, dataNode):
        Data.__init__(self, dataNode)

        self.pelvisControlA = getDestination(dataNode, 'pelvisControlA')
        self.pelvisControlB = getDestination(dataNode, 'pelvisControlB')
        self.pelvisControlAGroup = getDestination(dataNode, 'pelvisControlAGroup')
        self.pelvisControlBGroup = getDestination(dataNode, 'pelvisControlBGroup')
        # self.pelvisResultant = getControlResultantAndDrivers(self.pelvisControlA)[0]

        possibleControls = [self.pelvisControlA, self.pelvisControlB]
        possibleControlGroups = [self.pelvisControlAGroup, self.pelvisControlBGroup]
        self.controls = [x for x in possibleControls if x is not None and x != '']
        self.controlGroups = [x for x in possibleControlGroups if x is not None and x != '']


class BipedArm(Data):
    def __init__(self, dataNode):
        Data.__init__(self, dataNode)

        srcAttrFKNames, srcAttrIKNames = getThreeJointLimbSrcAttrNames(self.dataType, self.version)

        self.shoulderFkControl = getDestination(dataNode, srcAttrFKNames[0])
        self.elbowFkControl = getDestination(dataNode, srcAttrFKNames[1])
        self.handFkControl = getDestination(dataNode, srcAttrFKNames[2])

        self.elbowControl = getDestination(dataNode, srcAttrIKNames[0])
        self.elbowSubIKControl = getDestination(dataNode, srcAttrIKNames[1])
        self.handControl = getDestination(dataNode, srcAttrIKNames[2])

        self.switchControlAndAttr = getSource(dataNode, 'switchControlAndAttr', plugs=True)
        self.switchControlAttr = self.switchControlAndAttr.split('.')[-1]
        self.switchControl = getDestination(dataNode, 'switchControl')

        # Resultants.
        self.bufferResultant = getDestination(dataNode, 'bufferResultant')
        self.handResultant = getControlResultantAndDrivers(self.handFkControl)[0]
        self.elbowResultant = getControlResultantAndDrivers(self.elbowFkControl)[0]
        self.shoulderResultant = getControlResultantAndDrivers(self.shoulderFkControl)[0]

        self.fkControls = [self.shoulderFkControl, self.elbowFkControl, self.handFkControl]
        self.ikControls = [self.elbowControl, self.handControl]

        self.fkMarkers = getMarkers(self.fkControls)
        self.ikMarkers = getMarkers(self.ikControls)


class BipedLeg(Data):
    def __init__(self, dataNode):
        Data.__init__(self, dataNode)

        srcAttrFKNames, srcAttrIKNames = getThreeJointLimbSrcAttrNames(self.dataType, self.version)

        self.hipFkControl = getDestination(dataNode, srcAttrFKNames[0])
        self.kneeFkControl = getDestination(dataNode, srcAttrFKNames[1])
        self.footFkControl = getDestination(dataNode, srcAttrFKNames[2])
        self.toeFkControl = getDestination(dataNode, srcAttrFKNames[3])

        self.kneeControl = getDestination(dataNode, srcAttrIKNames[0])
        self.kneeSubIKControl = getDestination(dataNode, srcAttrIKNames[1])
        self.footControl = getDestination(dataNode, srcAttrIKNames[2])
        self.toeControl = getDestination(dataNode, srcAttrIKNames[3])

        self.switchControlAndAttr = getSource(dataNode, 'switchControlAndAttr', plugs=True)
        self.switchControlAttr = self.switchControlAndAttr.split('.')[-1]
        self.switchControl = getDestination(dataNode, 'switchControl')

        # Resultants.
        self.bufferResultant = getDestination(dataNode, 'bufferResultant')
        self.toeResultant = getControlResultantAndDrivers(self.toeFkControl)[0]
        self.footResultant = getControlResultantAndDrivers(self.footFkControl)[0]
        self.kneeResultant = getControlResultantAndDrivers(self.kneeFkControl)[0]
        self.hipResultant = getControlResultantAndDrivers(self.hipFkControl)[0]

        self.fkControls = [self.hipFkControl, self.kneeFkControl, self.footFkControl]
        if self.toeFkControl:
            self.fkControls.append(self.toeFkControl)
        self.ikControls = [self.kneeControl, self.footControl]
        if self.toeControl:
            self.ikControls.append(self.toeControl)

        self.fkMarkers = getMarkers(self.fkControls)
        self.ikMarkers = getMarkers(self.ikControls)


class Tail(Data):
    def __init__(self, dataNode):
        Data.__init__(self, dataNode)

        self.switchControlAndAttr = getSource(dataNode, 'switchControlAndAttr', plugs=True)
        self.switchControlAttr = self.switchControlAndAttr.split('.')[-1]
        self.switchControl = getDestination(dataNode, 'switchControl')

        self.fkControls = getDestinations(dataNode, 'fkControls')
        self.ikControls = getDestinations(dataNode, 'ikControls')
        self.resultants = getDestinations(dataNode, 'resultants')

        self.fkMarkers = getMarkers(self.fkControls)
        self.ikMarkers = getMarkers(self.ikControls)


class Generic(Data):
    def __init__(self, dataNode):
        Data.__init__(self, dataNode)

        self.controls = getDestinations(dataNode, 'controls')
        self.fkControls = getDestinations(dataNode, 'fkControls')
        self.ikControls = getDestinations(dataNode, 'ikControls')


class ZLeg(Data):
    def __init__(self, dataNode):
        Data.__init__(self, dataNode)

        # IK controls.
        self.kneeControl = getDestination(dataNode, 'kneeControl')
        self.tarsusControl = getDestination(dataNode, 'tarsusControl')
        self.footControl = getDestination(dataNode, 'footControl')
        self.pasternControl = getDestination(dataNode, 'pasternControl')
        self.hoofControl = getDestination(dataNode, 'hoofControl')

        # FK controls.
        self.upperLegFkControl = getDestination(dataNode, 'upperLegFkControl')
        self.lowerLegFkControl = getDestination(dataNode, 'lowerLegFkControl')
        self.tarsusFkControl = getDestination(dataNode, 'tarsusFkControl')
        self.ankleFkControl = getDestination(dataNode, 'ankleFkControl')
        self.toeFkControl = getDestination(dataNode, 'toeFkControl')

        # Resultants.
        self.upperLegResultant = getControlResultantAndDrivers(self.upperLegFkControl)[0]
        self.lowerLegResultant = getControlResultantAndDrivers(self.lowerLegFkControl)[0]
        self.tarsusResultant = getControlResultantAndDrivers(self.tarsusFkControl)[0]
        self.ankleResultant = getControlResultantAndDrivers(self.ankleFkControl)[0]
        self.toeResultant = getControlResultantAndDrivers(self.toeFkControl)[0]

        self.switchControlAndAttr = getSource(dataNode, 'switchControlAndAttr', plugs=True)
        self.switchControlAttr = self.switchControlAndAttr.split('.')[-1]
        self.switchControl = getDestination(dataNode, 'switchControl')
        self.setupGroup = getDestination(dataNode, 'setupGroup')


class HoofedLeg(Data):
    def __init__(self, dataNode):
        Data.__init__(self, dataNode)

        # IK controls.
        self.fibulaTibiaIKControl = getDestination(dataNode, 'fibulaTibiaIKControl')
        self.metaTarsalsIKControl = getDestination(dataNode, 'metaTarsalsIKControl')
        self.proximalPhalangesIKControls = getDestination(dataNode, 'proximalPhalangesIKControls')
        # FK controls.
        self.femurFKControl = getDestination(dataNode, 'femurFKControl')
        self.fibulaTibiaFKControl = getDestination(dataNode, 'fibulaTibiaFKControl')
        self.tarsalsFKControl = getDestination(dataNode, 'tarsalsFKControl')
        self.metaTarsalsFKControl = getDestination(dataNode, 'metaTarsalsFKControl')
        self.proximalPhalangesFKControls = getDestination(dataNode, 'proximalPhalangesFKControls')

        # Resultants
        self.femurResultant = self.femurFKControl
        self.fibulaTibiaResultant = getControlResultantAndDrivers(self.fibulaTibiaFKControl)[0]
        self.tarsalsResultant = getControlResultantAndDrivers(self.tarsalsFKControl)[0]
        self.metaTarsalsResultant = getControlResultantAndDrivers(self.metaTarsalsFKControl)[0]
        self.proximalPhalangesResultant = getControlResultantAndDrivers(self.proximalPhalangesFKControls)[0]

        self.switchControlAndAttr = getSource(dataNode, 'switchControlAndAttr', plugs=True)
        self.switchControlAttr = self.switchControlAndAttr.split('.')[-1]


class WeaponHub(Data):
    def __init__(self, dataNode):
        Data.__init__(self, dataNode)

        # Weapon hub control.
        self.bControl = getDestination(dataNode, 'bControl')

        self.weaponsGroup = getDestination(dataNode, 'weaponsGroup')


class Weapon(Data):
    def __init__(self, dataNode):
        Data.__init__(self, dataNode)

        self.mainWeaponControl = getDestination(dataNode, 'mainWeaponControl')
        self.mainWeaponControlGroup = getDestinations(dataNode, 'mainWeaponControlGroup')
        self.mainParentConstraint = getDestinations(dataNode, 'mainParentConstraint')
        self.weaponControl = getDestination(dataNode, 'weaponControl')
        self.weaponControlGroup = getDestinations(dataNode, 'weaponControlGroup')
        self.weaponResultant = getDestination(dataNode, 'weaponResultant')
        self.weaponVersion = getDestination(dataNode, 'weaponVersion')
        self.bControlAndAttr = getSource(dataNode, 'bControlAndAttr', plugs=True)
        self.bControl, self.bControlAttr = self.bControlAndAttr.split('.')
        self.holsterResultants = getDestinations(dataNode, 'holsterResultants')
        self.holsterConditions = getDestinations(dataNode, 'holsterConditions')
        self.staticDrivers = getDestinations(dataNode, 'staticDrivers')


class KratosChain(Data):
    def __init__(self, dataNode):
        Data.__init__(self, dataNode)

        self.twoCtrlCurve = getDestination(dataNode, 'twoCtrlCurve')
        self.rebuiltCurve = getDestination(dataNode, 'rebuiltCurve')
        self.twelveCtrlCurve = getDestination(dataNode, 'twelveCtrlCurve')
        self.resultantCurve = getDestination(dataNode, 'resultantCurve')

        self.loResControls = getDestinations(dataNode, 'loResControls')
        self.hiResControls = getDestinations(dataNode, 'hiResControls')
        self.resultants = getDestinations(dataNode, 'resultants')

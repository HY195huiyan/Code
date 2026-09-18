from maya import cmds as mc


def addObjsAttrs(attributes, objs=None, attrType=None):
    ''' Sets the value and state of multiple objs and attributes.
        attributes =    ['aAttr', 'bAttr', ...]
        objs =          ['aObj', 'bObj', ...]
        attrType =      Maya dataType to be used
    '''

    if attrType is None:
        attrType = 'bool'

    if objs is None:
        objs = mc.ls(sl=True, l=True)
        if not len(objs):
            mc.warning('Please select or provide a list of objects')
            return False

    if isinstance(objs, str) or isinstance(objs, str):
        objs = [objs]
    if isinstance(attributes, str) or isinstance(attributes, str):
        attributes = [attributes]

    for obj in objs:
        lockState = mc.lockNode(obj, q=True)[0]
        if lockState:
            mc.lockNode(obj, lock=False)

        for attribute in attributes:
            if mc.attributeQuery(attribute, node=obj, exists=True) is True:
                mc.warning('Attribute "{}" already exists on node {}'.format(attribute, obj))
                continue

            if attrType.lower() not in ('string', 'str'):
                mc.addAttr(obj, longName=attribute, niceName=attribute, attributeType=attrType)
            else:
                mc.addAttr(obj, longName=attribute, niceName=attribute, dataType='string')

        mc.lockNode(obj, lock=lockState)

    return True


def setObjsAttrs(objs, attributes, value=None, **kwargs):
    ''' Sets the value and state of multiple objs and attributes.
        objs =          ['aObj', 'bObj', ...]
        attributes =    ['aAttr', 'bAttr', ...]
        value =         int or string etc. Value will be set on all the attributes passed in.
        **kwargs =      {'lock': True, 'ChannelBox': 'False', ...}
    '''
    if isinstance(objs, str) or isinstance(objs, str):
        objs = [objs]
    if isinstance(attributes, str) or isinstance(attributes, str):
        attributes = [attributes]

    # Filter non existing objs
    objs = mc.ls(objs)

    for obj in objs:
        for attribute in attributes:
            if mc.attributeQuery(attribute, node=obj, exists=True) is True:
                objAttr = '{}.{}'.format(obj, attribute)

                if value is None:
                    mc.setAttr(objAttr, **kwargs)
                elif mc.getAttr(objAttr, settable=True) is True:
                    mc.setAttr(objAttr, value, **kwargs)
                else:
                    # Try setting the states first, see if it becomes settable afterwards
                    mc.setAttr(objAttr, **kwargs)

                    if mc.getAttr(objAttr, settable=True) is True:
                        mc.setAttr(objAttr, value)
                    else:
                        mc.warning('{} is not settable.')


def connectObjsAttrs(objs, attributes):
    ''' Connects multiple obj attributes. Direction of connection is based on index,
    for example obj[0] --> obj[1], and so on.
        objs =          ['aObj', 'bObj', ...]
        attributes =    ['aAttr', 'bAttr', ...]
    '''

    if isinstance(objs, str) or isinstance(objs, str):
        objs = [objs]
    if isinstance(attributes, str) or isinstance(attributes, str):
        attributes = [attributes]

    # Filter non existing objs
    objs = mc.ls(objs)

    for i in range(len(objs)):
        if i < len(objs) - 1:
            for attribute in attributes:
                if mc.attributeQuery(attribute, node=objs[i], exists=True) is True:
                    if mc.attributeQuery(attribute, node=objs[i + 1], exists=True) is True:
                        sourceAttr = '{}.{}'.format(objs[i], attribute)
                        destAttr = '{}.{}'.format(objs[i + 1], attribute)
                        mc.connectAttr(sourceAttr, destAttr, force=1)
                        continue

                mc.warning("connectObjsAttrs: The attribute, {}, does not exist on one or more of the "
                           "provided objects.".format(attribute))


def lockAndHideAttrs(nodes, translate=True, rotate=True, scale=True, attrs=[]):
    """lock and hide translation, rotation and scale attributes

    Args:
        node (str): node object name
        translate (bool, optional): if true, lock and hide translation attributes
        rotate (bool, optional): if true, lock and hide rotation attributes
        scale (bool, optional): if true, lock and hide scale attributes
        attrs (list, optional): additional attributes need to lock and hide
    """
    if translate:
        for axis in 'xyz':
            setObjsAttrs(nodes, 't{0}'.format(axis), lock=True, channelBox=False, keyable=False)
    if rotate:
        for axis in 'xyz':
            setObjsAttrs(nodes, 'r{0}'.format(axis), lock=True, channelBox=False, keyable=False)
    if scale:
        for axis in 'xyz':
            setObjsAttrs(nodes, 's{0}'.format(axis), lock=True, channelBox=False, keyable=False)

    setObjsAttrs(nodes, attrs, lock=True, channelBox=False, keyable=False)


def unlockAttrs(nodes, translate=True, rotate=True, scale=True, attrs=[]):
    """unlock and show translation, rotation and scale attributes

    Args:
        node (str): node object name
        translate (bool, optional): if true, unlock and unhide translation attributes
        rotate (bool, optional): if true, unlock and unhide rotation attributes
        scale (bool, optional): if true, unlock and unhide rotation attributes
        attrs (list, optional): additional attributes need to unlock and unhide
    """
    if translate:
        for axis in 'xyz':
            setObjsAttrs(nodes, 't{0}'.format(axis), lock=False, keyable=True)
    if rotate:
        for axis in 'xyz':
            setObjsAttrs(nodes, 'r{0}'.format(axis), lock=False, keyable=True)
    if scale:
        for axis in 'xyz':
            setObjsAttrs(nodes, 's{0}'.format(axis), lock=False, keyable=True)

    setObjsAttrs(nodes, attrs, lock=False, keyable=True)


def _getAttrIndexData(attr):
    """
    Returns the value between the brackets of a multi attribute.
    Only the leaf attribute is considered (the last attribute if attr is a nested attribute)

    Examples:
    node.parents[5].child[1] -> '1'
    node.parents[5].child[5:10] -> '5:10'
    node.parents[5].child -> ValueError("Attribute is not a multi-attr")
    """
    leafAttr = attr.split('.')[-1]
    if '[' not in leafAttr:
        raise ValueError("Attribute is not a multi-attr (%s): '%s'" % (leafAttr, attr))
    return leafAttr.rsplit('[', 1)[1].split(']')[0]


def getAttrIndices(attr):
    """
    Returns the range of indices in a multi-attribute.

    mesh.vtx[5:10] -> [5, 6, 7, 8, 9, 10]
    mesh.vtx[5] -> [5]
    """
    index = _getAttrIndexData(attr)
    if ':' in index:
        # A range of indices (ie mesh.vtx[5:10])
        start, end = index.split(':')
        return list(range(int(start), int(end) + 1))

    # A single index (ie mesh.vtx[5])
    return [int(index)]


def getAttrListIndices(attrs):
    """
    Returns a list of the indices in a list of attributes

    Example:
    [mesh.vtx[5], mesh.vtx[7:10]] -> [5, 7, 8, 9, 10]
    """
    indices = set()
    for attr in attrs:
        indices.update(getAttrIndices(attr))

    return sorted(indices)


def getVertexComponentList(vertexIndices):
    """Collapse a list of vertex indices

    Args:
        vertexIndices (list): list of vertex index

    Returns:
        TYPE: Collapsed vertex components: [0, 1, 2, ,3 ,4] -> vtx[0: 4]
    """
    vertexIndices = sorted(vertexIndices)
    previousIndex = None
    componentList = []
    for i, vertIndex in enumerate(vertexIndices):
        # init
        if previousIndex is None:
            previousIndex = vertIndex
            startIndex = vertIndex
            continue

        if vertIndex - previousIndex == 1:
            if i < len(vertexIndices) - 1:
                previousIndex = vertIndex
            elif i == len(vertexIndices) - 1:
                # last element in the list
                componentList.append('vtx[{0}:{1}]'.format(startIndex, vertIndex))

        elif vertIndex - previousIndex > 1:
            if i < len(vertexIndices) - 1:
                if previousIndex == startIndex:
                    componentList.append('vtx[{0}]'.format(previousIndex))
                else:
                    componentList.append('vtx[{0}:{1}]'.format(startIndex, previousIndex))

                startIndex = vertIndex
                previousIndex = vertIndex

            elif i == len(vertexIndices) - 1:
                # last element in the scene
                componentList.append('vtx[{0}:{1}]'.format(startIndex, previousIndex))
                componentList.append('vtx[{0}]'.format(vertIndex))

    return componentList


def listAnimatedAttrs(node):
    """list all animated attributes of an object"""
    result = []
    attrs = mc.listConnections(node, c=1, scn=1, d=0, p=1, s=1, type='animCurve')
    count = len(attrs)

    for i in range(0, count, 2):
        result.append(attrs[i])

    return result


def isAttrUserDefined(node, attr):
    attrs = mc.listAttr(node, userDefined=1)
    if len(attrs) > 0:
        for attrName in attrs:
            if attrName == attr:
                return True

    return False


def moveAttrs(nodeAndAttributes, toObject, force=True):
    """
    moves attributes and connections from one node to another
    :param nodeAndAttributes: list of nodes w/ attrs -> node.attr
    :param toObject: the object to receive the attributes being moved
    :param force: forces new connection if attribute existed and was connected
    :return:
    """
    supportedAttrTypes = ('long', 'float', 'double', 'int', 'short', 'bool')
    moved = []
    for nodeAndAttr in nodeAndAttributes:
        node, attr = nodeAndAttr.split('.', 1)
        inputs = mc.listConnections(nodeAndAttr, s=True, d=False, scn=True, p=True, c=True)
        outputs = mc.listConnections(nodeAndAttr, s=False, d=True, scn=True, p=True, c=True)

        locked = False
        if not mc.attributeQuery(attr, node=toObject, exists=True):
            initValue = mc.getAttr(nodeAndAttr)
            defaultValue = mc.attributeQuery(attr, node=node, listDefault=True)
            attrType = mc.getAttr(nodeAndAttr, type=True)

            if attrType not in supportedAttrTypes:
                continue

            channelBox = mc.attributeQuery(attr, node=node, channelBox=True)
            keyable = mc.getAttr(nodeAndAttr, keyable=True)
            locked = mc.getAttr(nodeAndAttr, lock=True)

            mc.addAttr(toObject, k=keyable, ln=attr, nn=attr, at=attrType, dv=defaultValue[0])

            if mc.addAttr(nodeAndAttr, q=True, hasMinValue=True):
                minVal = mc.attributeQuery(attr, node=node, min=True)[0]
                mc.addAttr(toObject + '.' + attr, e=True, min=minVal)

            if mc.addAttr(nodeAndAttr, q=True, hasMaxValue=True):
                maxVal = mc.attributeQuery(attr, node=node, max=True)[0]
                mc.addAttr(toObject + '.' + attr, e=True, max=maxVal)

            if channelBox:
                mc.setAttr(toObject + '.' + attr, channelBox=channelBox)

            mc.setAttr(toObject + '.' + attr, initValue)

        if not inputs and not outputs:
            continue

        if inputs:
            # if the attribute already existed and was connected - skip if not using 'force'
            if not force and mc.listConnections(toObject + '.' + attr, s=True, d=False, scn=True):
                continue

            if mc.getAttr(toObject + '.' + attr, lock=True):
                mc.setAttr(toObject + '.' + attr, lock=False)
            mc.connectAttr(inputs[1], toObject + '.' + attr, force=True)

        if outputs:
            for i in range(0, len(outputs), 2):
                outputLocked = False
                if mc.getAttr(outputs[i + 1], lock=True):
                    mc.setAttr(outputs[i + 1], lock=False)
                    outputLocked = True
                mc.connectAttr(toObject + '.' + attr, outputs[i + 1], f=True)
                if outputLocked:
                    mc.setAttr(outputs[i + 1], lock=True)

        if locked:
            mc.setAttr(toObject + '.' + attr, lock=True)

        moved.append([nodeAndAttr, toObject + '.' + attr])

    return moved


def renameAttr(attrName, node, longName, niceName=""):
    """
    Renames the given user-defined attribute to the name given in the string argument.

    Args:
        attrName (string): the old long name for the attribute
        node (string): the name of the node
        longName (string): the new long name for the attribute
        niceName (nice name): the nice name of the attribute for display in the UI.

    """
    if not mc.attributeQuery(attrName, node=node, exists=True):
        mc.warning("Attribute {0} does not exist on node {1}".format(attrName, node))
        return
    attribute = "{0}.{1}".format(node, attrName)
    if niceName:
        mc.addAttr(attribute, e=True, niceName=niceName)
    mc.renameAttr(attribute, longName)
    return "{0}.{1}".format(node, longName)


def setOutlinerColor(node, color=[0, 1, 1]):
    if color == None:
        mc.setAttr('%s.useOutlinerColor' % node, False)
    else:
        mc.setAttr('%s.useOutlinerColor' % node, True)
        mc.setAttr('%s.outlinerColor' % node, color[0], color[1], color[2])


# ...refresh
# mel.eval('AEdagNodeCommonRefreshOutliners();')

def addBakeAttrs(node, editOutlinerColor=True, color=[0, 1, 1]):
    # ...vars
    attr_bake = '_bake'
    attr_keepJoint = '_KeepJoint'

    # ...add attrs
    if mc.objExists(node):
        for attr in [attr_bake, attr_keepJoint]:
            if not mc.objExists('%s.%s' % (node, attr)):
                mc.addAttr(node, ln=attr, at='bool', k=False, dv=True)
            else:
                mc.setAttr('%s.%s' % (node, attr), lock=False)
                mc.setAttr('%s.%s' % (node, attr), True)
        # ...color hierarchy
        if editOutlinerColor:
            setOutlinerColor(node, color=color)

    return True


def removeBakeAttrs(node, editOutlinerColor=True):
    # ...vars
    attr_bake = '_bake'
    attr_keepJoint = '_KeepJoint'

    success = False
    if mc.objExists(node):
        for attr in [attr_bake, attr_keepJoint]:
            if mc.objExists('%s.%s' % (node, attr)):
                mc.setAttr('%s.%s' % (node, attr), lock=False)
                mc.deleteAttr('%s.%s' % (node, attr))
                success = True
        # ...color hierarchy
        if editOutlinerColor:
            setOutlinerColor(node, color=None)
    # ...success
    if not success:
        return False
    return True

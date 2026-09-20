

import maya.cmds as mc


def getNamespace(nodes, asList=False, asString=False):
    '''returns the namespace of one or more objects

       Arguments:
       nodes: single string or list of strings
       asList: boolean that will pass back dictionary values instead of dict
       asString: return the first item from nsDict.values()
    '''

    nsDict = {}

    selString = mc.ls(nodes, showNamespace=True)
    for i in range(0, len(selString), 2):
        if str(selString[i + 1]) == ':':
            nsDict[selString[i]] = None
        else:
            nsDict[selString[i]] = selString[i + 1]

    if asList:
        return list(nsDict.values())
    elif asString:
        if not len(list(nsDict.values())):
            return None
        else:
            return list(nsDict.values())[0]
    else:
        return nsDict


def deleteGhostIntermediateObjects(nodeType):
    '''removes all intermediate objects not historically linked'''

    meshes = mc.ls(type=nodeType)
    intObjs = [x for x in meshes if mc.getAttr(x + '.intermediateObject')]

    deleted = []
    for obj in intObjs:
        hist = mc.listHistory(obj, f=True, ha=True, ac=True)
        hist.extend(mc.listHistory(obj, ha=True, ac=True))

        while obj in hist:
            hist.remove(obj)

        if len(hist) < 1:
            mc.delete(obj)
            deleted.append(obj)

    return deleted


def shapeTypeHierFilter(transform, shapeType=None):
    """
    checks that the input transform is a parent of a mesh shape
    OR that any other child transforms are mesh shape parents
    :return: True if mesh transforms contain a shape
    """
    transforms = [transform]
    temp = mc.listRelatives(transform, ad=True, type='transform')
    if temp:
        transforms.extend(temp)
    for node in transforms:
        if shapeType is None:
            if mc.listRelatives(node, shapes=True):
                return True
        elif getShapeNodeOfType(node, shapeType):
            return True
    return False


def getTransformsFromShapeType(shapeType, nodes=None, longName=True):
    ''' returns transforms that have immediate children of specified type '''
    # ensure is list
    if isinstance(nodes, str) or isinstance(nodes, str):
        nodes = [nodes]

    # if nothing - get selection
    if nodes is None:
        nodes = mc.ls(sl=True, l=longName)

    if not nodes:
        return None

    transforms = []
    for node in nodes:
        shapes = getShapeNodeOfType(node, shapeType)
        if shapes is not None:
            transforms.append(node)

    return transforms


def getShapeNodeOfType(obj, shapeType):
    foundShape = None
    if not mc.nodeType(obj) == 'transform':
        mc.warning('The provided object is not a transform')
        return None
    shapes = mc.listRelatives(obj, shapes=True, noIntermediate=True, f=True)
    if shapes:
        for shape in shapes:
            if mc.nodeType(shape) == shapeType:
                foundShape = shape
                return foundShape
    return None


def shapeParent(shapes, transform):
    """
    parents shape to transform
    :param shapes: shape node(s) to move under...
    :param transform: ... new transform parent of shape
    :return: new names of shapes
    """

    sel = mc.ls(sl=True)

    # ensure is list
    if isinstance(shapes, str) or isinstance(shapes, str):
        shapes = [shapes]

    finalShapes = []
    for shape in shapes:
        if mc.nodeType(shape) in ('joints', 'transform'):
            shape = mc.listRelatives(shape, shapes=True, f=True)
            if shape:
                finalShapes.extend(shape)
            if not shape:
                mc.warning('No shape was provided or could be found from {}'.format(shape))
        else:
            finalShapes.append(shape)

    finalSel = sel[:]
    for i in range(len(finalShapes)):
        selTransform = mc.listRelatives(finalShapes[i], parent=True)[0]
        finalSel = list(set(finalSel) - set([finalShapes[i], selTransform]))

        shape = mc.parent(finalShapes[i], transform, shape=True, absolute=True)[0]
        newTransform = mc.listRelatives(shape, parent=True)[0]
        mc.makeIdentity(newTransform, apply=True, t=True, r=True, s=True, n=2)
        finalShapes[i] = mc.parent(shape, transform, shape=True, relative=True)[0]
        mc.delete(newTransform)

    if sel:
        if len(sel) == len(finalSel):
            mc.select(sel)
        else:
            mc.select(finalShapes)

    return finalShapes


def getNodeWithMostChildren(nodes):
    '''
    Gets the node with the most children dag objects.
    :param nodes:   ['nodeA', ...]
    :return:        'nodeA'
    '''

    nodes = mc.ls(nodes)

    if len(nodes) < 1:
        mc.warning('Unable to get the node with the most children from: {}'.format(nodes))

        return None

    if isinstance(nodes, str) or isinstance(nodes, str):
        nodes = [nodes]

    topNode = nodes[0]
    childNum = 0

    for node in nodes:
        children = mc.listRelatives(node, allDescendents=True) or []

        if len(children) > childNum:
            childNum = len(children)
            topNode = node

    return topNode


def getTopNodesFromNodes(nodes=None, longName=True):
    '''
    return dictionary of selection or arguments (keys) and values (found top nodes)
    '''

    # ensure is list
    if isinstance(nodes, str) or isinstance(nodes, str):
        nodes = [nodes]

    # if nothing - get selection
    if nodes is None:
        nodes = mc.ls(sl=True, l=longName)

    listLen = len(nodes)

    if not nodes:
        return None

    # long names - gets multiple instances of short names
    topNodeDict = {}
    for node in nodes:
        temp = mc.ls(node, recursive=True, l=True)
        if not temp:
            mc.warning('Node %s does not exist' % node)
        topNodeDict[node] = temp

    longNameLen = len(list(topNodeDict.values()))

    if longNameLen == 0:
        mc.warning('Argument objects do not exist in scene')
        return None

    if not listLen == longNameLen:
        mc.warning('Multiples -OR- some not found')

    for key in topNodeDict:
        nodes = topNodeDict[key]
        temp = []
        for node in nodes:
            if longName:
                topNodeName = '|' + node.split('|')[1]
            else:
                topNodeName = node.split('|')[1]

            temp.append(topNodeName)

        # sort the list of top nodes by hierarchy size
        topNodeDict[key] = sorted(temp, key=lambda i: len(mc.listRelatives(i, ad=True, type='transform') or []),
                                  reverse=True)

    return topNodeDict


def getCleanReferenceNodes():
    """
    returns the references for Character Manager to operate on
    :return: valid maya reference nodes to operate on
    """

    # maya makes its own reference nodes under certain conditions
    ignoredReferenceNames = ('_UNKNOWN_REF_NODE_', 'sharedReferenceNode')
    ignoredReferences = []
    references = mc.ls(references=True) or []
    for ref in references:
        for ignoredName in ignoredReferenceNames:
            if ref.find(ignoredName) > -1:
                ignoredReferences.append(ref)
                break

    references = list(set(references) - set(ignoredReferences))

    junkReferences = []
    for ref in references:
        try:
            mc.referenceQuery(ref, filename=True)
        except Exception as e:
            # print('Exception occurred checking for filename on ref: {}'.format(ref))
            junkReferences.append(ref)

    references = list(set(references) - set(junkReferences))

    return references


def getTopNodeFromRef(ref):
    '''returns the top node with the most children - should be the rigs top node'''
    allReferenceNodes = getCleanReferenceNodes()
    if ref not in allReferenceNodes:
        return None

    nodes = mc.ls(mc.referenceQuery(ref, nodes=True, dp=True), l=True)
    transforms = mc.ls(nodes, type='transform')

    if not transforms:
        mc.warning('no transforms were part of this reference %s' % ref)

    assemblies = mc.ls(assemblies=True)
    topNodes = [i for i in assemblies if i in transforms]

    if not topNodes:
        mc.warning('A top node for reference %s could not be found' % ref)
        return None

    thisTopNode = topNodes[0]
    childNum = 0
    for node in topNodes:
        descendants = mc.listRelatives(node, ad=True)
        if descendants is None:
            continue
        if len(descendants) > childNum:
            thisTopNode = node
            childNum = len(descendants)

    return thisTopNode


def sortHierarchical(transforms, parentToChild=True, longName=False):
    ''' Sort a list of tranforms in hierarchial order (parent to child or child to parent)
        Returns a sorted list of transforms. '''

    # Ensure transforms is a list
    if isinstance(transforms, str) or isinstance(transforms, str):
        transforms = [transforms]

    # Filter out the dgNodes
    if longName:
        transforms = mc.ls(transforms, type='transform', long=True)
    else:
        transforms = mc.ls(transforms, type='transform')

    # Check substance of transforms
    if len(transforms) == 0:
        mc.warning('No transforms detected.')
        return None
    elif len(transforms) == 1:
        return transforms

    sortedTransforms = []

    for transform in transforms:
        if transform in sortedTransforms:
            continue

        # Get the top node and its descendents
        # Iterate up the hierarchy, matching those transforms to transforms passed in argument
        # Adds them to a final list (that is actually child to parent by default)
        topNode = list(getTopNodesFromNodes([transform], longName=False).values())[0]
        if longName:
            hier = mc.listRelatives(topNode, allDescendents=True, fullPath=True) or []
        else:
            hier = mc.listRelatives(topNode, allDescendents=True, path=True) or []
        hier.extend(topNode)

        for node in hier:
            if node in transforms and node not in sortedTransforms:
                sortedTransforms.append(node)

    if parentToChild:
        sortedTransforms.reverse()

    return sortedTransforms


def sortSeperateHierarchies(transforms, parentToChild=True):
    ''' Sort a list of transforms into a list of sepearte hierarchies.
        transforms    = list of transforms
        parentToChild = bool (opt arg for reversing the hierarchy order)
    '''

    # Ensure transforms is a list
    if isinstance(transforms, str) or isinstance(transforms, str):
        transforms = [transforms]

    # Filter out the dgNodes
    transforms = mc.ls(transforms, type='transform')

    # Check substance of transforms
    if len(transforms) == 0:
        mc.warning('No transforms detected.')
        return None
    elif len(transforms) == 1:
        mc.warning('Only 1 transform detected.')
        return [transforms]

    transforms = sortHierarchical(transforms, parentToChild=True)

    # Build a list of seperate transform hierarchy lists
    transformHiers = []
    hierParent = transforms[0]
    for i, iTransform in enumerate(transforms):
        if iTransform == hierParent:
            iTransformChldrn = mc.listRelatives(iTransform, allDescendents=True,
                                                path=True, type='transform') or []

            transformHiers.append([iTransform])

            if i + 1 < len(transforms):
                for jTransform in transforms[i + 1:]:
                    if jTransform in iTransformChldrn:
                        # Add the next transform into this hierarchy parents list
                        transformHiers[-1].append(jTransform)
                    else:
                        # This is the new hiearchy parent to check its children
                        hierParent = jTransform
                        break

    if not parentToChild:
        for hier in transformHiers:
            hier.reverse()

    return transformHiers


def getTopParentsWithinObjs(objs):
    ''' Get/return the top parents from within a list of objs.
        objs = [parentA, childA, parentB, childB]
        Returns [parentA, parentB]
    '''

    topParents = []

    # Get the objs which are the highest objs in their hierarchies
    for obj in objs:
        tempParent = obj
        topParent = obj

        while tempParent:
            if tempParent in objs:
                topParent = tempParent

            tempParent = mc.listRelatives(tempParent, parent=True, path=True)

            if tempParent:
                tempParent = tempParent[0]

        if topParent not in topParents:
            topParents.append(topParent)

    return topParents

def isObjectParentOf(parent, node):
    """check if an object is a parent of the second object at some point in the hierarchy"""
    firstParent = [node]
    if not firstParent:
        return 0
    while firstParent[0] != "":
        firstParent = mc.listRelatives(firstParent, p=1)
        if firstParent:
            if firstParent[0] == parent:
                return 1
        else:
            return 0
    return 0

def findNodeTypeInHierarchy(obj, type):
    """find a type of object in the selected object's Hierarchy"""

    children = mc.listRelatives(obj, c=1, type=type)
    if len(children) == 0:
        transforms = mc.listRelatives(obj, c=1)
        for transform in transforms:
            nodes = findNodeTypeInHierarchy(transform, type)
            if len(nodes):
                children = children + nodes

    return children

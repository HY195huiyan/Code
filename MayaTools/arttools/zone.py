"Functions for working with zones/trigger volumes."

from collections import namedtuple

from maya import cmds


EffectDesc = namedtuple('EffectDesc', ['attr_name', 'nice_name', 'node_name', 'type_name'])

ZONE_TRANSFORM_TYPE = 'smZone'
ZONE_TARGET_SET_ATTRIBUTE = 'targetSet'
ZONE_SHADER_NAME = 'smZoneShader'


DISPLAY_LAYER_COLORS = {
    'EntityZones': 4,  # Dark red
    'SoundZones': 5,  # Dark blue
    'CameraZones': 7,  # Dark green
    'FXVolumes': 14,  # Green
    'TriggerVolumes': 18,  # Cyan
}


# ---------------------------------------------------------------------------
# Bounding box helpers (pure maya.cmds implementation, formerly ..geom.bbox)
# ---------------------------------------------------------------------------

def selection_bounding_box():
    "Returns (min_xyz, max_xyz) for the set of selected transform objects."
    transforms = cmds.ls(selection=True, type='transform', long=True, noIntermediate=True)

    if not transforms:
        cmds.error('Nothing is selected.')

    min_pt = [float('inf')] * 3
    max_pt = [float('-inf')] * 3

    for transform in transforms:
        # cmds.exactWorldBoundingBox returns [xmin, ymin, zmin, xmax, ymax, zmax]
        bb = cmds.exactWorldBoundingBox(transform)
        for i in range(3):
            min_pt[i] = min(min_pt[i], bb[i])
            max_pt[i] = max(max_pt[i], bb[i + 3])

    return min_pt, max_pt


def selection_center_and_size():
    "Returns the center point and dimensions of the selection's bounding box."
    min_pt, max_pt = selection_bounding_box()

    center = [
        (min_pt[0] + max_pt[0]) / 2.0,
        (min_pt[1] + max_pt[1]) / 2.0,
        (min_pt[2] + max_pt[2]) / 2.0,
    ]
    size = [
        max_pt[0] - min_pt[0],
        max_pt[1] - min_pt[1],
        max_pt[2] - min_pt[2],
    ]

    return center, size


# ---------------------------------------------------------------------------
# Zone / trigger volume functions
# ---------------------------------------------------------------------------

def __create_collision_primitive(transform, primitive):
    "Creates a collision primitive shape node."
    name = transform + 'Shape'
    return cmds.createNode(primitive, name=name, parent=transform)


def __create_collision_mesh(transform):
    "Creates a generic poly mesh shape node."
    name = transform + 'Shape'
    shape = cmds.createNode('mesh', name=name, parent=transform)

    poly, = cmds.polyCube(
        object=False,
        width=2, height=2, depth=2,
        subdivisionsX=1, subdivisionsY=1, subdivisionsZ=1,
        axis=(0, 1, 0), createUVs=1, constructionHistory=False,
    )
    cmds.connectAttr(poly + '.output', shape + '.inMesh')

    return shape


def __add_to_display_layer(node, layer):
    "Adds a node to a display layer (creating the layer if necessary)."
    if not cmds.objExists(layer):
        layer = cmds.createDisplayLayer(name=layer, empty=True)
        cmds.setAttr(layer + '.shading', False)
        cmds.setAttr(layer + '.texturing', False)
        layer_color = DISPLAY_LAYER_COLORS.get(layer)
        if layer_color:
            cmds.setAttr(layer + '.color', layer_color)

    cmds.editDisplayLayerMembers(layer, node)


def __create_shading_group(node):
    "Creates a translucent blue shading group for rendering FX nodes if it doesn't already exist"
    zone_sg_name = ZONE_SHADER_NAME + '_SG'
    if not cmds.objExists(ZONE_SHADER_NAME):
        if cmds.objExists(zone_sg_name):
            cmds.delete(zone_sg_name)

        shaderNode = cmds.shadingNode('lambert', asShader=True, n=ZONE_SHADER_NAME)

        cmds.setAttr(shaderNode + '.color', 0, .25, .5, type='double3')
        cmds.setAttr(shaderNode + '.transparency', .7, .7, .7, type='double3')
        SG = cmds.sets(renderable=1, noSurfaceShader=1, empty=1, name=zone_sg_name)
        cmds.connectAttr((shaderNode + '.outColor'), (SG + '.surfaceShader'), f=1)

    cmds.sets(node, e=True, forceElement=zone_sg_name)


def __disconnect_shading_groups(node):
    "Disconnects all shading groups from the given node's shape node."
    shapes = cmds.listRelatives(node, shapes=True, path=True)
    for shape in shapes:
        shading_groups = cmds.listConnections(
            shape, type='shadingEngine',
            connections=True, plugs=True,
            source=False, destination=True,
        )

        for i in range(0, len(shading_groups), 2):
            source, dest = shading_groups[i], shading_groups[i + 1]
            cmds.disconnectAttr(source, dest)


def create_zone(name, collision_primitive=None, display_layer=None):
    """Creates a zone/volume. If a collision primitive node type is supplied
    (e.g. PhysicsCollisionBox), then the zone's shape node will be that type.
    Otherwise, the zone's shape node will be a poly cube.

    If a display layer name is supplied, then the zone will be added to that
    display layer (creating the layer if it does not exist). Default colors for
    a known set of display layers are defined by DISPLAY_LAYER_COLORS.
    """
    transform = cmds.createNode(ZONE_TRANSFORM_TYPE, name=name)

    if collision_primitive:
        shape = __create_collision_primitive(transform, collision_primitive)
    else:
        shape = __create_collision_mesh(transform)

    if display_layer:
        __add_to_display_layer(node=transform, layer=display_layer)

    __create_shading_group(transform)

    cmds.select(transform, replace=True)

    return transform, shape


def create_zone_around_selection(name, display_layer=None):
    """Creates a zone/volume around the currently selected objects. The zone's
    shape will always be a primitive collision box.
    """
    center, size = selection_center_and_size()

    transform, shape = create_zone(
        name, collision_primitive='PhysicsCollisionBox',
        display_layer=display_layer
    )

    cmds.move(
        center[0], center[1], center[2],
        transform, absolute=True, worldSpace=True
    )

    cmds.setAttr(shape + '.sizeX', size[0])
    cmds.setAttr(shape + '.sizeY', size[1])
    cmds.setAttr(shape + '.sizeZ', size[2])

    return transform, shape


def convert_to_zone(transform, display_layer=None):
    """Converts an existing node to a zone/volume. Disconnects any shading
    groups assigned to the zone's shape node.
    """
    assert cmds.nodeType(transform) == 'transform'

    other_transform = cmds.createNode(ZONE_TRANSFORM_TYPE)
    cmds.nodeCast(transform, other_transform, swapValues=True, swapNames=True)
    cmds.delete(other_transform)

    __disconnect_shading_groups(node=transform)

    if display_layer:
        __add_to_display_layer(node=transform, layer=display_layer)

    cmds.select(transform, replace=True)


def __name_prompt(name_prefix):
    "Prompts the user for a name for a zone being created."
    result = cmds.promptDialog(
        title='Zone Name',
        message='Enter Name:', text='',
        button=('Create', 'Cancel'),
        defaultButton='Create', cancelButton='Cancel', dismissString='Cancel'
    )

    if result == 'Create':
        name_suffix = cmds.promptDialog(query=True, text=True)
        return name_prefix + name_suffix
    else:
        return None


CHILD_VOLUME_PROMPT_OPTION_CREATE_CHILD_LINKED = 'Create Child (linked)'
CHILD_VOLUME_PROMPT_OPTION_CREATE_PARENT = 'Create Parent'
CHILD_VOLUME_PROMPT_OPTION_CANCEL = 'Cancel'


def __name_child_prompt(selected_node):
    "Prompts the user for a name for a zone being created and for settings around how to make a 'child' volume"
    return cmds.promptDialog(
        title='Zone Name',
        message='\'Parent\' Volume: {}\r\n\r\nEnter Name:'.format(selected_node), text=selected_node + "_",
        button=(
            CHILD_VOLUME_PROMPT_OPTION_CREATE_CHILD_LINKED,
            CHILD_VOLUME_PROMPT_OPTION_CREATE_PARENT,
            CHILD_VOLUME_PROMPT_OPTION_CANCEL),
        defaultButton=CHILD_VOLUME_PROMPT_OPTION_CREATE_CHILD_LINKED,
        cancelButton=CHILD_VOLUME_PROMPT_OPTION_CANCEL,
        dismissString=CHILD_VOLUME_PROMPT_OPTION_CANCEL
    )


def prompt_create_zone(name_prefix, **kwargs):
    "Creates a zone/volume with a name chosen by the user. If another volume is selected, offer options for creating a 'child' volume"
    selected = cmds.ls(sl=True)
    if len(selected) > 0 and cmds.nodeType(selected[0]) == 'smZone':
        result = __name_child_prompt(selected[0])
        name_suffix = cmds.promptDialog(query=True, text=True)
        name = name_suffix
        if name is not None and result != CHILD_VOLUME_PROMPT_OPTION_CANCEL:
            transform, shape = create_zone(name, **kwargs)
            if result == CHILD_VOLUME_PROMPT_OPTION_CREATE_CHILD_LINKED:
                # connect each of the blenders that were connected to the parent to the child
                __connect_parent_effects_to_child(selected[0], transform)
                __copy_parent_attributes_to_child(selected[0], transform)
            elif result == CHILD_VOLUME_PROMPT_OPTION_CREATE_PARENT:
                pass
            return transform, shape
    else:
        name = __name_prompt(name_prefix)
        if name is not None:
            return create_zone(name, **kwargs)

    return None, None


def __copy_parent_attributes_to_child(parent, child):
    # for the attributes like the transform that we want to copy from parent to child
    cmds.copyAttr(parent, child, values=True, attribute=['r', 't', 's'])
    parentShape = cmds.listRelatives(parent, shapes=True)[0]
    childShape = cmds.listRelatives(child, shapes=True)[0]
    attrs = [".sizeX", ".sizeY", ".sizeZ", ".radius", ".height"]

    for attr in attrs:
        if cmds.attributeQuery(attr, node=parentShape, exists=True) and cmds.attributeQuery(attr, node=childShape, exists=True):
            cmds.setAttr(childShape + attr, cmds.getAttr(parentShape + attr))

    parentTargetSetCount = cmds.getAttr(parent + ".targetSet", size=True)

    for i in range(parentTargetSetCount):
        penetrationMaxAttr = ".targetSet[{}].penetrationMax".format(i)
        effectPriorityAttr = ".targetSet[{}].effectPriority".format(i)
        combatFXAttr = ".targetSet[{}].combatFX".format(i)
        cmds.setAttr(child + penetrationMaxAttr, cmds.getAttr(parent + penetrationMaxAttr))
        cmds.setAttr(child + effectPriorityAttr, cmds.getAttr(parent + effectPriorityAttr))
        cmds.setAttr(child + combatFXAttr, cmds.getAttr(parent + combatFXAttr))


def zigzag(seq):
    return seq[::2], seq[1::2]


def __connect_parent_effects_to_child(parent, child):
    for dst, src in zip(*zigzag(cmds.listConnections(parent, c=True, p=True))):
        # if the attribute category doesn't have "effect" in it, it's not a 'blender'
        if 'effect' not in dst:
            continue
        cmds.connectAttr(src, dst.replace(parent, child))


def prompt_create_zone_around_selection(name_prefix, **kwargs):
    "Creates a zone/volume with a name chosen by the user."
    name = __name_prompt(name_prefix)
    if name is not None:
        return create_zone_around_selection(name, **kwargs)
    else:
        return None, None


def __query(attr, **kwargs):
    "Returns information about an attribute on a zone transform node."
    return cmds.attributeQuery(attr, type=ZONE_TRANSFORM_TYPE, **kwargs)


def effect_target_attributes():
    "Returns a description of every effect target attribute on a zone."
    effect_targets = []

    for attr_name in __query(ZONE_TARGET_SET_ATTRIBUTE, listChildren=True):
        if 'effect' not in __query(attr_name, categories=True):
            continue

        nice_name = __query(attr_name, niceName=True)
        node_name = attr_name.replace('effect', '', 1)
        type_name = 't' + node_name
        desc = EffectDesc(attr_name, nice_name, node_name, type_name)
        effect_targets.append(desc)

    return effect_targets
import re
import maya.cmds as mc

# ============ 可配置项 ============
TRANSLATION_ATTRS = ['tx', 'ty', 'tz']
ROTATION_ATTRS = ['rx', 'ry', 'rz']
SCALE_ATTRS = ['sx', 'sy', 'sz']
DO_NOT_LOCK_ATTR = '_doNotLock'
DO_NOT_LOCK_CHANNELS_ATTR = '_doNotLockChannels'


# ============ 新增：让 controlType 可见 ============
def revealControlTypeAttrs(nodes=None):
    """
    把 controlType 设为通道盒可见。
    nodes 为 None 时，处理场景里所有带 controlType 的节点。
    """
    if nodes is None:
        nodes = mc.ls('*.controlType', objectsOnly=True) or []
    for node in nodes:
        try:
            # channelBox=True 让它显示在通道盒（灰色，不可 K 帧）
            mc.setAttr(node + '.controlType', channelBox=True)
        except Exception:
            pass


def hideControlTypeAttrs(nodes=None):
    """ 可选：解锁时把 controlType 从通道盒收起。 """
    if nodes is None:
        nodes = mc.ls('*.controlType', objectsOnly=True) or []
    for node in nodes:
        try:
            mc.setAttr(node + '.controlType', channelBox=False)
        except Exception:
            pass


# ============ 基础工具 ============
def toggleSegmentScaleCompensateAccess(reveal=True):
    ctrlJoints = mc.ls(['*.controlType', '*.controlLocation'], type='joint', objectsOnly=True)
    ctrlJoints = list(set(ctrlJoints))
    for j in ctrlJoints:
        lockStatus = mc.lockNode(j, query=True)[0]
        mc.lockNode(j, lock=False)
        if reveal:
            mc.setAttr(j + '.segmentScaleCompensate', lock=False)
            mc.setAttr(j + '.segmentScaleCompensate', channelBox=True)
        else:
            mc.setAttr(j + '.segmentScaleCompensate', lock=True)
            mc.setAttr(j + '.segmentScaleCompensate', channelBox=False)
        mc.lockNode(j, lock=lockStatus)


def activateAllDisplayLayersPlayback():
    layers = mc.ls(type='displayLayer')
    if 'defaultLayer' in layers:
        layers.remove('defaultLayer')
    for layer in layers:
        try:
            mc.setAttr(layer + '.hideOnPlayback', False)
            if mc.layerButton(layer, query=True, exists=True):
                mc.layerButton(layer, edit=True, layerHideOnPlayback=False)
        except Exception:
            pass


def setSwitchControlDefault():
    switchControls = mc.ls('*.IKSwitch')
    if not switchControls:
        print('Cannot find switch controls.')
        return
    for ctrl in switchControls:
        sLower = ctrl.lower()
        if 'back' in sLower or 'hand' in sLower:
            mc.setAttr(ctrl, 0)   # FK
        elif 'foot' in sLower:
            mc.setAttr(ctrl, 1)   # IK
    print('Set arms to FK and feet to IK.')


def setAttrOnAllSameAttrs(attr, value):
    for plug in mc.ls('*.' + attr):
        try:
            mc.setAttr(plug, value)
        except Exception:
            pass


def deactivateNCloth():
    for rtc in mc.ls('RuntimeClothControl1', recursive=True):
        for attr in mc.listAttr(rtc, ud=True, string='*_nClothEnable') or []:
            try:
                mc.setAttr('{}.{}'.format(rtc, attr), 0)
            except Exception:
                pass
        try:
            mc.setAttr('{}.{}'.format(rtc, 'startFrame'), 100000)
        except Exception:
            pass


# ============ 局部锁定逻辑 ============
def lockHideTwoHandedConstControls(lock=True):
    controls = mc.ls('*TwoHandedConst*', type='transform')
    for ctrl in controls:
        if mc.objExists(ctrl + '.' + DO_NOT_LOCK_CHANNELS_ATTR):
            continue
        if mc.listRelatives(ctrl, children=True, type='transform') is None:
            try:
                mc.setAttr(ctrl + '.v', lock=False)
                mc.setAttr(ctrl + '.v', not lock)
                mc.setAttr(ctrl + '.v', lock=lock)
            except Exception:
                pass
        for attr in TRANSLATION_ATTRS + ROTATION_ATTRS + ['v']:
            try:
                mc.setAttr(ctrl + '.' + attr, lock=lock)
            except Exception:
                pass


def lockPivotAttrsOnNodes(nodes, lock=True):
    attrs = [
        'rotatePivot', 'rotatePivotX', 'rotatePivotY', 'rotatePivotZ',
        'rotatePivotTranslate', 'rotatePivotTranslateX', 'rotatePivotTranslateY', 'rotatePivotTranslateZ',
        'scalePivot', 'scalePivotX', 'scalePivotY', 'scalePivotZ',
        'scalePivotTranslate', 'scalePivotTranslateX', 'scalePivotTranslateY', 'scalePivotTranslateZ'
    ]
    for node in nodes:
        if lock and mc.listRelatives(node, children=True, type='camera'):
            continue
        isLocked = mc.lockNode(node, q=True, lock=True)[0]
        if isLocked:
            mc.lockNode(node, lock=False)
        for attr in attrs:
            try:
                mc.setAttr(node + '.' + attr, lock=lock)
            except Exception:
                continue
        mc.lockNode(node, lock=isLocked)


def lockTopNodeAndChildrenTRS(topNode, isLock=None):
    if not mc.objExists(topNode):
        return
    nodes = [topNode]
    nodes.extend(mc.listRelatives(topNode, children=True, type='transform') or [])
    for node in nodes:
        for attr in TRANSLATION_ATTRS + ROTATION_ATTRS + SCALE_ATTRS:
            if mc.reference(node + '.' + attr, inr=True) or mc.objExists(node + '.' + DO_NOT_LOCK_CHANNELS_ATTR):
                continue
            mc.setAttr(node + '.' + attr, lock=False)
            attrInput = mc.listConnections(node + '.' + attr, s=True, d=False, scn=True, p=True, c=True)
            if attrInput:
                mc.disconnectAttr(attrInput[1], attrInput[0])
            if attr in SCALE_ATTRS:
                try:
                    mc.setAttr(node + '.' + attr, 1.0)
                except Exception:
                    pass
            else:
                try:
                    mc.setAttr(node + '.' + attr, 0.0)
                except Exception:
                    pass
            if isLock:
                mc.setAttr(node + '.' + attr, lock=True)
        if not isLock:
            try:
                mc.setAttr(node + '.visibility', lock=False)
            except Exception:
                pass
    return nodes


def lockDownRig(lock):
    sel = mc.ls(sl=True, l=True)
    sel = mc.listRelatives(sel, ad=True, f=True) or []
    for item in sel:
        mc.lockNode(item, lock=False)
        udAttrs = mc.listAttr(item, ud=True) or []
        if set(udAttrs) & {'controlType', '_doNotLock'}:
            continue
        skipTypes = ('ikHandle', 'poleVectorConstraint', 'pointConstraint', 'orientConstraint', 'parentConstraint')
        if mc.nodeType(item) in skipTypes:
            for attr in mc.listAttr(item, k=True) or []:
                if mc.objExists(item + '.' + attr):
                    mc.setAttr(item + '.' + attr, lock=lock)
        elif mc.nodeType(item) in ('transform', 'joint') and not mc.objExists(item + '.' + DO_NOT_LOCK_CHANNELS_ATTR):
            shortName = item.rsplit('|', 1)[-1]
            m = re.search(r'\d', shortName)
            if m:
                shortName = shortName[:m.start()]
            patterns = ['Group(0-9)*$', 'GroupA(0-9)*$', 'GroupB(0-9)*$',
                        'GroupFK(0-9)*$', 'GroupIK(0-9)*$', 'GroupIk(0-9)*$', 'GroupFk(0-9)*$']
            if any(re.search(p, shortName) for p in patterns) and not shortName.endswith('PullGroup'):
                for attr in ('tx', 'ty', 'tz', 'rx', 'ry', 'rz', 'sx', 'sy', 'sz', 'v'):
                    mc.setAttr(item + '.' + attr, lock=lock)
        mc.lockNode(item, lock=lock)
    return True


# ============ 角色描述 ============
def make_character(topNode, controlsGroup=None, jointsGroup=None):
    if controlsGroup is None:
        controlsGroup = _find_child_by_name(topNode, 'Controls')
    if jointsGroup is None:
        jointsGroup = _find_child_by_name(topNode, 'Joints')
    return {
        'topNode': topNode,
        'controlsGroup': controlsGroup,
        'jointsGroup': jointsGroup,
    }


def _find_child_by_name(topNode, name):
    candidates = mc.ls(mc.listRelatives(topNode, ad=True, type='transform', f=True) or [], long=True)
    for c in candidates:
        if c.rsplit('|', 1)[-1] == name:
            return c
    return None


def _resolve_character(char):
    if isinstance(char, dict):
        return char
    return make_character(char)


# ============ 拆开的全局阶段 ============
def global_prepare():
    """ 全局前置：解锁全场景 + 检查 animLayer / 约束 + 显示 controlType。 """
    mc.lockNode(mc.ls(), lock=False)
    toggleSegmentScaleCompensateAccess(reveal=False)

    if mc.ls(type='animLayer'):
        raise Exception('Anim layers exist. Please delete anim layers and retry.')

    allControls = mc.ls('*.controlType', objectsOnly=True) or []
    for ctrl in allControls:
        attrs = mc.listAttr(ctrl, keyable=True, unlocked=True, scalar=True, visible=True,
                            read=True, write=True, connectable=True, multi=True)
        if not attrs:
            continue
        for attr in attrs:
            cons = mc.listConnections(ctrl + '.' + attr, type='constraint', source=True, destination=False)
            if cons:
                raise Exception('%s.%s is constrained. Please fix before locking rig.' % (ctrl, attr))

    # ★ 新增：让所有 controlType 在通道盒可见
    revealControlTypeAttrs(allControls)


def lock_one_character(char):
    char = _resolve_character(char)
    topNode = char['topNode']
    controlsGroup = char['controlsGroup']
    jointsGroup = char['jointsGroup']

    if not mc.objExists(topNode):
        print('skip: topNode not found ->', topNode)
        return

    lockTopNodeAndChildrenTRS(topNode, isLock=True)

    for node in [controlsGroup, jointsGroup]:
        if node and mc.objExists(node):
            mc.select(node, replace=True)
            lockDownRig(True)

    ctrlNodes = mc.ls(mc.listRelatives(topNode, ad=True, type='transform', f=True) or [], long=True)
    ctrlNodes = [n for n in ctrlNodes if mc.objExists(n + '.controlType')]
    lockPivotAttrsOnNodes(ctrlNodes, lock=True)

    # ★ 新增：这个角色的 controlType 也确保可见
    revealControlTypeAttrs(ctrlNodes)


def global_finalize():
    mc.lockNode(mc.ls(), lock=True)

    doNotLocks = mc.ls('*.' + DO_NOT_LOCK_ATTR, objectsOnly=True)
    doNotLocks.extend(mc.ls('*.controlType', objectsOnly=True))
    if doNotLocks:
        mc.lockNode(doNotLocks, lock=False)


# ============ 主入口 ============
def oneClickLocking(characters):
    if isinstance(characters, (str, dict)):
        characters = [characters]

    originalSelection = mc.ls(selection=True)
    mc.select(clear=True)

    global_prepare()

    for char in characters:
        lock_one_character(char)

    global_finalize()

    lockHideTwoHandedConstControls(lock=True)
    setSwitchControlDefault()

    for layer in ['_Controls', '_Curves', '_MeshParted', '_Mesh', '_Joints', '_Character', '_FaceSliders']:
        try:
            mc.setAttr(layer + '.visibility', 1)
            mc.layerButton(layer, edit=True, layerVisible=True)
        except Exception:
            pass
    for layer in ['_Face', '_PoseReaders', '_PSD', '_RBFNodes', '_RBF']:
        try:
            mc.setAttr(layer + '.visibility', 0)
            mc.layerButton(layer, edit=True, layerVisible=False)
        except Exception:
            pass

    activateAllDisplayLayersPlayback()
    deactivateNCloth()

    if originalSelection:
        mc.select(originalSelection, replace=True)
    else:
        mc.select(clear=True)

    print('-= one click rig locking done (multi-character) =-')


def oneClickUnlocking(characters):
    if isinstance(characters, (str, dict)):
        characters = [characters]

    originalSelection = mc.ls(selection=True)
    mc.select(clear=True)

    mc.lockNode(mc.ls(), lock=False)

    for char in characters:
        char = _resolve_character(char)
        topNode = char['topNode']
        controlsGroup = char['controlsGroup']

        if not mc.objExists(topNode):
            continue

        mc.select(topNode, replace=True)
        lockDownRig(False)
        lockTopNodeAndChildrenTRS(topNode, isLock=False)

        ctrlNodes = mc.ls(mc.listRelatives(topNode, ad=True, type='transform', f=True) or [], long=True)
        ctrlNodes = [n for n in ctrlNodes if mc.objExists(n + '.controlType')]
        lockPivotAttrsOnNodes(ctrlNodes, lock=False)

    lockHideTwoHandedConstControls(lock=False)
    toggleSegmentScaleCompensateAccess(reveal=True)

    for layer in ['_Controls', '_Curves', '_MeshParted', '_Mesh', '_Joints', '_Character']:
        try:
            mc.setAttr(layer + '.visibility', 1)
            mc.layerButton(layer, edit=True, layerVisible=True)
            mc.setAttr(layer + '.displayType', 0)
        except Exception:
            pass

    activateAllDisplayLayersPlayback()

    # ★ 可选：解锁时是否收起 controlType。默认保留可见，想收起就取消注释
    # hideControlTypeAttrs()

    if originalSelection:
        mc.select(originalSelection, replace=True)
    else:
        mc.select(clear=True)

    print('-= one click rig unlocking done (multi-character) =-')
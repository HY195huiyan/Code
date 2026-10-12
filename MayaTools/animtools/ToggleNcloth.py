import maya.cmds as mc

# 存放原 startFrame 的属性名（挂在 RuntimeClothControl1 上）
START_FRAME_CACHE_ATTR = '_nClothStartFrameCache'
DISABLED_START_FRAME = 100000


def _findClothControlNodes():
    """ 找所有布料控制节点，统一返回长名。 """
    nodes = set()
    for n in mc.ls(type='transform', long=True) or []:
        if mc.listAttr(n, ud=True, string='*_nClothEnable'):
            nodes.add(n)
    return sorted(nodes)


def _getNClothEnableAttrs(node):
    """ 取节点上所有以 _nClothEnable 结尾的自定义属性。 """
    return mc.listAttr(node, ud=True, string='*_nClothEnable') or []


def _ensureCacheAttr(node):
    """ 确保节点上有存原 startFrame 的属性。 """
    if not mc.attributeQuery(START_FRAME_CACHE_ATTR, node=node, exists=True):
        mc.addAttr(node, ln=START_FRAME_CACHE_ATTR, at='long')
    return node + '.' + START_FRAME_CACHE_ATTR


# ============ 对外接口 ============
def setNClothEnabled(enabled):
    """
    开/关布料。
    enabled=True  -> 可用：*_nClothEnable=1，startFrame 恢复原值
    enabled=False -> 不可用：*_nClothEnable=0，startFrame=100000
    """
    nodes = _findClothControlNodes()
    if not nodes:
        print('No cloth control nodes found.')
        return

    for node in nodes:
        # 1. 开关所有 *_nClothEnable
        for attr in _getNClothEnableAttrs(node):
            plug = '{}.{}'.format(node, attr)
            try:
                mc.setAttr(plug, 1 if enabled else 0)
            except Exception as e:
                print('setAttr failed:', plug, e)

        # 2. startFrame 处理
        if mc.attributeQuery('startFrame', node=node, exists=True):
            plug = node + '.startFrame'
            cachePlug = _ensureCacheAttr(node)
            try:
                if enabled:
                    # 恢复：读缓存；没有缓存则设 1
                    if mc.attributeQuery(START_FRAME_CACHE_ATTR, node=node, exists=True):
                        cached = mc.getAttr(cachePlug)
                        mc.setAttr(plug, cached)
                    else:
                        mc.setAttr(plug, 1)
                else:
                    # 关闭：先存原值，再设 100000
                    if not mc.getAttr(cachePlug) or mc.getAttr(cachePlug) == DISABLED_START_FRAME:
                        mc.setAttr(cachePlug, mc.getAttr(plug))
                    mc.setAttr(plug, DISABLED_START_FRAME)
            except Exception as e:
                print('startFrame failed:', plug, e)

    print('NCloth {}: {} node(s)'.format('enabled' if enabled else 'disabled', len(nodes)))


def enableNCloth():
    setNClothEnabled(True)


def disableNCloth():
    setNClothEnabled(False)


def toggleNCloth():
    """ 在当前状态之间切换。 """
    nodes = _findClothControlNodes()
    if not nodes:
        print('No cloth control nodes found.')
        return
    # 以第一个节点的第一个 enable 属性为准判断当前状态
    node = nodes[0]
    attrs = _getNClothEnableAttrs(node)
    if not attrs:
        print('No *_nClothEnable attrs found.')
        return
    current = mc.getAttr('{}.{}'.format(node, attrs[0]))
    setNClothEnabled(not bool(current))
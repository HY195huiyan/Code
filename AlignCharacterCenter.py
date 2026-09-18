from typing import List, Tuple, Optional
import importlib
from maya import cmds
from maya_utils.decorators import viewportOff


def GetWorldPositionXyz(obj: str) -> Tuple[float, float, float]:
    """
    获取对象在世界空间中的平移坐标。
    
    Args:
        obj: 对象名称
        
    Returns:
        (x, y, z) 坐标元组
        
    Raises:
        ValueError: 对象不存在
    """
    if not cmds.objExists(obj):
        raise ValueError(f"对象不存在: {obj}")
    pos = cmds.xform(obj, q=True, ws=True, t=True)
    return float(pos[0]), float(pos[1]), float(pos[2])


def ComputeCenterXz(
    contributors: List[str],
    weights: Optional[List[float]] = None,
    useBoundingBoxCenter: bool = False
) -> Tuple[float, float]:
    """
    计算贡献者在XZ平面上的加权中心位置。
    
    Args:
        contributors: 对象名称列表
        weights: 可选权重列表，长度需与contributors一致
        useBoundingBoxCenter: 是否使用包围盒中心
        
    Returns:
        (centerX, centerZ) 中心坐标
        
    Raises:
        ValueError: contributors为空、权重长度不匹配或对象不存在
    """
    if not contributors:
        raise ValueError("贡献者列表为空")
    
    # 统一验证所有对象
    for obj in contributors:
        if not cmds.objExists(obj):
            raise ValueError(f"贡献者对象不存在: {obj}")
    
    # 处理权重
    if weights is not None:
        weights = list(weights)
        if len(weights) != len(contributors):
            raise ValueError("权重列表长度必须与贡献者列表一致")
    
    sumX = 0.0
    sumZ = 0.0
    sumW = 0.0
    
    for i, obj in enumerate(contributors):
        if useBoundingBoxCenter:
            bb = cmds.exactWorldBoundingBox(obj)
            # exactWorldBoundingBox 返回 [minX, minY, minZ, maxX, maxY, maxZ]
            x = (bb[0] + bb[3]) * 0.5
            z = (bb[2] + bb[5]) * 0.5
        else:
            x, _, z = GetWorldPositionXyz(obj)
        
        w = 1.0 if weights is None else float(weights[i])
        sumX += x * w
        sumZ += z * w
        sumW += w
    
    if sumW == 0.0:
        # 所有权重为零时的后备方案：使用平均权重
        sumW = float(len(contributors))
    
    return sumX / sumW, sumZ / sumW


def get_rigs_from_namespaces(test_objects: List[str]) -> Optional[str]:
    """
    通过扫描场景命名空间来查找角色。
    
    Args:
        test_objects: 用于验证的对象名称列表（不含命名空间）
        
    Returns:
        找到的命名空间，未找到返回None
    """
    # 首先检查测试对象中是否已包含命名空间
    for obj in test_objects:
        if ':' in obj:
            ns = obj.split(':')[0]
            if cmds.namespace(exists=ns):
                return ns
    
    # 获取场景中所有命名空间（递归）
    namespaces = cmds.namespaceInfo(listOnlyNamespaces=True, recurse=True)
    
    # 按深度排序，优先匹配最内层命名空间
    namespaces = sorted(namespaces, key=lambda x: x.count(':'))
    
    for ns in namespaces:
        # 跳过系统命名空间
        if ns in ['UI', 'shared', 'default']:
            continue
            
        # 检查该命名空间下是否存在所有测试对象
        all_exist = True
        for obj in test_objects:
            # 如果对象本身已包含命名空间，提取基础名称
            if ':' in obj:
                base_name = obj.split(':')[-1]
            else:
                base_name = obj
            
            full_path = f"{ns}:{base_name}" if ns else base_name
            if not cmds.objExists(full_path):
                all_exist = False
                break
        
        if all_exist and test_objects:
            return ns
    
    return None


def CheckIfRigIsValid(rig: str, test_objects: List[str]) -> bool:
    """
    检查指定命名空间下是否存在所有测试对象。
    
    Args:
        rig: 命名空间名称
        test_objects: 测试对象名称列表（不含命名空间）
        
    Returns:
        所有对象都存在返回True
    """
    if not rig:
        return False
    
    for obj in test_objects:
        # 如果对象已包含命名空间，提取基础名称
        if ':' in obj:
            base_name = obj.split(':')[-1]
        else:
            base_name = obj
        
        full_path = f"{rig}:{base_name}"
        if not cmds.objExists(full_path):
            return False
    
    return True


def GetRigName(test_objects: List[str]) -> Optional[str]:
    """
    从测试对象列表中确定角色的命名空间。
    完全不依赖CharacterManager，使用Maya原生方法。
    
    Args:
        test_objects: 用于验证的对象名称列表
        
    Returns:
        找到的角色名称，未找到返回None
    """
    if not test_objects:
        return None
    
    # 方法1：从测试对象中提取命名空间
    for obj in test_objects:
        if ':' in obj:
            ns = obj.split(':')[0]
            if cmds.namespace(exists=ns):
                # 验证该命名空间下是否存在所有测试对象
                if CheckIfRigIsValid(ns, test_objects):
                    return ns
    
    # 方法2：扫描场景中的所有命名空间
    return get_rigs_from_namespaces(test_objects)


def AlignCenterXzOverTarget(
    contributors: List[str],
    targetObject: str,
    movers: Optional[List[str]] = None,
    weights: Optional[List[float]] = None,
    useBoundingBoxCenter: bool = False,
    freezeOnY: bool = True,
    verbose: bool = False
) -> dict:
    """
    计算贡献者的XZ中心，并将移动对象平移到目标对象的XZ位置上方。
    
    Args:
        contributors: 贡献中心计算的对象列表
        targetObject: 目标对象
        movers: 要移动的对象列表，默认为contributors
        weights: 可选的权重列表
        useBoundingBoxCenter: 是否使用包围盒中心
        freezeOnY: 是否保持Y轴不变
        verbose: 是否打印详细信息
        
    Returns:
        包含计算结果的字典
    """
    if not cmds.objExists(targetObject):
        raise ValueError(f"目标对象不存在: {targetObject}")
    
    if movers is None:
        movers = list(contributors)
    
    # 1) 计算贡献者中心（世界XZ）
    centerX, centerZ = ComputeCenterXz(
        contributors,
        weights=weights,
        useBoundingBoxCenter=useBoundingBoxCenter
    )
    
    # 2) 获取目标XZ位置
    targetX, _, targetZ = GetWorldPositionXyz(targetObject)
    
    # 3) 计算需要应用的偏移量
    deltaX = targetX - centerX
    deltaZ = targetZ - centerZ
    
    # 4) 应用偏移量到移动对象
    for obj in movers:
        if not cmds.objExists(obj):
            raise ValueError(f"移动对象不存在: {obj}")
        curX, curY, curZ = GetWorldPositionXyz(obj)
        newX = curX + deltaX
        newZ = curZ + deltaZ
        cmds.xform(obj, ws=True, t=(newX, curY, newZ))
    
    if verbose:
        print(f"[AlignCenterXzOverTarget] 中心偏移前 XZ: ({centerX:.6f}, {centerZ:.6f})")
        print(f"[AlignCenterXzOverTarget] 目标 XZ:        ({targetX:.6f}, {targetZ:.6f})")
        print(f"[AlignCenterXzOverTarget] 应用偏移:       ({deltaX:.6f}, {deltaZ:.6f})")
        print(f"[AlignCenterXzOverTarget] 移动对象:       {movers}")
    
    return {
        "centerBefore": (centerX, centerZ),
        "targetXz": (targetX, targetZ),
        "appliedDelta": (deltaX, deltaZ),
        "movers": movers
    }


def NudgeContributorsTowardTarget(
    contributors: List[str],
    targetObject: str,
    movers: Optional[List[str]] = None,
    weights: Optional[List[float]] = None,
    fraction: float = 1.0,
    useBoundingBoxCenter: bool = False,
    freezeOnY: bool = True,
    verbose: bool = False
) -> dict:
    """
    类似AlignCenterXzOverTarget，但只移动目标距离的一部分。
    fraction=1.0 完全对齐，0.5 移动一半距离，以此类推。
    """
    if fraction <= 0.0:
        centerX, centerZ = ComputeCenterXz(contributors, weights, useBoundingBoxCenter)
        targetX, _, targetZ = GetWorldPositionXyz(targetObject)
        return {
            "centerBefore": (centerX, centerZ),
            "targetXz": (targetX, targetZ),
            "appliedDelta": (0.0, 0.0),
            "movers": movers or list(contributors)
        }
    
    centerX, centerZ = ComputeCenterXz(
        contributors,
        weights=weights,
        useBoundingBoxCenter=useBoundingBoxCenter
    )
    targetX, _, targetZ = GetWorldPositionXyz(targetObject)
    
    fullDx = targetX - centerX
    fullDz = targetZ - centerZ
    dx = fullDx * float(fraction)
    dz = fullDz * float(fraction)
    
    if movers is None:
        movers = list(contributors)
    
    for obj in movers:
        if not cmds.objExists(obj):
            raise ValueError(f"移动对象不存在: {obj}")
        curX, curY, curZ = GetWorldPositionXyz(obj)
        newX = curX + dx
        newZ = curZ + dz
        cmds.xform(obj, ws=True, t=(newX, curY, newZ))
    
    if verbose:
        print(f"[NudgeContributorsTowardTarget] 中心偏移前 XZ: ({centerX:.6f}, {centerZ:.6f})")
        print(f"[NudgeContributorsTowardTarget] 目标 XZ:        ({targetX:.6f}, {targetZ:.6f})")
        print(f"[NudgeContributorsTowardTarget] 移动比例:       {fraction:.3f}")
        print(f"[NudgeContributorsTowardTarget] 应用偏移:       ({dx:.6f}, {dz:.6f})")
        print(f"[NudgeContributorsTowardTarget] 移动对象:       {movers}")
    
    return {
        "centerBefore": (centerX, centerZ),
        "targetXz": (targetX, targetZ),
        "appliedDelta": (dx, dz),
        "movers": movers
    }


def KeyOnLayer(
    objs: List[str],
    layerName: str,
    times: Optional[List[float]] = None
) -> None:
    """
    将对象的当前值关键帧到动画层。
    
    Args:
        objs: 对象列表
        layerName: 动画层名称
        times: 关键帧时间列表，默认为当前时间
    """
    if not objs:
        return
    
    # 确保图层存在
    if not cmds.objExists(layerName):
        layerName = cmds.animLayer(layerName)
    
    # 确保对象已添加到图层
    sel = cmds.ls(sl=True)
    try:
        cmds.select(objs, r=True)
        cmds.animLayer(layerName, e=True, addSelectedObjects=True)
    except RuntimeError as e:
        print(f"警告: 添加对象到动画层失败: {e}")
    finally:
        cmds.select(sel or [], r=True)
    
    # 设置关键帧时间
    if times is None:
        times = [cmds.currentTime(q=True)]
    
    for t in times:
        cmds.setKeyframe(objs, t=t, animLayer=layerName)


def KeyDeltaOnLayer(
    movers: List[str],
    layerName: str,
    dx: float,
    dz: float,
    time: Optional[float] = None,
    axes: Tuple[str, str] = ("tx", "tz")
) -> None:
    """
    直接将偏移值写入动画层。
    当平移是通过世界空间变换应用到基础姿态时使用。
    
    Args:
        movers: 要关键帧的对象列表
        layerName: 动画层名称
        dx: X轴偏移
        dz: Z轴偏移
        time: 关键帧时间
        axes: 要关键帧的轴
    """
    if not movers:
        return
    
    # 确保图层存在
    if not cmds.objExists(layerName):
        layerName = cmds.animLayer(layerName)
        cmds.setAttr(f"{layerName}.weight", 0.0)
    
    # 确保对象属于该图层
    sel = cmds.ls(sl=True)
    try:
        cmds.select(movers, r=True)
        cmds.scriptEditorInfo(suppressWarnings=True)
        cmds.animLayer(layerName, e=True, addSelectedObjects=True)
    except RuntimeError as e:
        print(f"警告: 添加对象到动画层失败: {e}")
    finally:
        cmds.select(sel or [], r=True)
        cmds.scriptEditorInfo(suppressWarnings=False)
    
    if time is None:
        time = cmds.currentTime(q=True)
    
    for obj in movers:
        if "tx" in axes and cmds.objExists(f"{obj}.tx"):
            cmds.setKeyframe(f"{obj}.tx", t=time, v=float(dx), animLayer=layerName, nr=True)
        if "tz" in axes and cmds.objExists(f"{obj}.tz"):
            cmds.setKeyframe(f"{obj}.tz", t=time, v=float(dz), animLayer=layerName, nr=True)


def KeyWorldOffsetOnLayer(
    movers: List[str],
    layerName: str,
    dx: float,
    dz: float,
    time: Optional[float] = None,
    axes: Tuple[str, str] = ("tx", "tz")
) -> None:
    """
    将世界空间偏移转换为本地平移增量并关键帧到动画层。
    
    方法：
    1. 对所有移动对象应用临时世界空间偏移
    2. 读取移动后的本地平移值
    3. 撤销临时移动
    4. 将计算出的本地增量关键帧到动画层
    
    Args:
        movers: 要移动的对象列表
        layerName: 动画层名称
        dx: X轴世界偏移
        dz: Z轴世界偏移
        time: 关键帧时间
        axes: 要处理的轴
    """
    if not movers:
        return
    
    if time is None:
        time = cmds.currentTime(q=True)
    
    # 确保图层存在并注册对象
    if not cmds.objExists(layerName):
        layerName = cmds.animLayer(layerName)
        cmds.setAttr(f"{layerName}.weight", 0.0)
    
    sel = cmds.ls(sl=True)
    try:
        cmds.select(movers, r=True)
        cmds.scriptEditorInfo(suppressWarnings=True)
        cmds.animLayer(layerName, e=True, addSelectedObjects=True)
    except RuntimeError as e:
        print(f"警告: 添加对象到动画层失败: {e}")
    finally:
        cmds.select(sel or [], r=True)
        cmds.scriptEditorInfo(suppressWarnings=False)
    
    # 构建工作列表，包含通道锁定信息
    items = []
    for obj in movers:
        if not cmds.objExists(obj):
            continue
        
        hasTx = "tx" in axes and cmds.objExists(f"{obj}.tx") and not cmds.getAttr(f"{obj}.tx", l=True)
        hasTz = "tz" in axes and cmds.objExists(f"{obj}.tz") and not cmds.getAttr(f"{obj}.tz", l=True)
        
        if not (hasTx or hasTz):
            continue
        
        preTx = cmds.getAttr(f"{obj}.tx") if hasTx else None
        preTz = cmds.getAttr(f"{obj}.tz") if hasTz else None
        items.append([obj, hasTx, hasTz, preTx, preTz, None, None])  # postTx, postTz 占位
    
    if not items:
        return
    
    # 1) 在单个撤销块中应用世界空间偏移
    cmds.undoInfo(openChunk=True, chunkName="KeyWorldOffsetOnLayer_TempMove")
    try:
        for obj, hasTx, hasTz, preTx, preTz, _, _ in items:
            cmds.xform(obj, ws=True, r=True, t=(float(dx), 0.0, float(dz)))
    finally:
        cmds.undoInfo(closeChunk=True)
    
    # 2) 读取移动后的本地值
    for entry in items:
        obj, hasTx, hasTz, preTx, preTz, _, _ = entry
        postTx = cmds.getAttr(f"{obj}.tx") if hasTx else None
        postTz = cmds.getAttr(f"{obj}.tz") if hasTz else None
        entry[5] = postTx
        entry[6] = postTz
    
    # 3) 撤销临时移动
    prevInfo = cmds.scriptEditorInfo(q=True, suppressInfo=True)
    prevResults = cmds.scriptEditorInfo(q=True, suppressResults=True)
    try:
        cmds.scriptEditorInfo(suppressInfo=True, suppressResults=True)
        cmds.undo()  # 撤销整个块
    finally:
        cmds.scriptEditorInfo(suppressInfo=prevInfo, suppressResults=prevResults)
    
    # 4) 将测量的本地增量关键帧到动画层
    for obj, hasTx, hasTz, preTx, preTz, postTx, postTz in items:
        if hasTx and postTx is not None:
            localDx = float(postTx - preTx)
            cmds.setKeyframe(f"{obj}.tx", t=time, v=localDx, animLayer=layerName, nr=True)
        if hasTz and postTz is not None:
            localDz = float(postTz - preTz)
            cmds.setKeyframe(f"{obj}.tz", t=time, v=localDz, animLayer=layerName, nr=True)


def CenterHeadAndUpperTorso(
    layerName: str,
    targetObjectName: str,
    contributors: List[str],
    movers: List[str],
    rigName: Optional[str] = None,
    weights: Optional[List[float]] = None,
    useBoundingBoxCenter: bool = False,
    fraction: float = 1.0,
    verbose: bool = False
) -> None:
    """
    计算贡献者的XZ中心，并将世界空间偏移关键帧到动画层。
    完全不修改基础姿态，只写入叠加动画。
    
    Args:
        layerName: 动画层名称
        targetObjectName: 目标对象名称（不含命名空间）
        contributors: 贡献中心计算的对象列表（不含命名空间）
        movers: 要移动的对象列表（不含命名空间）
        rigName: 可选，手动指定角色命名空间
        weights: 可选的权重列表
        useBoundingBoxCenter: 是否使用包围盒中心
        fraction: 移动比例 0.0-1.0
        verbose: 是否打印详细信息
    """
    testObjects = [targetObjectName] + contributors + movers
    
    # 获取命名空间
    if rigName is None:
        rigName = GetRigName(testObjects)
        if not rigName and verbose:
            print("[CenterHeadAndUpperTorso] 未找到角色绑定，尝试使用当前命名空间...")
            # 尝试使用当前命名空间
            current_namespace = cmds.namespaceInfo(currentNamespace=True)
            if current_namespace and current_namespace != ':':
                rigName = current_namespace
    
    if not rigName:
        if verbose:
            print("[CenterHeadAndUpperTorso] 错误: 未找到角色绑定，请手动指定 rigName 参数")
        return
    
    # 命名空间限定
    targetObject = f"{rigName}:{targetObjectName}"
    contributors_qualified = [f"{rigName}:{n}" for n in contributors]
    movers_qualified = [f"{rigName}:{n}" for n in movers]
    
    # 验证目标对象
    if not cmds.objExists(targetObject):
        raise ValueError(f"目标对象不存在: {targetObject}")
    
    # 1) 计算贡献者中心（世界XZ）
    centerX, centerZ = ComputeCenterXz(
        contributors_qualified,
        weights=weights,
        useBoundingBoxCenter=useBoundingBoxCenter
    )
    
    # 2) 获取目标世界XZ
    targetX, _, targetZ = GetWorldPositionXyz(targetObject)
    
    # 3) 计算需要的世界空间偏移
    fullDx = targetX - centerX
    fullDz = targetZ - centerZ
    
    # 4) 可选的部分移动
    dx = float(fullDx) * float(fraction)
    dz = float(fullDz) * float(fraction)
    
    # 5) 将世界偏移关键帧到动画层
    currentTime = cmds.currentTime(q=True)
    KeyWorldOffsetOnLayer(
        movers=movers_qualified,
        layerName=layerName,
        dx=dx,
        dz=dz,
        time=currentTime,
        axes=("tx", "tz")
    )
    
    if verbose:
        print(f"[CenterHeadAndUpperTorso] 中心偏移前 XZ: ({centerX:.6f}, {centerZ:.6f})")
        print(f"[CenterHeadAndUpperTorso] 目标 XZ:        ({targetX:.6f}, {targetZ:.6f})")
        print(f"[CenterHeadAndUpperTorso] 移动比例:       {fraction:.3f}")
        print(f"[CenterHeadAndUpperTorso] 关键帧偏移:     ({dx:.6f}, {dz:.6f}) 到图层 '{layerName}' 时间 {currentTime}")
        print(f"[CenterHeadAndUpperTorso] 角色命名空间:   {rigName}")


def GetPlaybackRange() -> Tuple[int, int]:
    """
    获取场景播放范围。
    
    Returns:
        (最小帧, 最大帧)
    """
    minFrame = int(round(cmds.playbackOptions(q=True, minTime=True)))
    maxFrame = int(round(cmds.playbackOptions(q=True, maxTime=True)))
    return minFrame, maxFrame


def ShowWarningDialog(message: str, title: str = "警告") -> str:
    """
    显示警告对话框。
    
    Args:
        message: 警告消息
        title: 对话框标题
        
    Returns:
        按下的按钮文本
    """
    result = cmds.confirmDialog(
        title=title,
        message=str(message),
        button=["确定"],
        defaultButton="确定",
        cancelButton="确定",
        dismissString="确定",
        icon="warning",
        messageAlign="left"
    )
    return result


@viewportOff
def AlignObjectsToTargetForTimeline(
    layerName: str = "AlignToCenter",
    targetObjectName: str = "zeroJointControl1",
    contributors: List[str] = None,
    movers: List[str] = None,
    weights: Optional[List[float]] = None,
    rigName: Optional[str] = None,  # ← 改为必须参数（通过 None 检测）
    showProgress: bool = True,
    verbose: bool = False
) -> None:
    """
    为整个时间线范围对齐对象。
    
    ⚠️ 重要：必须通过 rigName 参数明确指定要处理的角色！
    
    Args:
        layerName: 动画层名称
        targetObjectName: 目标对象名称
        contributors: 贡献者列表
        movers: 移动对象列表
        weights: 权重列表
        rigName: 【必须】手动指定角色命名空间（如 "character_A"）
        showProgress: 是否显示进度条
        verbose: 是否打印详细信息
    """
    # ===== 1. 设置默认值 =====
    if contributors is None:
        contributors = ["HeadControl1", "BackControl3", "PelvisControlA1"]
    if movers is None:
        movers = [
            "PelvisControlA1",
            "BackControlIk3",
            "LeftFootControl1",
            "RightFootControl1",
            "LeftHandControl1",
            "RightHandControl1"
        ]
    
    # ===== 2. 检查是否指定了角色 =====
    if rigName is None:
        error_msg = (
            "❌ 错误：必须指定要处理的角色！\n\n"
            "使用方法：\n"
            "  AlignObjectsToTargetForTimeline(\n"
            "      rigName='character_A',  # ← 明确指定\n"
            "      ...\n"
            "  )\n\n"
            "可用的角色列表：\n"
        )
        
        # 尝试获取可用角色列表
        namespaces = cmds.namespaceInfo(listOnlyNamespaces=True, recurse=True)
        available_rigs = []
        for ns in namespaces:
            if ns not in ['UI', 'shared', 'default']:
                if cmds.objExists(f"{ns}:{targetObjectName}"):
                    available_rigs.append(ns)
        
        if available_rigs:
            error_msg += f"  {', '.join(available_rigs)}"
        else:
            error_msg += "  （未找到任何有效角色）"
        
        print(error_msg)
        ShowWarningDialog(error_msg, title="错误：未指定角色")
        return
    
    # ===== 3. 验证指定的角色是否存在 =====
    testObjects = [targetObjectName] + contributors + movers
    
    if not CheckIfRigIsValid(rigName, testObjects):
        error_msg = (
            f"❌ 错误：角色 '{rigName}' 不存在或无效！\n\n"
            f"请确保以下对象存在：\n"
            f"  {rigName}:{targetObjectName}\n"
        )
        for ctrl in contributors:
            error_msg += f"  {rigName}:{ctrl}\n"
        print(error_msg)
        ShowWarningDialog(error_msg, title="错误：角色无效")
        return
    
    # ===== 4. 确认处理角色 =====
    if verbose:
        print(f"\n{'='*60}")
        print(f"【处理角色】{rigName}")
        print(f"{'='*60}")
    
    # ===== 5. 删除已有图层 =====
    if cmds.objExists(layerName):
        if verbose:
            print(f"删除旧图层: {layerName}")
        cmds.delete(layerName)
    
    # ===== 6. 获取播放范围 =====
    minFrame, maxFrame = GetPlaybackRange()
    total_frames = maxFrame - minFrame + 1
    
    if verbose:
        print(f"播放范围: {minFrame} - {maxFrame} ({total_frames} 帧)")
    
    # ===== 7. 显示进度条 =====
    if showProgress:
        cmds.progressWindow(
            title=f'正在对齐: {rigName}',
            progress=0,
            status=f'处理帧...',
            isInterruptable=True
        )
    
    try:
        for idx, frame in enumerate(range(minFrame, maxFrame + 1)):
            # 检查用户是否取消
            if showProgress and cmds.progressWindow(q=True, isCancelled=True):
                if verbose:
                    print("用户取消操作")
                break
            
            # 更新进度
            if showProgress:
                cmds.progressWindow(
                    e=True,
                    progress=int((idx + 1) / total_frames * 100),
                    status=f'处理第 {frame} 帧 ({idx+1}/{total_frames})'
                )
            
            # 跳转到当前帧
            cmds.currentTime(frame)
            
            # 执行单帧对齐
            CenterHeadAndUpperTorso(
                layerName=layerName,
                targetObjectName=targetObjectName,
                contributors=contributors,
                movers=movers,
                weights=weights,
                rigName=rigName,  # ← 明确传递角色名
                useBoundingBoxCenter=False,
                fraction=1.0,
                verbose=False  # 避免输出过多
            )
            
    finally:
        if showProgress:
            cmds.progressWindow(endProgress=True)
    
    # ===== 8. 启用动画层 =====
    if cmds.objExists(layerName):
        cmds.setAttr(f"{layerName}.weight", 1.0)
        cmds.currentTime(0, e=True, update=True)
        
        if verbose:
            print(f"\n✅ 处理完成！")
            print(f"  角色: {rigName}")
            print(f"  图层: {layerName}")
            print(f"  帧数: {total_frames}")
            print(f"{'='*60}")
    else:
        print(f"❌ 错误：图层 '{layerName}' 创建失败")


def get_available_rigs(target_object_name: str = "zeroJointControl1") -> List[str]:
    """
    获取场景中所有可用的角色命名空间。
    
    Args:
        target_object_name: 用于验证的目标对象名称
        
    Returns:
        角色命名空间列表
    """
    namespaces = cmds.namespaceInfo(listOnlyNamespaces=True, recurse=True)
    rigs = []
    
    for ns in namespaces:
        if ns in ['UI', 'shared', 'default']:
            continue
        
        if cmds.objExists(f"{ns}:{target_object_name}"):
            rigs.append(ns)
    
    return sorted(rigs)


def quick_align(rig_name: str, target_x: float = 15.0, target_z: float = 8.0, 
                layerName: str = None, showProgress: bool = True) -> None:
    """
    快速对齐指定角色到目标位置。
    
    Args:
        rig_name: 角色命名空间
        target_x: 目标 X 位置
        target_z: 目标 Z 位置
        layerName: 动画层名称（默认自动生成）
        showProgress: 是否显示进度
    """
    if layerName is None:
        layerName = f"{rig_name}_Align"
    
    # 移动目标到指定位置
    target_obj = f"{rig_name}:zeroJointControl1"
    if cmds.objExists(target_obj):
        cmds.xform(target_obj, ws=True, t=(target_x, 0, target_z))
        print(f"📍 目标移动到: ({target_x}, {target_z})")
    
    # 执行对齐
    AlignObjectsToTargetForTimeline(
        layerName=layerName,
        targetObjectName="zeroJointControl1",
        contributors=["HeadControl1", "BackControl3", "PelvisControlA1"],
        movers=[
            "PelvisControlA1",
            "BackControlIk3",
            "LeftFootControl1",
            "RightFootControl1",
            "LeftHandControl1",
            "RightHandControl1"
        ],
        rigName=rig_name,
        showProgress=showProgress,
        verbose=True
    )
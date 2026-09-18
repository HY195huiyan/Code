import logging
import tempfile
from pathlib import Path
import maya.cmds as cmds
from pxr import Usd, UsdGeom, UsdUtils

# 尝试导入可选依赖
try:
    import AppLink.process
    HAS_APPLINK = True
except ImportError:
    HAS_APPLINK = False
    print("警告: AppLink不可用")

try:
    import usd2maya.options
    import usd2maya.utils
    import usd2maya.scene
    HAS_USD2MAYA = True
except ImportError:
    HAS_USD2MAYA = False
    print("警告: usd2maya不可用")

try:
    from smproceduraltools.usd import mat_utils
    HAS_MAT_UTILS = True
except ImportError:
    HAS_MAT_UTILS = False
    print("警告: mat_utils不可用")

# 全局服务器变量
_SERVER = None

# 配置日志
import logging as log_mod
logger = log_mod.getLogger("Flattenmesh")
logger.setLevel(log_mod.INFO)

if not logger.handlers:
    handler = log_mod.StreamHandler()
    handler.setLevel(log_mod.INFO)
    formatter = log_mod.Formatter('%(levelname)s: %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)


def processPrims(rootPrim, excludeHide=False):
    """处理USD场景中的prim"""
    if HAS_MAT_UTILS:
        mat_utils.apply_material_swaps(rootPrim)

    toFlatten = set()
    primRange = iter(Usd.PrimRange(rootPrim))
    next(primRange)

    for prim in primRange:
        typeName = prim.GetTypeName()

        # Exclude hidden meshes.
        name = prim.GetName()
        if excludeHide and name.startswith("HIDE_") or name.startswith("MAYA_ONLY"):
            # Handle display layers.
            if api := Usd.CollectionAPI(prim, "displayLayer"):
                toHide = api.ComputeIncludedObjects(api.ComputeMembershipQuery(), prim.GetStage())
                for obj in toHide:
                    if isinstance(obj, Usd.Prim) and obj.IsValid():
                        obj.SetActive(False)
            prim.SetActive(False)
            continue

        # Deactivate invisible meshes.
        if imageable := UsdGeom.Imageable(prim):
            if imageable.ComputeVisibility() == "invisible":
                prim.SetActive(False)
                continue

        # Recurse down refNodes.
        if typeName == "SMSRefNode":
            primRange.PruneChildren()
            toFlatten.update(processPrims(prim, excludeHide=True))
            continue

        # Deactivate shadow proxies.
        if (attr := prim.GetAttribute("_ShadowPreset")) and attr.Get() == "Proxy":
            prim.SetActive(False)
            continue

        # Deactivate sheet meshes.
        if (
            (attr := prim.GetAttribute("_sheet"))
            and attr.Get() is True
            and (attr := prim.GetAttribute("_sheetVisible"))
            and attr.Get() is False
        ):
            prim.SetActive(False)
            continue

        # Deactive automation.
        if (attr := prim.GetAttribute("_automationEmbedType")) and attr.Get():
            prim.SetActive(False)
            continue

        # Deactivate breakable "broken" meshes.
        if (attr := prim.GetAttribute("BS_Breakable__Enable")) and attr.Get() == 1:
            if child := prim.GetChild("Broken"):
                child.SetActive(False)

        # Deactivate all LODs except 0.
        if typeName == "SMSLodGroup":
            rel = prim.GetRelationship("lods") or prim.GetRelationship("sms_lods")
            lods = rel.GetTargets()
            if len(lods) > 1:
                for lod in lods[1:]:
                    if lodPrim := prim.GetStage().GetPrimAtPath(lod):
                        lodPrim.SetActive(False)
            prim.SetTypeName("Xform")
            continue

        # Collect meshes in mask.
        elif typeName == "Mesh":
            toFlatten.add(prim.GetPath())
            primRange.PruneChildren()
            continue

        elif typeName == "Material":
            primRange.PruneChildren()
            continue

        # Clear the types for anything else.
        prim.SetTypeName("Xform")

    return toFlatten


def _get_unique_import_prim(prim) -> str:
    """获取唯一的导入路径"""
    stage = prim.GetStage()
    baseName = prim.GetName()
    path = f"/Import/{baseName}"
    i = 0
    while stage.GetPrimAtPath(path).IsValid():
        path = f"/Import/{baseName}__{i}"
        i += 1
    return path


def _convert_via_applink(temp_dir: Path) -> Path:
    """通过AppLink转换 - 修复版本"""
    global _SERVER
    
    # 导出Maya二进制文件
    filePath = temp_dir / "source_scene.mb"
    actualFile = cmds.file(
        str(filePath),
        type="mayaBinary",
        constructionHistory=False,
        exportSelected=True,
        force=True,
    )

    def _function(mayaFile: str):
        """在独立进程中执行转换"""
        import maya2usd.batch
        import maya2usd.options

        options = maya2usd.options.ExportOptions()
        options.rootUsdPath = "/Root"
        options.useMayaVisibility = True
        conversion = maya2usd.batch.BatchConversion(
            [mayaFile],
            exportOptions=options,
            recurseRefNodes=True,
            useCurrentSceneForSingleFile=True,
        )
        conversion.join()
        return conversion.usdForMayaFile(mayaFile)

    # 初始化AppLink服务器 - 修复版本
    if _SERVER is None:
        try:
            # 尝试方式1: 带logger参数
            logger_ignore = logging.Logger("ignore", logging.CRITICAL + 1)
            _SERVER = AppLink.process.MayaServer(logger=logger_ignore)
        except Exception as e1:
            logger.warning(f"AppLink初始化方式1失败: {e1}")
            try:
                # 尝试方式2: 无参数
                _SERVER = AppLink.process.MayaServer()
            except Exception as e2:
                logger.warning(f"AppLink初始化方式2失败: {e2}")
                try:
                    # 尝试方式3: 使用默认参数
                    import AppLink
                    _SERVER = AppLink.process.MayaServer()
                except Exception as e3:
                    raise RuntimeError(f"AppLink初始化失败: {e3}")

    proxy = _SERVER.proxy(180)
    usdFile = proxy.system.doExec(_function, actualFile)
    return Path(usdFile)


def _convert_via_maya_usd(temp_dir: Path) -> Path:
    """备用转换方法: 使用mayaUSD导出"""
    usd_file = temp_dir / "converted.usd"
    
    # 加载插件
    try:
        if not cmds.pluginInfo("mayaUsdPlugin", query=True, loaded=True):
            cmds.loadPlugin("mayaUsdPlugin", quiet=True)
    except:
        pass
    
    selection = cmds.ls(selection=True, long=True)
    if not selection:
        raise RuntimeError("没有选中的物体")
    
    # 尝试不同的导出方式
    try:
        # 方式1: mayaUSDExport
        if hasattr(cmds, 'mayaUSDExport'):
            cmds.mayaUSDExport(
                file=str(usd_file),
                exportRoots=selection,
            )
            if usd_file.exists():
                return usd_file
    except Exception as e:
        logger.debug(f"mayaUSDExport失败: {e}")
    
    try:
        # 方式2: USDExport
        if hasattr(cmds, 'USDExport'):
            cmds.USDExport(
                file=str(usd_file),
                selection=True,
            )
            if usd_file.exists():
                return usd_file
    except Exception as e:
        logger.debug(f"USDExport失败: {e}")
    
    raise RuntimeError("所有USD导出方式都失败了")


def _convert_to_usd(temp_dir: Path) -> Path:
    """转换Maya到USD - 支持多种转换方式"""
    
    # 首先尝试AppLink
    if HAS_APPLINK:
        try:
            logger.info("尝试使用AppLink转换...")
            return _convert_via_applink(temp_dir)
        except Exception as e:
            logger.warning(f"AppLink转换失败: {e}")
            logger.info("尝试备用转换方法...")
    
    # 备用方法: mayaUSD
    try:
        logger.info("尝试使用mayaUSD导出...")
        return _convert_via_maya_usd(temp_dir)
    except Exception as e:
        logger.error(f"mayaUSD导出失败: {e}")
        raise RuntimeError(f"USD转换失败: {e}")


def run():
    """主函数"""
    # Get selection.
    selection = cmds.ls(selection=True, long=True)
    if not selection:
        raise RuntimeError("Nothing is selected!")
    selectedNode = selection[0]
    
    logger.info("=" * 60)
    logger.info("开始USD扁平化处理")
    logger.info(f"选择的物体: {selectedNode}")
    logger.info("=" * 60)

    # Use a diagnostics delegate to hide cruft of warnings.
    delegate = UsdUtils.CoalescingDiagnosticDelegate()

    # 使用TemporaryDirectory自动清理
    with tempfile.TemporaryDirectory(prefix="usd_flatten_") as td:
        tempDir = Path(td)
        logger.info("临时目录创建成功")

        # Export and convert the selection to USD.
        logger.info("步骤1: 转换Maya到USD...")
        usdFile = _convert_to_usd(tempDir)
        logger.info(f"USD文件创建成功: {usdFile}")

        # Open the USD stage and process it.
        logger.info("步骤2: 处理USD场景...")
        stage = Usd.Stage.Open(str(usdFile))
        layer = stage.GetSessionLayer()
        stage.SetEditTarget(layer)

        toFlatten = processPrims(stage.GetPseudoRoot())
        mask = Usd.StagePopulationMask(toFlatten)
        
        if not toFlatten:
            logger.warning("没有找到需要扁平化的mesh")
            return

        # Create a new prim, "Import", that all the meshes will get lofted into.
        logger.info(f"步骤3: 创建扁平化网格 (共{len(toFlatten)}个)...")
        stage.DefinePrim("/Import", "Xform")
        for path in mask.GetPaths():
            # Create the base prim and reference in the mesh.
            sourcePrim = stage.GetPrimAtPath(path)
            if not sourcePrim:
                continue
            newPath = _get_unique_import_prim(sourcePrim)
            newPrim = stage.DefinePrim(newPath)
            newPrim.GetReferences().AddInternalReference(path)

            # Compute a "flattened" transform for the mesh.
            sourceXform = UsdGeom.Xformable(sourcePrim)
            sourceMatrix = sourceXform.ComputeLocalToWorldTransform(0)
            newXform = UsdGeom.Xformable(newPrim)
            newXform.ClearXformOpOrder()
            newXform.AddTransformOp(opSuffix="flatten").Set(sourceMatrix)

        # Write the USD modifications to disk and import back into Maya.
        logger.info("步骤4: 导入USD回Maya...")
        tempUsd = tempDir / "flattened.usd"
        layer.subLayerPaths.append(str(usdFile))
        layer.Export(tempUsd.as_posix())

        # 创建节点并导入
        newNode = cmds.createNode("transform", name="refnode_import")
        newNode = cmds.ls(newNode, long=True)[0]

        # 导入USD
        if HAS_USD2MAYA:
            # HACK: Clear the MObject cache manually until the fix to usd2maya is in and settled.
            if hasattr(usd2maya.utils, 'maya') and hasattr(usd2maya.utils.maya, '_MOBJECT_CACHE'):
                usd2maya.utils.maya._MOBJECT_CACHE = {}

            options = usd2maya.options.ImportOptions()
            options.customAttributesToConvert = []
            options.parentPath = newNode
            options.rootUsdPath = "/Import"
            usd2maya.scene.importFromFile(tempUsd.as_posix(), importOptions=options)
        else:
            # 备用导入方式
            try:
                if not cmds.pluginInfo("mayaUsdPlugin", query=True, loaded=True):
                    cmds.loadPlugin("mayaUsdPlugin", quiet=True)
                cmds.mayaUSDImport(
                    file=str(tempUsd),
                    parent=newNode,
                    primPath="/Import",
                )
            except Exception as e:
                logger.error(f"USD导入失败: {e}")
                raise

        # Move the new node to wherever the selection was.
        position = cmds.getAttr(f"{selectedNode}.t")[0]
        cmds.move(*position, newNode, preserveChildPosition=True)
        cmds.select(newNode, replace=True)
        
        # 统计结果
        children = cmds.listRelatives(newNode, children=True)
        child_count = len(children) if children else 0
        logger.info(f"✅ 处理完成！新节点: {newNode} (包含 {child_count} 个子物体)")
        logger.info("=" * 60)


# 导出函数供外部调用
__all__ = ['run', 'processPrims']
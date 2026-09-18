
import os
import re
import maya.cmds as cmds


class TileNodeExporter:
    """
    处理TileNode的查找、选择以及导出逻辑
    """
    TILESET_PREFIX = "Tileset"

    @classmethod
    def get_all_tile_nodes(cls):
        """获取场景中所有以 Tileset 开头的 group"""
        tile_nodes = cmds.ls(f"{cls.TILESET_PREFIX}*", type='transform')
        print(f"[TileNodeExporter] 找到 {len(tile_nodes)} 个TileNode: {tile_nodes}")
        return tile_nodes

    @classmethod
    def sanitize_filename(cls, filename):
        """清理文件名，移除非法字符"""
        filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
        filename = filename.strip('. ')
        return filename

    @classmethod
    def export_tile_node(cls, tile_node, export_dir, export_filename_base):
        """导出整个 tileNode 为一个 .mb 文件（包含所有子物体）"""
        print(f"\n{'='*60}")
        print(f"[TileNodeExporter] 导出节点: {tile_node}")

        # 清理文件名
        clean_filename = cls.sanitize_filename(export_filename_base)

        # 构建完整路径
        full_path = os.path.join(export_dir, f"{clean_filename}.mb")

        print(f"[TileNodeExporter] 导出路径: {full_path}")

        # 检查节点下是否有模型
        all_children = cmds.listRelatives(tile_node, allDescendents=True, type='transform') or []
        meshes = []
        for child in all_children:
            shapes = cmds.listRelatives(child, shapes=True, type='mesh') or []
            if shapes:
                meshes.append(child)

        print(f"[TileNodeExporter] 节点下找到 {len(meshes)} 个模型: {[m.split('|')[-1] for m in meshes]}")

        if not meshes:
            cmds.warning(f"TileNode '{tile_node}' 下没有找到任何模型，跳过导出。")
            return False

        # 保存当前选择
        original_selection = cmds.ls(selection=True)

        try:
            # 关键：选择整个 tileNode 及其所有子物体
            cmds.select(tile_node, replace=True, hierarchy=True)

            selected_count = len(cmds.ls(selection=True))
            print(f"[TileNodeExporter] 已选择 {selected_count} 个物体")
            print(f"[TileNodeExporter] 将导出为单个文件: {clean_filename}.mb")
            print("[TileNodeExporter] 所有模型将保持原始位置、旋转和缩放")

            # 导出为.mb文件
            cmds.file(full_path,
                      force=True,
                      type="mayaBinary",
                      exportSelected=True,
                      preserveReferences=False,
                      constructionHistory=True)

            print(f"[TileNodeExporter] ✅ 导出成功: {full_path}")
            return True

        except Exception as e:
            cmds.warning(f"❌ 导出失败 {tile_node}: {str(e)}")
            return False
        finally:
            # 恢复原始选择
            if original_selection:
                cmds.select(original_selection)
            else:
                cmds.select(clear=True)

    @classmethod
    def export_all_tile_nodes(cls, tile_nodes_data):
        """导出所有 tileNode"""
        results = {}
        total_nodes = len(tile_nodes_data)

        for i, (node_name, (export_dir, base_name)) in enumerate(tile_nodes_data.items(), 1):
            print(f"\n{'='*60}")
            print(f"[TileNodeExporter] 进度: {i}/{total_nodes}")
            print(f"[TileNodeExporter] 节点名称: {node_name}")
            print(f"[TileNodeExporter] 导出目录: {export_dir}")
            print(f"[TileNodeExporter] 输出文件: {base_name}.mb")
            print(f"{'='*60}")

            if not export_dir or not base_name:
                cmds.warning(f"TileNode '{node_name}' 的导出路径或文件名为空，跳过。")
                results[node_name] = False
                continue

            # 检查目录是否存在
            if not os.path.exists(export_dir):
                print(f"[TileNodeExporter] 创建目录: {export_dir}")
                try:
                    os.makedirs(export_dir)
                except Exception as e:
                    cmds.warning(f"无法创建目录 {export_dir}: {str(e)}")
                    results[node_name] = False
                    continue

            ok = cls.export_tile_node(node_name, export_dir, base_name)
            results[node_name] = ok

        # 打印最终结果
        print(f"\n{'='*60}")
        print("[TileNodeExporter] 导出完成统计:")
        for node, success in results.items():
            status = "✅ 成功" if success else "❌ 失败"
            print(f"  {status}: {node}")
        print(f"{'='*60}")

        return results

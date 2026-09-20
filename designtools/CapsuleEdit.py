
import os
import json
import maya.cmds as mc
import maya.mel as mel


class CapsuleTool(object):

    def __init__(self):
        self.removeTokens = []

    # --------------------------------------------------------
    # 基础获取
    # --------------------------------------------------------

    def getCapsules(self, selArray=None):
        result = []
        if selArray:
            for sel in selArray:
                if self._isCapsuleTransform(sel):
                    result.append(sel)
                    continue
                children = mc.listRelatives(sel, children=True, path=True) or []
                for c in children:
                    if mc.objectType(c) == "PhysicsCollisionCapsule":
                        result.append(sel)
                        break
        else:
            shapes = mc.ls(type="PhysicsCollisionCapsule") or []
            for s in shapes:
                parent = mc.listRelatives(s, parent=True, path=True)
                if parent:
                    result.append(parent[0])
        return result

    def _isCapsuleTransform(self, node):
        if not mc.objExists(node):
            return False
        children = mc.listRelatives(node, children=True, path=True) or []
        for c in children:
            if mc.objectType(c) == "PhysicsCollisionCapsule":
                return True
        return False

    def _getCapsuleShape(self, capsule):
        children = mc.listRelatives(capsule, children=True, path=True) or []
        for c in children:
            if mc.objectType(c) == "PhysicsCollisionCapsule":
                return c
        return None

    def _uniqueName(self, base):
        """如果 base 已存在，自动加 _1 _2 ..."""
        if not mc.objExists(base):
            return base
        i = 1
        while mc.objExists("%s_%d" % (base, i)):
            i += 1
        return "%s_%d" % (base, i)

    # --------------------------------------------------------
    # 创建
    # --------------------------------------------------------

    def createCapsule(self, name="capsule", height=4.0, radius=1.0):
        capsuleOld = mel.eval('createPhysicsCollisionNode("Capsule", 0, 1)')
        capsule = mc.rename(capsuleOld, name)

        shape = self._getCapsuleShape(capsule)
        if shape:
            mc.setAttr("%s.height" % shape, height)
            mc.setAttr("%s.radius" % shape, radius)

        for attr in ("tx", "ty", "tz", "rx", "ry", "rz"):
            mc.setAttr("%s.%s" % (capsule, attr), 0)
        for attr in ("sx", "sy", "sz"):
            mc.setAttr("%s.%s" % (capsule, attr), 1)

        return capsule

    # --------------------------------------------------------
    # Mirror：复制出新 capsule，按轴镜像
    # --------------------------------------------------------

    def mirror(self, axis="x", selArray=None, debug=True):
        axis = axis.lower()
        if axis not in ("x", "y", "z"):
            mc.warning("Mirror axis must be x/y/z")
            return False

        capsules = self.getCapsules(selArray)
        if not capsules:
            mc.warning("No Capsules selected to Mirror!")
            return False

        newCapsules = []
        for c in capsules:
            newC = self._duplicateCapsule(c)
            newCapsules.append(newC)

            tAttr = "translate%s" % axis.upper()
            rAttr = "rotate%s" % axis.upper()

            mc.setAttr("%s.%s" % (newC, tAttr),
                       -mc.getAttr("%s.%s" % (c, tAttr)))
            mc.setAttr("%s.%s" % (newC, rAttr),
                       -mc.getAttr("%s.%s" % (c, rAttr)))

            shader = self._getShader(c)
            if shader:
                shaderData = self._getShaderData(shader)
                newShader, newSG = self._createShader(shader)
                mc.sets(newC, edit=True, forceElement=newSG)
                self._setShaderData(newShader, shaderData)

        if debug:
            msg = "Successfully Mirrored %d Capsules on %s axis (new capsules created)" % (
                len(newCapsules), axis.upper())
            print(msg)
            mc.warning(msg)

        mc.select(newCapsules, r=True)
        return True

    def _duplicateCapsule(self, capsule):
        newName = self._uniqueName(capsule + "_mirror")
        dup = mc.duplicate(capsule, name=newName, upstreamNodes=False,
                           inputConnections=False, renameChildren=True)
        if isinstance(dup, (list, tuple)):
            dup = dup[0]
        return dup

    # --------------------------------------------------------
    # Bake Scale
    # --------------------------------------------------------

    def bakeScaleInHeightRadius(self, selArray=None, debug=True):
        capsules = self.getCapsules(selArray)
        if not capsules:
            mc.warning("No Capsules selected to Bake!")
            return False

        for c in capsules:
            shape = self._getCapsuleShape(c)
            if not shape:
                continue

            sy = mc.getAttr("%s.sy" % c)
            mc.setAttr("%s.height" % shape, mc.getAttr("%s.height" % shape) * sy)
            mc.setAttr("%s.sy" % c, 1)

            sx = mc.getAttr("%s.sx" % c)
            mc.setAttr("%s.radius" % shape, mc.getAttr("%s.radius" % shape) * sx)
            mc.setAttr("%s.sx" % c, 1)

            mc.setAttr("%s.sz" % c, 1)

        if debug:
            msg = "Successfully Baked Scale in Height/Radius: %d" % len(capsules)
            print(msg)
            mc.warning(msg)

        return True

    # --------------------------------------------------------
    # Delete
    # --------------------------------------------------------

    def delete(self, selArray=None, debug=True):
        capsules = self.getCapsules(selArray)
        if not capsules:
            mc.warning("No Capsules selected to Delete!")
            return False

        for c in capsules:
            if mc.objExists(c):
                mc.delete(c)

        if debug:
            msg = "Deleted %d Capsules" % len(capsules)
            print(msg)
            mc.warning(msg)

        return True

    # --------------------------------------------------------
    # Save
    # --------------------------------------------------------

    def save(self, filepath=None, selArray=None, debug=True):
        capsules = self.getCapsules(selArray)
        if not capsules:
            mc.warning("No Capsules to Save!")
            return False

        if not filepath:
            filepath = mc.fileDialog2(fileMode=0, caption="Save Capsules",
                                      fileFilter="JSON Files (*.json)")
            if not filepath:
                return None
            filepath = filepath[0]

        data = {}
        if os.path.exists(filepath):
            try:
                with open(filepath, "r") as f:
                    data = json.load(f)
            except Exception:
                data = {}

        for c in capsules:
            data[c] = self._getCapsuleData(c)

        with open(filepath, "w") as f:
            json.dump(data, f, indent=4)

        if debug:
            msg = "Successfully Saved %d Capsules to %s" % (len(capsules), filepath)
            print(msg)
            mc.warning(msg)

        return True

    def _getCapsuleData(self, capsule):
        shape = self._getCapsuleShape(capsule)
        data = {
            "height": mc.getAttr("%s.height" % shape) if shape else 1.0,
            "radius": mc.getAttr("%s.radius" % shape) if shape else 1.0,
            "localMatrix": mc.xform(capsule, q=True, m=True, os=True),
        }
        shader = self._getShader(capsule)
        data["shader"] = shader
        data["shaderData"] = self._getShaderData(shader) if shader else {}
        return data

    # --------------------------------------------------------
    # Load：优先按选中过滤，每个 entry 新建 capsule，放在原点
    # --------------------------------------------------------

    def load(self, filepath=None, debug=True):
        if not filepath:
            filepath = mc.fileDialog2(fileMode=1, caption="Load Capsules",
                                      fileFilter="JSON Files (*.json)")
            if not filepath:
                return None
            filepath = filepath[0]

        with open(filepath, "r") as f:
            data = json.load(f)

        # ★ 优先看选中的 capsule
        selCapsules = self.getCapsules(mc.ls(sl=True))
        if selCapsules:
            # 只保留 JSON 里存在的选中项
            names = [n for n in selCapsules if n in data]
            if not names:
                result = mc.confirmDialog(
                    title="Load Capsules",
                    message="Selected capsules not found in data.\n\nLoad ALL capsules in file?",
                    button=["All", "Cancel"],
                    defaultButton="Cancel",
                    cancelButton="Cancel",
                    dismissString="Cancel")
                if result == "Cancel":
                    return False
                names = list(data.keys())
        else:
            # 没选中 → 问是否 load 全部
            result = mc.confirmDialog(
                title="Load Capsules",
                message="No capsule selected.\n\nLoad ALL capsules in file?",
                button=["All", "Cancel"],
                defaultButton="Cancel",
                cancelButton="Cancel",
                dismissString="Cancel")
            if result == "Cancel":
                return False
            names = list(data.keys())

        created = []
        for name in names:
            d = data[name]
            newName = self._uniqueName(name)
            capsule = self.createCapsule(
                name=newName,
                height=d.get("height", 1.0),
                radius=d.get("radius", 1.0),
            )

            shape = self._getCapsuleShape(capsule)
            if shape:
                mc.setAttr("%s.height" % shape, d.get("height", 1.0))
                mc.setAttr("%s.radius" % shape, d.get("radius", 1.0))

            for attr in ("tx", "ty", "tz", "rx", "ry", "rz"):
                mc.setAttr("%s.%s" % (capsule, attr), 0)
            for attr in ("sx", "sy", "sz"):
                mc.setAttr("%s.%s" % (capsule, attr), 1)

            shaderName = d.get("shader")
            if shaderName:
                shader, shaderSG = self._createShader(shaderName)
                mc.sets(capsule, edit=True, forceElement=shaderSG)
                self._setShaderData(shader, d.get("shaderData", {}))

            created.append(capsule)

        if debug:
            msg = "Successfully Loaded %d Capsules (new nodes created at origin)" % len(created)
            print(msg)
            mc.warning(msg)
            mc.select(created, r=True)

        return True

    # --------------------------------------------------------
    # Shader
    # --------------------------------------------------------

    def _getShader(self, node):
        shapes = mc.listRelatives(node, children=True, path=True) or [node]
        for s in shapes:
            sgs = mc.listConnections(s, type="shadingEngine") or []
            if sgs:
                shaders = mc.listConnections(sgs[0] + ".surfaceShader") or []
                if shaders:
                    return shaders[0]
        return None

    def _getShaderData(self, shader):
        data = {}
        if shader and mc.objExists(shader):
            try:
                data["color"] = mc.getAttr("%s.color" % shader)[0]
            except Exception:
                data["color"] = [0, 0, 1]
            try:
                data["collisionSharedProperties"] = mc.getAttr(
                    "%s._CollisionSharedProperties" % shader)
            except Exception:
                data["collisionSharedProperties"] = "RagdollCollisionMat"
            try:
                data["materialFX"] = mc.getAttr("%s._MaterialFX" % shader)
            except Exception:
                data["materialFX"] = "MFX_DEFAULT"
        return data

    def _createShader(self, shader="RAGDOLL_DEFAULT", color=[0, 0, 1],
                      collisionSharedProperties="RagdollCollisionMat",
                      materialFX="MFX_DEFAULT"):
        if not mc.objExists(shader):
            shader = mc.shadingNode("designSheetShader", name=shader, asShader=True)
            shaderSG = mc.sets(name="%sSG" % shader, empty=True,
                               renderable=True, noSurfaceShader=True)
            mc.connectAttr("%s.outColor" % shader, "%s.surfaceShader" % shaderSG)
            mc.setAttr("%s.color" % shader, color[0], color[1], color[2], type="double3")
            mc.setAttr("%s._CollisionSharedProperties" % shader,
                       collisionSharedProperties, type="string")
            mc.setAttr("%s._MaterialFX" % shader, materialFX, type="string")
        shaderSG = (mc.listConnections(shader, type="shadingEngine") or [None])[0]
        return shader, shaderSG

    def _setShaderData(self, shader, data):
        if not shader or not mc.objExists(shader):
            return
        if "color" in data:
            c = data["color"]
            mc.setAttr("%s.color" % shader, c[0], c[1], c[2], type="double3")
        if "collisionSharedProperties" in data:
            mc.setAttr("%s._CollisionSharedProperties" % shader,
                       data["collisionSharedProperties"], type="string")
        if "materialFX" in data:
            mc.setAttr("%s._MaterialFX" % shader,
                       data["materialFX"], type="string")


# ============================================================
# UI
# ============================================================

class CapsuleToolUI(object):

    def __init__(self, windowTitle="Capsule Tool"):
        self.window = "capsuleToolUI"
        self.windowTitle = windowTitle
        self.tool = CapsuleTool()

    def openUI(self):
        if mc.window(self.window, exists=True):
            mc.deleteUI(self.window)

        self.window = mc.window(self.window, title=self.windowTitle,
                                sizeable=True, resizeToFitChildren=True)
        mc.columnLayout(adjustableColumn=True)

        mc.text(label="")
        mc.button(label="Mirror", height=30, command=self.cmd_mirror)
        mc.button(label="Bake Scale In Height/Radius", height=30, command=self.cmd_bake)
        mc.text(label="")
        mc.button(label="Delete", height=30, command=self.cmd_delete)
        mc.text(label="")
        mc.button(label="Save", height=30, command=self.cmd_save)
        mc.button(label="Load", height=30, command=self.cmd_load)

        mc.showWindow(self.window)

    def cmd_mirror(self, *args):
        self.open_mirror_dialog()

    def cmd_bake(self, *args):
        self.tool.bakeScaleInHeightRadius(mc.ls(sl=True))

    def cmd_delete(self, *args):
        self.tool.delete(mc.ls(sl=True))

    def cmd_save(self, *args):
        self.tool.save(selArray=mc.ls(sl=True))

    def cmd_load(self, *args):
        self.tool.load()

    def open_mirror_dialog(self):
        win = "capsuleMirrorDialog"
        if mc.window(win, exists=True):
            mc.deleteUI(win)

        mc.window(win, title="Mirror Axis", sizeable=False, widthHeight=(220, 180))
        mc.columnLayout(adjustableColumn=True, rowSpacing=6)

        mc.text(label="Select Mirror Axis:")
        mc.radioCollection()
        mc.radioButton("mirrorX", label="X", sl=True)
        mc.radioButton("mirrorY", label="Y")
        mc.radioButton("mirrorZ", label="Z")

        mc.text(label="")
        mc.button(label="Mirror", height=30, command=self._do_mirror)
        mc.button(label="Cancel", height=30,
                  command=lambda *a: mc.deleteUI(win))

        mc.showWindow(win)

    def _do_mirror(self, *args):
        axis = "x"
        if mc.radioButton("mirrorY", q=True, sl=True):
            axis = "y"
        elif mc.radioButton("mirrorZ", q=True, sl=True):
            axis = "z"

        self.tool.mirror(axis=axis, selArray=mc.ls(sl=True))

        if mc.window("capsuleMirrorDialog", exists=True):
            mc.deleteUI("capsuleMirrorDialog")


# ============================================================
# 入口
# ============================================================

def openUI():
    ui = CapsuleToolUI()
    ui.openUI()
    return ui


if __name__ == "__main__":
    openUI()
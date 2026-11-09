
import maya.cmds as cmds
import maya.api.OpenMaya as om

WINDOW_NAME = "makePlanarToolWin"


# ----------------------------------------------------------------------
# Core
# ----------------------------------------------------------------------
def _get_selected_face_verts():
    """Return unique vertices (world pos + names) and faces from selection."""
    faces = cmds.filterExpand(cmds.ls(selection=True, flatten=True),
                              selectionMask=34, expand=True)
    if not faces:
        raise RuntimeError("Please select polygon faces first.")

    vtx_comp = cmds.polyListComponentConversion(faces, toVertex=True)
    vtxs = cmds.filterExpand(vtx_comp, selectionMask=31, expand=True)
    if not vtxs:
        raise RuntimeError("No vertices found in the selection.")

    vtxs = list(dict.fromkeys(vtxs))  # de-duplicate

    pts = [cmds.xform(v, query=True, worldSpace=True, translation=True)
           for v in vtxs]
    return vtxs, pts, faces


def _best_fit_plane(pts):
    """Least-squares best-fit plane. Returns (centroid, unit normal)."""
    n = len(pts)
    cx = sum(p[0] for p in pts) / n
    cy = sum(p[1] for p in pts) / n
    cz = sum(p[2] for p in pts) / n
    centroid = om.MVector(cx, cy, cz)

    xx = xy = xz = yy = yz = zz = 0.0
    for p in pts:
        dx, dy, dz = p[0] - cx, p[1] - cy, p[2] - cz
        xx += dx * dx; xy += dx * dy; xz += dx * dz
        yy += dy * dy; yz += dy * dz; zz += dz * dz

    try:
        import numpy as np
        M = np.array([[xx, xy, xz],
                      [xy, yy, yz],
                      [xz, yz, zz]], dtype=float)
        w, v = np.linalg.eigh(M)
        normal = om.MVector(v[0, 0], v[1, 0], v[2, 0])
    except ImportError:
        normal = _inverse_power_iteration(xx, xy, xz, yy, yz, zz)

    normal.normalize()
    return centroid, normal


def _inverse_power_iteration(xx, xy, xz, yy, yz, zz):
    """Fallback without numpy: inverse power iteration for smallest eigenvector."""
    sigma = min(xx, yy, zz) * 0.999
    a00, a11, a22 = xx - sigma, yy - sigma, zz - sigma
    v = om.MVector(1.0, 1.0, 1.0)
    for _ in range(20):
        b = v
        det = (a00 * (a11 * a22 - yz * yz)
               - xy * (xy * a22 - yz * xz)
               + xz * (xy * yz - a11 * xz))
        if abs(det) < 1e-15:
            break
        inv = 1.0 / det
        x = inv * ((a11 * a22 - yz * yz) * b.x
                   - (xy * a22 - yz * xz) * b.y
                   + (xy * yz - a11 * xz) * b.z)
        y = inv * (-(xy * a22 - yz * xz) * b.x
                   + (a00 * a22 - xz * xz) * b.y
                   - (a00 * yz - xy * xz) * b.z)
        z = inv * ((xy * yz - a11 * xz) * b.x
                   - (a00 * yz - xy * xz) * b.y
                   + (a00 * a11 - xy * xy) * b.z)
        v = om.MVector(x, y, z)
        if v.length() < 1e-15:
            break
        v.normalize()
    return v


def _avg_face_normal(vtxs):
    """Average face normal in world space. Select verts first to avoid warnings."""
    cmds.select(vtxs, replace=True)
    nx = cmds.polyNormalPerVertex(query=True, x=True)
    ny = cmds.polyNormalPerVertex(query=True, y=True)
    nz = cmds.polyNormalPerVertex(query=True, z=True)
    n = len(nx)
    if n == 0:
        return om.MVector(0, 1, 0)
    v = om.MVector(sum(nx) / n, sum(ny) / n, sum(nz) / n)
    v.normalize()
    return v


def make_planar(mode=1, axis="y"):
    """
    mode 1: best-fit plane (recommended)
    mode 2: average face normal direction, centroid anchor
    mode 3: flatten along world axis, axis='x'/'y'/'z'
    """
    vtxs, pts, faces = _get_selected_face_verts()

    n = len(pts)
    centroid = om.MVector(sum(p[0] for p in pts) / n,
                          sum(p[1] for p in pts) / n,
                          sum(p[2] for p in pts) / n)

    if mode == 3:
        axis = axis.lower()
        normal = {"x": om.MVector(1, 0, 0),
                  "y": om.MVector(0, 1, 0),
                  "z": om.MVector(0, 0, 1)}[axis]
    elif mode == 2:
        normal = _avg_face_normal(vtxs)
    else:
        centroid, normal = _best_fit_plane(pts)

    if normal.length() < 1e-9:
        cmds.select(faces, replace=True)
        raise RuntimeError("Cannot determine a valid plane normal (degenerate selection).")

    normal.normalize()

    cmds.undoInfo(openChunk=True)
    try:
        for v, p in zip(vtxs, pts):
            rel = om.MVector(p[0] - centroid.x,
                             p[1] - centroid.y,
                             p[2] - centroid.z)
            d = normal * rel
            move = normal * (-d)
            cmds.xform(v, worldSpace=True, relative=True,
                       translation=[move.x, move.y, move.z])
    finally:
        cmds.undoInfo(closeChunk=True)

    cmds.selectMode(object=True)
    cmds.select(faces, replace=True)


# ----------------------------------------------------------------------
# UI
# ----------------------------------------------------------------------
def _run(mode, axis="y"):
    try:
        make_planar(mode, axis)
    except Exception as e:
        cmds.warning(str(e))


def _on_mode1(*args):
    _run(1)


def _on_mode2(*args):
    _run(2)


def _on_mode3(*args):
    axis = cmds.radioButtonGrp("mp_axisGrp", query=True, select=True)
    axis = {1: "x", 2: "y", 3: "z"}.get(axis, "y")
    _run(3, axis)


def show_ui():
    if cmds.window(WINDOW_NAME, exists=True):
        cmds.deleteUI(WINDOW_NAME)
    cmds.window(WINDOW_NAME, title="Make Planar Tool", widthHeight=(300, 220))

    cmds.columnLayout(adjustableColumn=True, rowSpacing=8, columnOffset=("both", 10))

    cmds.frameLayout(label="Planarize Mode", collapsable=False,
                     marginHeight=6, marginWidth=6)
    cmds.columnLayout(adjustableColumn=True, rowSpacing=6)

    cmds.button(label="1. Best-Fit Plane (Recommended)", height=32,
                command=_on_mode1,
                annotation="Least-squares fit over all selected vertices, then project along the fitted normal.")

    cmds.button(label="2. Average Face Normal", height=32,
                command=_on_mode2,
                annotation="Use the average face normal as flatten direction, anchored at the centroid.")

    cmds.button(label="3. Flatten Along World Axis", height=32,
                command=_on_mode3,
                annotation="Flatten along the selected world axis.")

    cmds.radioButtonGrp("mp_axisGrp", label="Axis:", numberOfRadioButtons=3,
                        labelArray3=["X", "Y", "Z"], select=2,
                        columnWidth3=(50, 50, 50),
                        columnAlign3=("left", "left", "left"))

    cmds.setParent("..")
    cmds.setParent("..")

    cmds.separator(height=6, style="in")

    cmds.text(label="Usage: select polygon faces, then click a button above.",
              align="left", font="smallObliqueLabelFont")

    cmds.setParent("..")
    cmds.showWindow(WINDOW_NAME)


# Auto-show when executed directly
if __name__ == "__main__":
    show_ui()
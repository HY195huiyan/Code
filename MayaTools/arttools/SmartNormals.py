# -*- coding: utf-8 -*-
"""
SmartNormals.py
Two vertex-normal write modes:
  1. Smooth  - area-weighted average (corner-area proxy = product of two edge lengths)
  2. Snap    - snap to the largest adjacent face (average if equal area)
Supports hard-edge detection (break blending by angle).
"""

import math
import re
from collections import defaultdict

import maya.cmds as cmds
import maya.api.OpenMaya as om2

WINDOW_NAME = "smartNormalsWin"
PROGRESS_NAME = "smartNormalsProgressBar"


# ---------------------------------------------------------------------------
# Geometry helpers
# ---------------------------------------------------------------------------
def _get_mesh_fn_from_dag(dag_path):
    """Create (MFnMesh, MDagPath) from a transform or shape path."""
    shapes = cmds.listRelatives(dag_path, shapes=True, type="mesh", fullPath=True)
    if shapes:
        target = shapes[0]
    elif cmds.objectType(dag_path) == "mesh":
        target = dag_path
    else:
        raise RuntimeError("No mesh shape found for %s" % dag_path)

    sel = om2.MSelectionList()
    sel.add(target)
    dag = sel.getDagPath(0)
    return om2.MFnMesh(dag), dag


def _face_normal(fn, face_id):
    """Face normal (world space, unit vector)."""
    return fn.getPolygonNormal(face_id, om2.MSpace.kWorld)


def _angle_between(n1, n2):
    """Angle between two unit vectors (radians)."""
    d = max(-1.0, min(1.0, n1 * n2))
    return math.acos(d)


def _corner_area_proxy(fn, face_id, vertex_id, pts):
    """Corner-area proxy at this vertex in this face: product of the two incident edge lengths."""
    loop = list(fn.getPolygonVertices(face_id))
    n = len(loop)
    try:
        idx = loop.index(vertex_id)
    except ValueError:
        return 0.0

    prev_v = loop[(idx - 1) % n]
    next_v = loop[(idx + 1) % n]
    p_v = pts[vertex_id]
    p_prev = pts[prev_v]
    p_next = pts[next_v]

    v_prev = om2.MVector(p_prev.x - p_v.x, p_prev.y - p_v.y, p_prev.z - p_v.z)
    v_next = om2.MVector(p_next.x - p_v.x, p_next.y - p_v.y, p_next.z - p_v.z)
    return v_prev.length() * v_next.length()


# ---------------------------------------------------------------------------
# Core algorithm
# ---------------------------------------------------------------------------
def _compute_vertex_normal(fn, vertex_id, snap_mode, hard_edges, hard_angle_deg, pts, vertex_faces):
    """Return the normal to write for this vertex (om2.MVector, normalized)."""
    faces = vertex_faces.get(vertex_id, [])
    if not faces:
        return om2.MVector(0, 1, 0)

    final = om2.MVector(0, 0, 0)
    biggest = -1.0
    best_normal = None
    hard_rad = math.radians(hard_angle_deg)

    for fid in faces:
        n = _face_normal(fn, fid)

        is_hard = False
        if hard_edges and best_normal is not None:
            if _angle_between(n, best_normal) > hard_rad:
                is_hard = True

        area = _corner_area_proxy(fn, fid, vertex_id, pts)

        if snap_mode:
            if area > biggest:
                biggest = area
                best_normal = n
                final = om2.MVector(n)
            elif abs(area - biggest) < 1e-9 and best_normal is not None:
                final += n
        else:
            if is_hard:
                continue
            final += n * area
            if best_normal is None:
                best_normal = n

    length = final.length()
    if length < 1e-9:
        return om2.MVector(0, 1, 0)
    return final / length


# ---------------------------------------------------------------------------
# Main processing
# ---------------------------------------------------------------------------
def _split_vertex(vertex_name):
    """Split 'pCube1.vtx[12]' into ('pCube1', 12)."""
    m = re.match(r"^(.+)\.vtx\[(\d+)\]$", vertex_name)
    if not m:
        return None, None
    return m.group(1), int(m.group(2))


def _set_progress(value, max_value, visible=True, status=""):
    """Update the in-window progress bar (ignored if the control does not exist)."""
    if not cmds.progressBar(PROGRESS_NAME, exists=True):
        return
    cmds.progressBar(PROGRESS_NAME, edit=True,
                     visible=visible,
                     maxValue=max_value,
                     progress=value)
    if status:
        cmds.progressBar(PROGRESS_NAME, edit=True, status=status)
    cmds.refresh()


def _hide_progress_later():
    """Hide the progress bar after a short delay."""
    if cmds.progressBar(PROGRESS_NAME, exists=True):
        cmds.progressBar(PROGRESS_NAME, edit=True, visible=False)


def _apply_to_selection(snap_mode, hard_edges, show_bar, hard_angle=60.0):
    sel = cmds.ls(sl=True)
    if not sel:
        cmds.warning("Please select vertices of a polygon mesh first.")
        return

    verts = cmds.filterExpand(sel, ex=True, sm=31) or []
    if not verts:
        cmds.polySelectConvert(3)
        verts = cmds.filterExpand(ex=True, sm=31) or []

    verts = cmds.ls(verts, flatten=True) or []

    if not verts:
        cmds.warning("No vertices to process.")
        return

    total = len(verts)
    estimate = total * 0.01
    if estimate > 10:
        cont = cmds.confirmDialog(
            title="Confirm",
            message="This will process %d vertices (approx. %.0f seconds).\nContinue?"
                    % (total, estimate),
            button=["Yes", "No"], defaultButton="Yes",
            cancelButton="No", dismissString="No")
        if cont != "Yes":
            return

    groups = defaultdict(list)
    for v in verts:
        node, idx = _split_vertex(v)
        if node is not None:
            groups[node].append(idx)

    if not groups:
        cmds.warning("Unable to parse vertex names.")
        return

    undo_state = cmds.undoInfo(q=True, state=True)
    cmds.undoInfo(stateWithoutFlush=False)

    try:
        if show_bar:
            _set_progress(0, total, visible=True,
                          status="Processing normals... 0/%d" % total)

        done = 0
        cancelled = False
        for node, vids in groups.items():
            fn, dag = _get_mesh_fn_from_dag(node)
            pts = fn.getPoints(om2.MSpace.kWorld)

            vertex_faces = {}
            it = om2.MItMeshVertex(dag)
            while not it.isDone():
                vertex_faces[it.index()] = list(it.getConnectedFaces())
                it.next()

            for vid in vids:
                if show_bar and cmds.progressBar(PROGRESS_NAME, exists=True):
                    if cmds.progressBar(PROGRESS_NAME, q=True, isCancelled=True):
                        cancelled = True
                        break

                normal = _compute_vertex_normal(
                    fn, vid, snap_mode, hard_edges, hard_angle, pts, vertex_faces)

                vertex_name = "%s.vtx[%d]" % (node, vid)
                cmds.polyNormalPerVertex(vertex_name,
                                         xyz=(normal.x, normal.y, normal.z))

                done += 1
                if show_bar:
                    _set_progress(done, total,
                                  status="Processing normals... %d/%d" % (done, total))

            if cancelled:
                break

        if show_bar:
            _set_progress(total, total, status="Done")
            cmds.refresh()
            cmds.evalDeferred(_hide_progress_later)

    finally:
        cmds.undoInfo(stateWithoutFlush=undo_state)

    cmds.select(sel, r=True)


# ---------------------------------------------------------------------------
# UI
# ---------------------------------------------------------------------------
def _on_apply(*args):
    try:
        snap_mode = cmds.radioButton("rbSnap", q=True, select=True)
    except RuntimeError:
        snap_mode = False
    try:
        hard_edges = cmds.checkBox("cbHardEdges", q=True, value=True)
    except RuntimeError:
        hard_edges = True
    try:
        hard_angle = cmds.floatFieldGrp("ffHardAngle", q=True, value1=True)
    except RuntimeError:
        hard_angle = 60.0
    try:
        show_bar = cmds.checkBox("cbProgress", q=True, value=True)
    except RuntimeError:
        show_bar = True

    _apply_to_selection(snap_mode, hard_edges, show_bar, hard_angle)


def _on_mode_changed(*args):
    if not cmds.radioButton("rbSnap", exists=True):
        return
    if not cmds.checkBox("cbHardEdges", exists=True):
        return
    snap_mode = cmds.radioButton("rbSnap", q=True, select=True)
    enable = not snap_mode
    cmds.checkBox("cbHardEdges", edit=True, enable=enable)
    cmds.floatFieldGrp("ffHardAngle", edit=True, enable=enable)


def smartNormalsUI():
    if cmds.window(WINDOW_NAME, exists=True):
        cmds.deleteUI(WINDOW_NAME)

    cmds.window(WINDOW_NAME, title="Smart Normals", widthHeight=(360, 290))
    cmds.columnLayout(adjustableColumn=True, rowSpacing=8,
                      columnOffset=("both", 12))

    cmds.text(label="Normal Mode:", align="left")
    cmds.radioCollection("normalModeCol")
    cmds.radioButton("rbSmooth", label="Smooth (Area-Weighted Average)",
                     onCommand=_on_mode_changed)
    cmds.radioButton("rbSnap", label="Snap (Largest Adjacent Face)",
                     onCommand=_on_mode_changed)
    cmds.radioCollection("normalModeCol", edit=True, select="rbSmooth")

    cmds.separator(height=8, style="in")
    cmds.checkBox("cbHardEdges", label="Respect Hard Edges (break blending by angle)",
                  value=True)
    cmds.floatFieldGrp("ffHardAngle", numberOfFields=1, label="Hard Edge Angle",
                       value1=60.0, precision=1)
    cmds.checkBox("cbProgress", label="Show Progress Bar", value=True)

    cmds.separator(height=8, style="in")
    cmds.button(label="Apply to Selected Vertices", height=32, command=_on_apply)

    # Progress bar control (created up front so it can be edited later)
    cmds.progressBar(PROGRESS_NAME, height=20, visible=False, status="")

    cmds.showWindow(WINDOW_NAME)
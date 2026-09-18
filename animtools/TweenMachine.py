
import maya.cmds as cmds

WINDOW_NAME = "tweenMachineWin"

# Preset bias values shown as buttons (in percent)
BUTTON_VALUES = [-75, -60, -33, 0, 33, 60, 75]

# Current overshoot state
_overshoot = False


# ---------------------------------------------------------------------------
# Core tween logic
# ---------------------------------------------------------------------------

def _get_nodes():
    """Return the list of selected nodes."""
    return cmds.ls(selection=True, long=False) or []


def _get_selected_attrs():
    """Return the attributes currently selected in the Channel Box, as long names."""
    short_names = cmds.channelBox("mainChannelBox", q=True, selectedMainAttributes=True) or []
    mapping = {
        "tx": "translateX", "ty": "translateY", "tz": "translateZ",
        "rx": "rotateX",    "ry": "rotateY",    "rz": "rotateZ",
        "sx": "scaleX",     "sy": "scaleY",     "sz": "scaleZ",
        "v":  "visibility",
    }
    return [mapping.get(a, a) for a in short_names]


def tween(bias_percent):
    """
    Create a tween key on the current frame.

    bias_percent: -150..150 (0 = previous frame value, 100 = next frame value,
                  50 = exactly halfway between the two keys)
    """
    nodes = _get_nodes()
    if not nodes:
        cmds.warning("tweenMachine: nothing selected.")
        return

    attrs = _get_selected_attrs()
    current_time = cmds.currentTime(query=True)

    curves = cmds.keyframe(nodes, query=True, name=True) or []
    if not curves:
        cmds.warning("tweenMachine: no keyframed curves on selection.")
        return

    if attrs:
        curves = [c for c in curves if any(c.endswith(a) for a in attrs)]
        if not curves:
            cmds.warning("tweenMachine: no matching curves for selected attributes.")
            return

    bias = bias_percent / 100.0

    for curve in curves:
        prev_time = cmds.findKeyframe(curve, which="previous", time=(current_time, current_time))
        next_time = cmds.findKeyframe(curve, which="next", time=(current_time, current_time))

        if prev_time is None or next_time is None:
            continue
        if prev_time == current_time or next_time == current_time:
            continue

        prev_val = cmds.keyframe(curve, query=True, time=(prev_time, prev_time), valueChange=True)
        next_val = cmds.keyframe(curve, query=True, time=(next_time, next_time), valueChange=True)

        if not prev_val or not next_val:
            continue

        prev_val = prev_val[0]
        next_val = next_val[0]

        new_val = prev_val + (next_val - prev_val) * bias

        cmds.setKeyframe(curve, time=current_time, value=new_val, outTangentType="spline")
        cmds.keyTangent(curve, time=(current_time, current_time), inTangentType="spline")

    cmds.currentTime(current_time)


# ---------------------------------------------------------------------------
# UI callbacks
# ---------------------------------------------------------------------------

def _on_slider_change(value):
    tween(value)


def _on_button(value):
    tween(value)


def _toggle_overshoot(state):
    global _overshoot
    _overshoot = state
    lo, hi = (-150.0, 150.0) if _overshoot else (-100.0, 100.0)
    cmds.floatSliderGrp("tmBiasSlider", edit=True, minValue=lo, maxValue=hi)


# ---------------------------------------------------------------------------
# UI
# ---------------------------------------------------------------------------

def start():
    """Build and show the tweenMachine window."""
    if cmds.window(WINDOW_NAME, exists=True):
        cmds.deleteUI(WINDOW_NAME)

    cmds.window(WINDOW_NAME, title="tweenMachine", widthHeight=(360, 140), sizeable=True)

    # Top-level form: slider on top, button row in the middle, checkbox at bottom
    form = cmds.formLayout("tmMainForm", numberOfDivisions=100)

    slider = cmds.floatSliderGrp(
        "tmBiasSlider",
        label="Bias",
        field=True,
        minValue=-100.0,
        maxValue=100.0,
        value=0.0,
        columnWidth3=(40, 60, 180),
        adjustableColumn=2,
        changeCommand=_on_slider_change,
    )

    # Button row: each button gets its own form layout cell so they can be
    # sized equally and stretched with the window.
    btn_row = cmds.formLayout("tmButtonRow", numberOfDivisions=100)

    btn_names = []
    for i, v in enumerate(BUTTON_VALUES):
        name = "tmBtn{}".format(i)
        cmds.button(name, label=str(v), command=lambda *args, val=v: _on_button(val))
        btn_names.append(name)

    # Attach buttons left-to-right, each taking an equal share of width.
    n = len(btn_names)
    for i, name in enumerate(btn_names):
        # Vertical: pin top and bottom to the row form
        cmds.formLayout(btn_row, edit=True,
                        attachForm=[(name, "top", 0), (name, "bottom", 0)])

        # Horizontal: first button pinned left, last button pinned right,
        # each middle button attached to its left neighbor.
        if i == 0:
            cmds.formLayout(btn_row, edit=True, attachForm=[(name, "left", 0)])
        else:
            cmds.formLayout(btn_row, edit=True,
                            attachControl=[(name, "left", 0, btn_names[i - 1])])
        if i == n - 1:
            cmds.formLayout(btn_row, edit=True, attachForm=[(name, "right", 0)])

    # Give every non-last button an equal width using attachPosition.
    # Split the row into n equal columns.
    for i, name in enumerate(btn_names):
        left_pct = (i / n) * 100.0
        right_pct = ((i + 1) / n) * 100.0
        cmds.formLayout(btn_row, edit=True,
                        attachPosition=[(name, "left", 0, left_pct),
                                        (name, "right", 0, right_pct)])

    cmds.setParent("..")  # back to main form

    chk = cmds.checkBox(label="Overshoot (-150 / 150)", value=False, changeCommand=_toggle_overshoot)

    # Arrange the three sections in the main form
    cmds.formLayout(
        form, edit=True,
        attachForm=[
            (slider, "top", 8),
            (slider, "left", 8),
            (slider, "right", 8),

            (btn_row, "left", 8),
            (btn_row, "right", 8),

            (chk, "left", 8),
            (chk, "bottom", 8),
        ],
        attachControl=[
            (btn_row, "top", 8, slider),
            (chk, "top", 8, btn_row),
        ],
    )

    cmds.showWindow(WINDOW_NAME)


# Auto-launch when run directly from the Script Editor
if __name__ == "__main__":
    start()

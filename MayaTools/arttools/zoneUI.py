"UI for creating FX zones with multiple shapes."

import os
import sys

from maya import cmds
from maya import OpenMayaUI as omui

# --- Qt / shiboken compatibility (Maya 2020-2024 vs 2025+) -----------------
try:
    from PySide2 import QtWidgets, QtCore
    from shiboken2 import wrapInstance
except ImportError:
    from PySide6 import QtWidgets, QtCore
    from shiboken6 import wrapInstance

# --- import zone module (works as package, or when run standalone) ---------
try:
    from . import zone
except ImportError:
    _here = os.path.dirname(os.path.abspath(__file__)) if '__file__' in globals() else ''
    if _here and _here not in sys.path:
        sys.path.insert(0, _here)
    import zone  # noqa: F401


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
SHAPE_TYPES = [
    ('PhysicsCollisionBox', 'Box'),
    ('PhysicsCollisionSphere', 'Sphere'),
    ('PhysicsCollisionCapsule', 'Capsule'),
]

DISPLAY_LAYERS = list(getattr(zone, 'DISPLAY_LAYER_COLORS', {}).keys()) or [
    'EntityZones', 'SoundZones', 'CameraZones', 'FXVolumes', 'TriggerVolumes',
]


def _maya_main_window():
    ptr = omui.MQtUtil.mainWindow()
    if ptr is None:
        return None
    return wrapInstance(int(ptr), QtWidgets.QWidget)


# ---------------------------------------------------------------------------
# Shape-specific sizing helpers for "Around Selection"
# ---------------------------------------------------------------------------
def _apply_shape_to_bbox(shape, shape_type, center, size):
    """Set shape attributes so the primitive wraps the given bbox.

    center: [x, y, z]
    size:   [width, height, depth]
    """
    if shape_type in (None, 'PhysicsCollisionBox'):
        if cmds.attributeQuery('sizeX', node=shape, exists=True):
            cmds.setAttr(shape + '.sizeX', size[0])
            cmds.setAttr(shape + '.sizeY', size[1])
            cmds.setAttr(shape + '.sizeZ', size[2])
    elif shape_type == 'PhysicsCollisionSphere':
        radius = max(size) / 2.0
        if cmds.attributeQuery('radius', node=shape, exists=True):
            cmds.setAttr(shape + '.radius', radius)
    elif shape_type == 'PhysicsCollisionCapsule':
        radius = max(size[0], size[2]) / 2.0
        height = size[1]
        if cmds.attributeQuery('radius', node=shape, exists=True):
            cmds.setAttr(shape + '.radius', radius)
        if cmds.attributeQuery('height', node=shape, exists=True):
            cmds.setAttr(shape + '.height', height)
    else:
        for attr, val in (('sizeX', size[0]), ('sizeY', size[1]), ('sizeZ', size[2])):
            if cmds.attributeQuery(attr, node=shape, exists=True):
                cmds.setAttr(shape + '.' + attr, val)


class ZoneCreatorUI(QtWidgets.QDialog):

    WINDOW_OBJECT_NAME = 'ZoneCreatorUI'

    def __init__(self, parent=None):
        super(ZoneCreatorUI, self).__init__(parent or _maya_main_window())
        self.setObjectName(self.WINDOW_OBJECT_NAME)
        self.setWindowTitle('FX Zone Creator')
        self.setMinimumWidth(440)

        self._entries = []

        self._build_ui()
        self._refresh_list()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------
    def _build_ui(self):
        main_layout = QtWidgets.QVBoxLayout(self)

        form = QtWidgets.QFormLayout()

        self.name_prefix_edit = QtWidgets.QLineEdit('FX')
        form.addRow('Name Prefix:', self.name_prefix_edit)

        self.layer_combo = QtWidgets.QComboBox()
        self.layer_combo.addItems(DISPLAY_LAYERS)
        idx = self.layer_combo.findText('FXVolumes')
        if idx >= 0:
            self.layer_combo.setCurrentIndex(idx)
        form.addRow('Display Layer:', self.layer_combo)

        self.shape_combo = QtWidgets.QComboBox()
        for type_name, label in SHAPE_TYPES:
            self.shape_combo.addItem(label, type_name)
        form.addRow('Shape Type:', self.shape_combo)

        main_layout.addLayout(form)

        add_row = QtWidgets.QHBoxLayout()
        self.add_button = QtWidgets.QPushButton('Add Shape')
        self.add_button.clicked.connect(self._on_add_shape)
        add_row.addWidget(self.add_button)

        self.add_around_selection_button = QtWidgets.QPushButton('Add Around Selection')
        self.add_around_selection_button.clicked.connect(self._on_add_around_selection)
        add_row.addWidget(self.add_around_selection_button)
        main_layout.addLayout(add_row)

        self.list_widget = QtWidgets.QListWidget()
        self.list_widget.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        main_layout.addWidget(self.list_widget)

        list_btn_row = QtWidgets.QHBoxLayout()
        self.select_in_scene_btn = QtWidgets.QPushButton('Select in Scene')
        self.select_in_scene_btn.clicked.connect(self._on_select_in_scene)
        list_btn_row.addWidget(self.select_in_scene_btn)

        self.delete_entry_btn = QtWidgets.QPushButton('Remove')
        self.delete_entry_btn.clicked.connect(self._on_remove_entries)
        list_btn_row.addWidget(self.delete_entry_btn)

        self.clear_btn = QtWidgets.QPushButton('Clear')
        self.clear_btn.clicked.connect(self._on_clear)
        list_btn_row.addWidget(self.clear_btn)
        main_layout.addLayout(list_btn_row)

        # --- bottom actions: Create / Close each 50% width ---
        bottom_row = QtWidgets.QHBoxLayout()
        bottom_row.setSpacing(6)

        self.create_btn = QtWidgets.QPushButton('Create')
        self.create_btn.setDefault(True)
        self.create_btn.setSizePolicy(
            QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed
        )
        self.create_btn.clicked.connect(self._on_create)
        bottom_row.addWidget(self.create_btn, 1)  # stretch=1

        self.cancel_btn = QtWidgets.QPushButton('Close')
        self.cancel_btn.setSizePolicy(
            QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed
        )
        self.cancel_btn.clicked.connect(self.close)
        bottom_row.addWidget(self.cancel_btn, 1)  # stretch=1

        main_layout.addLayout(bottom_row)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _current_layer(self):
        text = self.layer_combo.currentText().strip()
        return text or None

    def _current_shape_type(self):
        return self.shape_combo.currentData()

    def _next_auto_name(self):
        prefix = self.name_prefix_edit.text().strip() or 'FX'
        index = len(self._entries) + 1
        return '{}_{}'.format(prefix, index)

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------
    def _on_add_shape(self):
        name = self._next_auto_name()
        shape_type = self._current_shape_type()
        layer = self._current_layer()

        try:
            transform, shape = zone.create_zone(
                name,
                collision_primitive=shape_type,
                display_layer=layer,
            )
        except Exception as exc:
            cmds.warning('Failed to create zone "{}": {}'.format(name, exc))
            return

        self._entries.append({
            'name': name,
            'transform': transform,
            'shape': shape,
            'shape_type': shape_type,
            'layer': layer,
        })
        self._refresh_list()

    def _on_add_around_selection(self):
        name = self._next_auto_name()
        layer = self._current_layer()
        shape_type = self._current_shape_type()

        try:
            center, size = zone.selection_center_and_size()
        except Exception as exc:
            cmds.warning('Failed to compute selection bbox: {}'.format(exc))
            return

        try:
            transform, shape = zone.create_zone(
                name,
                collision_primitive=shape_type,
                display_layer=layer,
            )
        except Exception as exc:
            cmds.warning('Failed to create zone "{}": {}'.format(name, exc))
            return

        cmds.move(center[0], center[1], center[2], transform,
                  absolute=True, worldSpace=True)

        _apply_shape_to_bbox(shape, shape_type, center, size)

        self._entries.append({
            'name': name,
            'transform': transform,
            'shape': shape,
            'shape_type': shape_type,
            'layer': layer,
        })
        self._refresh_list()

    def _on_select_in_scene(self):
        items = self.list_widget.selectedItems()
        if not items:
            return
        transforms = [it.data(QtCore.Qt.UserRole) for it in items]
        transforms = [t for t in transforms if t and cmds.objExists(t)]
        if transforms:
            cmds.select(transforms, replace=True)

    def _on_remove_entries(self):
        items = self.list_widget.selectedItems()
        if not items:
            return
        transforms_to_remove = set(it.data(QtCore.Qt.UserRole) for it in items)

        existing = [t for t in transforms_to_remove if cmds.objExists(t)]
        if existing:
            answer = cmds.confirmDialog(
                title='Remove',
                message='Delete {} zone(s) from the scene?'.format(len(existing)),
                button=['Delete', 'Cancel'],
                defaultButton='Delete',
                cancelButton='Cancel',
                dismissString='Cancel',
            )
            if answer != 'Delete':
                return
            cmds.delete(existing)

        self._entries = [
            e for e in self._entries if e['transform'] not in transforms_to_remove
        ]
        self._refresh_list()

    def _on_clear(self):
        if not self._entries:
            return

        existing = [e['transform'] for e in self._entries if cmds.objExists(e['transform'])]
        if existing:
            answer = cmds.confirmDialog(
                title='Clear',
                message='Delete all {} zone(s) from the scene?'.format(len(existing)),
                button=['Delete', 'Cancel'],
                defaultButton='Delete',
                cancelButton='Cancel',
                dismissString='Cancel',
            )
            if answer != 'Delete':
                return
            cmds.delete(existing)

        self._entries = []
        self._refresh_list()

    def _on_create(self):
        transforms = [e['transform'] for e in self._entries if cmds.objExists(e['transform'])]
        if transforms:
            cmds.select(transforms, replace=True)
        self.close()

    # ------------------------------------------------------------------
    # List refresh
    # ------------------------------------------------------------------
    def _refresh_list(self):
        self.list_widget.clear()
        for entry in self._entries:
            label = '{}  [{}]'.format(entry['name'], entry['shape_type'] or 'polyCube')
            item = QtWidgets.QListWidgetItem(label)
            item.setData(QtCore.Qt.UserRole, entry['transform'])
            if not cmds.objExists(entry['transform']):
                item.setForeground(QtCore.Qt.red)
            self.list_widget.addItem(item)


# ---------------------------------------------------------------------------
# Public entry points
# ---------------------------------------------------------------------------
def show():
    if cmds.window(ZoneCreatorUI.WINDOW_OBJECT_NAME, exists=True):
        cmds.deleteUI(ZoneCreatorUI.WINDOW_OBJECT_NAME)

    dlg = ZoneCreatorUI()
    dlg.show()
    return dlg


def prompt_create_zone_multi(name_prefix='FX'):
    dlg = show()
    dlg.name_prefix_edit.setText(name_prefix)
    return dlg
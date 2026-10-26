import maya.cmds as cmds
from maya import OpenMayaUI as omui

try:
    from PySide2.QtWidgets import QWidget, QVBoxLayout, QPushButton, QLabel, QFrame
    from PySide2.QtCore import Qt
    from shiboken2 import wrapInstance
except ImportError:
    from PySide6.QtWidgets import QWidget, QVBoxLayout, QPushButton, QLabel, QFrame
    from PySide6.QtCore import Qt
    from shiboken6 import wrapInstance

def get_maya_main_window():
    main_window_ptr = omui.MQtUtil.mainWindow()
    return wrapInstance(int(main_window_ptr), QWidget)

class AttributeTaggerUI(QWidget):
    def __init__(self, parent=get_maya_main_window()):
        super(AttributeTaggerUI, self).__init__(parent)
        
        self.setWindowTitle("Attribute Tagger")
        self.setMinimumWidth(300)
        self.setWindowFlags(Qt.Window)
        
        self.build_ui()

    def build_ui(self):
        layout = QVBoxLayout(self)
        
        # Instruction label
        info_label = QLabel("Select objects, then click a button to add a tag:")
        info_label.setStyleSheet("font-weight: bold; margin-bottom: 5px;")
        layout.addWidget(info_label)

        # 1. String Button (Game Object Tag)
        btn_string = QPushButton("Add game object tag")
        btn_string.setStyleSheet("background-color: #5c5c5c; color: white; padding: 5px;")
        btn_string.clicked.connect(lambda: self.addingFlags("gameObjectTag", "string", ""))
        layout.addWidget(btn_string)

        # Separator line
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        layout.addWidget(line)

        # 2-9. Boolean Buttons
        # Note: Maya attribute names cannot contain spaces, camelCase is used internally
        self.bool_attrs = [
            ("anim group", "animGroup"),
            ("auto animate", "autoAnimate"),
            ("is animated", "isAnimated"),
            ("keep joint", "keepJoint"),
            ("new game object", "newGameObject"),
            ("platform", "platform"),
            ("use UI camera", "useUICamera"),
            ("force high mips loaded", "forceHighMipsLoaded")
        ]

        for display_name, attr_name in self.bool_attrs:
            btn = QPushButton(f"Add {display_name}")
            btn.setStyleSheet("background-color: #4a6c8c; color: white; padding: 5px;")
            # Pass attribute name, type (bool), and default value (1 means True)
            btn.clicked.connect(lambda checked=False, n=attr_name: self.addingFlags(n, "bool", 1))
            layout.addWidget(btn)

    # ==========================================
    # Core logic based on the provided MEL code
    # ==========================================

    def addingFlags(self, name, attr_type, value):
        select_list = cmds.ls(selection=True, long=True)
        if len(select_list) == 0:
            cmds.warning("Please select at least one object first!")
            return

        print("--------------------------------------------------------")
        print("Adding " + name + " attribute to selected game objects")
        
        go_list = self.addingFlagsRun(name, attr_type, value)

        for go in go_list:
            print("  Added " + name + " attribute to: " + go)
            
        print("--------------------------------------------------------")

    def addingFlagsRun(self, name, attr_type, value):
        go_list = []
        select_list = cmds.ls(selection=True, long=True)
        if len(select_list) == 0:
            return go_list

        for go in select_list:
            # Skip nodes that already have the attribute
            if cmds.attributeQuery(name, node=go, exists=True):
                continue

            # Add attribute and make it keyable (-k true)
            if attr_type == "string":
                cmds.addAttr(go, longName=name, dataType="string", keyable=True)
                # Set value if one is provided, otherwise leave default (empty)
                if value != "":
                    cmds.setAttr(f"{go}.{name}", value, type="string")
            else:
                cmds.addAttr(go, longName=name, attributeType="bool", keyable=True, defaultValue=bool(value))
                
            go_list.append(go)
            
        return go_list


def run():
    """
    Launch the Attribute Tagger UI.
    This function can be called from other scripts or Maya Script Editor.
    """
    # Close existing window if it's already open
    global tagger_ui
    if 'tagger_ui' in globals() and tagger_ui is not None:
        try:
            tagger_ui.close()
            tagger_ui.deleteLater()
        except:
            pass
            
    # Create and show the new window
    tagger_ui = AttributeTaggerUI()
    tagger_ui.show()
    return tagger_ui


# Automatically run when the script is executed in the Script Editor
if __name__ == "__main__":
    run()
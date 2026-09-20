

from maya import cmds
import character_definitions as cd

class RibbonIkFkMatch():

    def __init__(self, key, snap, playbackRange):

        self.key = key
        self.snap = snap
        self.playback = playbackRange

        self.selection = None
        self.data_parent = None
        self.switch_control = None
        self.fk_controls = None
        self.ik_controls = None

    def run(self):

        cmds.undoInfo(openChunk=True)

        self.selection = self.get_selection()

        if self.selection:
            self.data_parent = self.get_data_parent(self.selection)

        if self.data_parent:
            self.switch_control = self.get_switch_control(self.data_parent)
            self.fk_controls = self.get_fk_controls(self.data_parent)

            self.ik_controls = self.get_ik_controls(self.data_parent)

        if self.playback:

            start_frame = cmds.playbackOptions(q=True, minTime=True)
            end_frame = cmds.playbackOptions(q=True, maxTime=True)

            frames = self.get_keyframes(self.ik_controls + self.fk_controls, start_frame, end_frame)
            if frames:

                original_time = cmds.currentTime(query=True)

                for frame in frames:
                    cmds.currentTime(frame)
                    self.ik_to_fk()
                    self.set_keyframe()

                cmds.currentTime(original_time)

        else:
            if self.switch_control and self.fk_controls and self.ik_controls:
                self.ik_to_fk()

                if self.key:
                    self.set_keyframe()

        cmds.undoInfo(closeChunk=True)

        return True

    def get_selection(self):

        selection = cmds.ls(sl=True)
        if selection:
            if cmds.objExists(f'{selection[0]}.controlType'):
                return selection[0]

    def get_data_parent(self, control):

        if cmds.objExists(f'{control}.dataParent'):
            connections = cmds.listConnections(f'{control}.dataParent', s=True)
            if connections:
                return connections[0]

    def get_switch_control(self, data_parent):

        if cmds.objExists(data_parent):
            return cd.getObjectFromDataAttr(data_parent, 'switchControl')

    def get_fk_controls(self, data_parent):

        if cmds.objExists(data_parent):
            return cd.getObjectFromDataAttr(data_parent, 'fkControls')

    def get_ik_controls(self, data_parent):

        if cmds.objExists(data_parent):
            return cd.getObjectFromDataAttr(data_parent, 'ikControls')

    def ik_to_fk(self):

        if self.switch_control:
            if cmds.getAttr(f'{self.switch_control}.IKSwitch') == 1:
                for fk, ik in zip(self.fk_controls, self.ik_controls):
                    cmds.matchTransform(fk, ik)

                    if not self.snap:
                        cmds.setAttr(f'{self.switch_control}.IKSwitch', 0)

            elif cmds.getAttr(f'{self.switch_control}.IKSwitch') == 0:
                for ik, fk in zip(self.ik_controls, self.fk_controls):
                    cmds.matchTransform(ik, fk)

                    if not self.snap:
                        cmds.setAttr(f'{self.switch_control}.IKSwitch', 1)

        return True

    def set_keyframe(self):
        current_time = cmds.currentTime(q=True)

        if not self.snap:
            cmds.setKeyframe(self.switch_control, attribute='IKSwitch', time=current_time)

        all_controls = self.fk_controls + self.ik_controls
        for ctrl in all_controls:
            attrs = cmds.listAttr(ctrl, keyable=True)
            for attr in attrs:
                cmds.setKeyframe(ctrl, attribute=attr, time=current_time)

        # Apply Euler Filter to all rotation curves
        rotation_curves = []
        for ctrl in all_controls:
            attrs = cmds.listAttr(ctrl, keyable=True)
            if attrs:
                for attr in attrs:
                    if attr in ['rotateX', 'rotateY', 'rotateZ']:
                        anim_curve = cmds.listConnections(f"{ctrl}.{attr}", type="animCurve")
                        if anim_curve:
                            rotation_curves.extend(anim_curve)

        if rotation_curves:
            cmds.filterCurve(rotation_curves)

        return True

    def get_keyframes(self, controls, start_frame, end_frame):
        keyed_frames = set()

        for control in controls:
            key_times = cmds.keyframe(control, query=True, timeChange=True)
            if key_times:
                filtered_times = [t for t in key_times if start_frame <= t <= end_frame]
                keyed_frames.update(filtered_times)

        return sorted(keyed_frames)

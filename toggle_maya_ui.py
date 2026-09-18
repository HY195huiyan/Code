

import maya.cmds as mc
import maya.mel as mm


def getGlobalActivePanel():
    return str(mm.eval('global string $gToggleMayaUIActivePanel; $ghetto2 = $gToggleMayaUIActivePanel;'))


def getTimeSliderVis():
    return str(mm.eval('global string $gToggleMayaTimeSliderVis; $ghetto6 = $gToggleMayaTimeSliderVis;')) or '1'


def setGlobalActivePanel(panel):
    mm.eval('global string $gToggleMayaUIActivePanel; $gToggleMayaUIActivePanel = "%s";' % panel)
    mm.eval('global string $gToggleMayaTimeSliderVis; $gToggleMayaTimeSliderVis = $gTimeSliderVisible')


def toggleMayaUI(status, printInfo=False, timeSlider=False):
    ''' Toggle Maya's window UIs on/off.  Speeds up bakeResults process. '''

    if printInfo:
        print(('Disabling Maya UI...', 'Enabling Maya UI...')[status])

    # $ghetto is needed to return value of $gMainPane.  Ghetto...
    gMainPane = str(mm.eval('global string $gMainPane; $ghetto = $gMainPane;'))

    windows = mc.lsUI(type='window')

    if not windows:
        return

    # Record active panel before disabling UI.
    if not status:
        panel = mc.getPanel(withFocus=True)
        setGlobalActivePanel(panel)
        '''
        if timeSlider:
            mm.eval('setTimeSliderVisible(0)')
        '''

    for window in windows:
        if window != 'MayaWindow' and window != 'CommandWindow' and mc.objExists(window):
            mc.window(window, edit=True, iconify=not status)

    if gMainPane:
        mc.paneLayout(gMainPane, edit=True, manage=status)

    if status:
        activePanel = getGlobalActivePanel()
        if activePanel:
            try:
                mc.setFocus(activePanel)
            except:
                pass
        setGlobalActivePanel('')
        mm.eval('setTimeSliderVisible('+getTimeSliderVis()+')')

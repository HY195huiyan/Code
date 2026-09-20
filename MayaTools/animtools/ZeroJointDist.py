import maya.cmds as mc
import maya.mel as mel

import vector_math as vm

from smpub.qt.QtWrapper.QtCore import (Property, QRect, Qt)
from smpub.qt.QtWrapper.QtWidgets import (QDialog, QHBoxLayout, QLabel, QMainWindow, QPushButton, QVBoxLayout)
from smpub.qt.QtWrapper.QtCompat import (wrapInstance)

from maya_ops import user_interface_ops


class ZeroJointDistanceUI(QDialog):
  def __init__(self):
    super(ZeroJointDistanceUI, self).__init__(parent=user_interface_ops.getMayaMainWindow())
    self.initUI()

  
  def initUI(self):

    self.setWindowTitle('Zero Joint Distances')
    
    dialogLayout = QVBoxLayout()
    self.setLayout(dialogLayout)
    
    
    self.label = QLabel('')
    self.label .setGeometry(QRect(0, 0, 181, 31))
    self.label .setAlignment(Qt.AlignCenter)
    dialogLayout.addWidget(self.label)
    
    btnLayout = QHBoxLayout()
    dialogLayout.addLayout(btnLayout)
    
    okBTN = QPushButton('OK')
    okBTN.clicked.connect(self.close)
    
    btnLayout.addWidget(okBTN)
    
    self.show()


def getControls(topNode, shortNames=False):
  transforms = mc.listRelatives(topNode, ad=True, f=True, type=['transform', 'joint'])
  controls = []
  
  if not transforms:
    return None
  
  for transform in transforms:
    if mc.objExists(transform + '.controlType'):
      if shortNames == False:
        controls.append(transform)
      else:
        shortCtrlName = transform.rsplit('|', 1)[1]
        controls.append(shortCtrlName)
  return controls


def getZeroJointDistance(startFrame=mc.playbackOptions(q=True, min=True), endFrame=mc.playbackOptions(q=True, max=True)):
  #list top nodes
  assemblies = mc.ls(assemblies=True)
  hasZeroJoint = False
  
  zeroJointPrintOut = 'timeRange: '+str(startFrame)+' - '+str(endFrame)+'\n\n'
  
  allZeroJointControls = []
  
  #list all controls
  for topNode in assemblies:
    allControls = getControls(topNode)
    
    if allControls:
      
      for ctrl in allControls:
        if ctrl.find('zeroJointControl') > -1:
          allZeroJointControls.append(ctrl)
          break
      
  for zeroJointCtrl in allZeroJointControls:
    
    startPos = mc.getAttr(zeroJointCtrl+'.translate', time=startFrame)
    endPos = mc.getAttr(zeroJointCtrl+'.translate', time=endFrame)
    distance = vm.distance(startPos[0], endPos[0])
    
    zeroJointCtrlShortName = zeroJointCtrl.rsplit('|', 1)[-1]
    #thisString = 'print "'+zeroJointCtrlShortName+' distance '+str(distance)+', timeRange: '+str(startFrame)+', '+str(endFrame)+'\\n";'
    #mel.eval(thisString)
    
    zeroJointPrintOut += zeroJointCtrlShortName+' distance: '+str(distance)+'\n\n'
        
  #open a UI and send the text to it
  if len(allZeroJointControls) > 0:
    UI = main()
    UI.label.setText(zeroJointPrintOut)
  else:
    mc.warning('No zero joint control(s) present in scene')
    
    
        
def main():
  global gzjdWindow
  try:
    gzjdWindow.close()
    gzjdWindow.deleteLater()
  except:
    pass
  
  gzjdWindow = ZeroJointDistanceUI()
  gzjdWindow.show()
  
  return gzjdWindow

from maya.api import OpenMaya
from maya.api import OpenMayaAnim

import construct_curve_from_anim


def resetAPIClipboard():
    """Declares both the API_CLIPBOARD and CLIP_ITEM_ARRAY global variables and clears their contents.

    :return:
    """
    global API_CLIPBOARD, CLIP_ITEM_ARRAY, ANIM_CURVES, CLIP_ITEMS
    API_CLIPBOARD = OpenMayaAnim.MAnimCurveClipboard.theAPIClipboard
    CLIP_ITEM_ARRAY = OpenMayaAnim.MAnimCurveClipboardItemArray()
    API_CLIPBOARD.clear()
    CLIP_ITEM_ARRAY.clear()
    ANIM_CURVES = []
    CLIP_ITEMS = []


def writeToAPIClipboard(animFile):
    """Takes the data from the .anim file and writes it to the API Clipboard

    :returns:
    """
    for node in animFile.nodes:
        nodeCurves = construct_curve_from_anim.constructAnimCurvesFromNodeAttrs(node, animFile)
        ANIM_CURVES.extend(nodeCurves)

    # Create a MFnCurve and MAnimCurveClipboardItem for every curve added to the ANIM_CURVES list
    for curve in ANIM_CURVES:
        newMFnCurve = OpenMayaAnim.MFnAnimCurve()
        newClipItem = OpenMayaAnim.MAnimCurveClipboardItem()
        newCurveObj = newMFnCurve.create(curve.animCurveType)

        # Set the data of the new MFnCurve
        newMFnCurve.setIsWeighted(curve.isWeighted)
        newMFnCurve.setPreInfinityType(curve.preInfinity)
        newMFnCurve.setPostInfinityType(curve.postInfinity)

        # Set the keys and data of each key of the new MFnCurve
        for i, animKey in enumerate(curve.animKeys):
            MFnKeys = construct_curve_from_anim.convertKeyBasedOnCurveType(animFile, animKey.inValue, animKey.outValue,
                                                                           curve.animCurveType)

            newMFnCurve.addKey(MFnKeys[0], MFnKeys[1])

            # If the new MFnCurve has fixed in or out tangents, set the tangents' angles and weights
            if animKey.inTangent == 1:
                newMFnCurve.setTangentsLocked(i, False)
                curveTanAngle = OpenMaya.MAngle(animKey.inTanAngle, animFile.angularUnit)
                newMFnCurve.setAngle(i, curveTanAngle, True)
                newMFnCurve.setWeight(i, animKey.inTanWeight, True)

            if animKey.outTangent == 1:
                newMFnCurve.setTangentsLocked(i, False)
                curveTanAngle = OpenMaya.MAngle(animKey.outTanAngle, animFile.angularUnit)
                newMFnCurve.setAngle(i, curveTanAngle, False)
                newMFnCurve.setWeight(i, animKey.outTanWeight, False)

            newMFnCurve.setInTangentType(i, animKey.inTangent)
            newMFnCurve.setOutTangentType(i, animKey.outTangent)

            newMFnCurve.setTangentsLocked(i, animKey.tangentsLocked)
            newMFnCurve.setWeightsLocked(i, animKey.weightsLocked)
            newMFnCurve.setIsBreakdown(i, animKey.isBreakdown)

        # Set the name and address info of the MAnimCurveClipboardItem
        newClipItem.setNameInfo(curve.nodeName, curve.fullAttributeName, curve.leafAttributeName)
        newClipItem.setAddressingInfo(curve.addressingInfo[0], curve.addressingInfo[1], curve.addressingInfo[2])

        # Set the MFnCurve to the MAnimCurveClipboardItem
        newClipItem.setAnimCurve(newCurveObj)

        # Add the new MAnimCurveClipboardItem to the CLIP_ITEM_ARRAY
        CLIP_ITEM_ARRAY.append(newClipItem)

    API_CLIPBOARD.set(CLIP_ITEM_ARRAY)

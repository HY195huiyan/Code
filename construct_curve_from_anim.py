import math
from maya.api import OpenMaya

# these numbers can be found in API docs on MFnAnimCurve
TANGENTS_TO_INDEX = {
    "constant": 0,
    "fixed": 1,
    "linear": 2,
    "flat": 3,
    "spline": 4,
    "step": 5,
    "slow": 6,
    "fast": 7,
    "clamped": 8,
    "plateau": 9,
    "stepnext": 10,
    "auto": 11,
    "autoease": 28,
    "automix": 27,
    "autocustom": 29
}


def convertToCurveType(inputType, outputType):
    """Determines the animCurveType variable.
    It takes the inputType + outputType parameters, adds them to a string, then gets an index number corresponding
    to this string as an int

    :param inputType: str, input type of the anim curve.
    :param outputType: str, output type of the anim curve.
    :return: int, the anim curve's type as a whole, converted to an int using a dict.
    """
    curveTypeStrToInt = {
        "kAnimCurveTA": 0,
        "kAnimCurveTL": 1,
        "kAnimCurveTT": 2,
        "kAnimCurveTU": 3,
        "kAnimCurveUA": 4,
        "kAnimCurveUL": 5,
        "kAnimCurveUT": 6,
        "kAnimCurveUU": 7,
    }

    curveTypeStrToChar = {
        "time": "T",
        "angular": "A",
        "linear": "L",
        "unitless": "U"
    }

    outCurveType = curveTypeStrToInt[
        f"kAnimCurve{curveTypeStrToChar[inputType]}{curveTypeStrToChar[outputType]}"]
    return outCurveType


def convertKeyBasedOnCurveType(animFile, inKeyVal, outKeyVal, animCurveType=0):
    if animCurveType < 4:
        if animCurveType != 2:
            inVal = OpenMaya.MTime(inKeyVal, animFile.timeUnit)
            outVal = outKeyVal
        else:
            inVal = OpenMaya.MTime(inKeyVal, animFile.timeUnit)
            outVal = OpenMaya.MTime(outKeyVal, animFile.timeUnit)
    else:
        if animCurveType != 6:
            inVal = inKeyVal
            outVal = outKeyVal
        else:
            inVal = inKeyVal
            outVal = OpenMaya.MTime(outKeyVal, animFile.timeUnit)

    return inVal, outVal


def convertToRadians(keyValue, animFile):
    """Converts the keyValue to radians if it is for a rotation curve and isn't in radians already

    :param keyValue: float, corresponds to the output angle of a rotation key. May or may not be in radians.
    :param animFile: AnimData, holds the data of the .anim file
    :return: float, contains the output angle of a rotation key in radians
    """
    if animFile.angularUnit != 1:
        convertedKey = math.radians(float(keyValue))
        return convertedKey
    return keyValue


def getOutValue(animFile, outValue, curveNameInfo):
    if "rotate" in curveNameInfo:
        outVal = float(convertToRadians(outValue, animFile))
    else:
        outVal = float(outValue)
    return outVal


def constructAnimCurvesFromNodeAttrs(node, animFile):
    """Creates the anim curves for every keyed attribute on a single object.

    :param node: str, node containing keyed attributes.
    :param animFile: AnimData, holds the data of the .anim file

    :returns:
    """
    outCurves = []
    nodeAttributeAnimCurves = {}
    for keyedAttr in animFile.keys:
        if node in keyedAttr:
            nodeAttributeAnimCurves.update({keyedAttr: animFile.keys[keyedAttr]})

    for animCurve in nodeAttributeAnimCurves:
        newAnimCurveKeys = []

        # Create an array of AnimKey objects to add to this new curve
        for key in nodeAttributeAnimCurves[animCurve]:
            keyData = key.split()
            newKey = AnimKey(animFile, keyData, animFile.nameInfo[animCurve][0])
            newAnimCurveKeys.append(newKey)
        newAnimCurveData = animFile.animCurveData[animCurve]

        # Create the anim curve and append it to the ANIM_CURVES list.
        newAnimCurve = AnimCurve(animFile.nameInfo[animCurve][0], animFile.addressInfo[animCurve][0],
                                 newAnimCurveData, newAnimCurveKeys)
        outCurves.append(newAnimCurve)

    return outCurves


class AnimCurve:
    def __init__(self, namingInfo, addressingInfo, animCurveData, animKeys=[]):
        # .anim Name Info
        self.namingInfo = namingInfo
        self.fullAttributeName = namingInfo.split()[0]
        self.leafAttributeName = namingInfo.split()[1]
        self.nodeName = namingInfo.split()[2]

        # .anim Address Info
        self.addressingInfo = [int(addressingInfo.split()[0]), int(addressingInfo.split()[1]),
                               int(addressingInfo.split()[2])]

        # animData section of animFile that stores the key information
        self.inputType = animCurveData[0]
        self.outputType = animCurveData[1]
        self.animCurveType = convertToCurveType(self.inputType, self.outputType)
        self.isWeighted = int(animCurveData[2])
        self.preInfinity = TANGENTS_TO_INDEX[animCurveData[3]]
        self.postInfinity = TANGENTS_TO_INDEX[animCurveData[4]]

        # anim Keys
        self.animKeys = animKeys


class AnimKey:
    def __init__(self, animFile, keyData=[], curveNameInfo=""):
        self.animFile = animFile
        self.inValue = float(keyData[0])
        self.outValue = getOutValue(self.animFile, keyData[1], curveNameInfo)

        self.inTangent = int(TANGENTS_TO_INDEX[keyData[2]])
        self.outTangent = int(TANGENTS_TO_INDEX[keyData[3]])
        self.tangentsLocked = int(keyData[4])
        self.weightsLocked = int(keyData[5])
        self.isBreakdown = int(keyData[6])
        self.inTanAngle = 0
        self.inTanWeight = 0
        self.outTanAngle = 0
        self.outTanWeight = 0
        self.setTangentWeightsAndAngles(self.inTangent, self.outTangent, keyData)

    def setTangentWeightsAndAngles(self, inTangentType, outTangentType, keyData):
        """Sets the inTanAngle, inTanWeight, outTanAngle, and outTanWeight if the inTangentType and/or outTangentType
        are of type "fixed" (represented as a 1 in TANGENTS_TO_INDEX)

        :param inTangentType: int, the input Tangent type of the key
        :param outTangentType: int, the output Tangent type of the key
        :param keyData: list, contains the data of the key as a series of strings
        :return:
        """

        if inTangentType == 1:
            self.inTanAngle = float(keyData[7])
            self.inTanWeight = float(keyData[8])

        if outTangentType == 1:
            self.outTanAngle = float(keyData[7])
            self.outTanWeight = float(keyData[8])

        if inTangentType == 1 and outTangentType == 1:
            self.outTanAngle = float(keyData[9])
            self.outTanWeight = float(keyData[10])

    def printKeyData(self):
        print(
            f"{self.inValue} {self.outValue} {self.inTangent} {self.outTangent} {self.tangentsLocked} {self.weightsLocked} {self.isBreakdown}")

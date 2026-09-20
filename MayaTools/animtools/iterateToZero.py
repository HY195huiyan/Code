
import traceback
import math

import maya.cmds as mc


def main(driver, contingent, incrementInit, attrCycle=None, iterLimit=100, zeroTolerance=0.0001):
    '''
    driver = nodeAttrPair to set values on to attempt to reach zero on the ...
    contingent = nodeAndAttrPair to measure the driver against
    attrCycle = if not None, will be used as the modulo for the iterative "set"/setAttr value on the driver
                *example: 360.0 for a pole vector twist to keep the solve bounded
    iterLimit =  limit to exit function and prevent excessive/infinite looping
    zeroTolerance = exit value
    '''

    undoState = mc.undoInfo(q=True, state=True)
    # mc.undoInfo(state=False)
    start = mc.timerX()
    print('timer started...')
    result = None
    try:
        result = doIt(driver, contingent, incrementInit, attrCycle, iterLimit, zeroTolerance)
    except:
        traceback.print_exc()
    finally:
        mc.undoInfo(state=undoState)

    totalTime = mc.timerX(startTime=start)
    print('total time: %s' % totalTime)
    print('result: %s' % result)

    return result


def cleanZeroes(driver, number, zeroTolerance):
    decimal = float(number - int(number))
    if math.fabs(zeroTolerance - math.fabs(decimal) ) <= zeroTolerance:
        mc.setAttr(driver, float(int(number)))
    return True


def doIt(driver, contingent, incrementInit, attrCycle, iterLimit, zeroTolerance):

    driverValue = mc.getAttr(driver)

    increment = mc.getAttr(incrementInit)

    if attrCycle is not None:
        attrCycle = math.fabs(float(attrCycle))

    iterCount = 0
    while math.fabs(mc.getAttr(contingent)) >= zeroTolerance or iterCount > iterLimit:

        if iterCount > iterLimit:
            print('Went over iteration limit of %s' % iterLimit)
            return iterCount
        iterCount += 1

        # get current value we would like to see at zero
        prevTestValue = mc.getAttr(contingent)
        #print 'prevTestValue was', prevTestValue

        # set the driver - ik twist to the new contingent value
        driverValue += increment
        if attrCycle is not None:
            if attrCycle > 0.0:
                mc.setAttr(driver, driverValue % attrCycle)
        else:
            mc.setAttr(driver, driverValue)

        #print 'driver value %s' %driverValue
        # mc.refresh()
        # mc.pause(sec=1)

        # check if that made the contingent (angle) closer to zero - if yes - keep going
        if mc.getAttr(contingent) < prevTestValue:
            continue
        else:
            # if not - flip the value and go the other direction
            increment *= -1.0

            # also decrease the value by half so that we don't perpetually ping-pong over zero
            increment /= 2.0

    #clean driver floating point values if within tolerance of zero
    cleanZeroes(driver, driverValue, zeroTolerance)

    return iterCount

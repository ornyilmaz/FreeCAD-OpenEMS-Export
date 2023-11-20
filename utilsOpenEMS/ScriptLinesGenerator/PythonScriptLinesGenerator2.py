#   author: Lubomir Jagos
#
#
import os
from PySide2 import QtGui, QtCore, QtWidgets
import numpy as np
import re
import math

from utilsOpenEMS.GlobalFunctions.GlobalFunctions import _bool, _r
from utilsOpenEMS.ScriptLinesGenerator.OctaveScriptLinesGenerator2 import OctaveScriptLinesGenerator2
from utilsOpenEMS.GuiHelpers.GuiHelpers import GuiHelpers
from utilsOpenEMS.GuiHelpers.FactoryCadInterface import FactoryCadInterface

class PythonScriptLinesGenerator2(OctaveScriptLinesGenerator2):

    #
    #   constructor, get access to form GUI
    #
    def __init__(self, form, statusBar = None):
        self.form = form
        self.statusBar = statusBar

        self.internalPortIndexNamesList = {}
        self.internalNF2FFIndexNamesList = {}
        self.internalMaterialIndexNamesList = {}

        #
        # GUI helpers function like display message box and so
        #
        self.guiHelpers = GuiHelpers(self.form, statusBar = self.statusBar)
        self.cadHelpers = FactoryCadInterface.createHelper()

    def getCoordinateSystemScriptLines(self):
        genScript = ""

        genScript += "#######################################################################################################################################\n"
        genScript += "# COORDINATE SYSTEM\n"
        genScript += "#######################################################################################################################################\n"

        """ # Till now not used, just using rectangular coordination type, cylindrical MUST BE IMPLEMENTED!
        gridCoordsType = self.getModelCoordsType()
        if (gridCoordsType == "rectangular"):
            genScript += "CSX = InitCSX('CoordSystem',0); # Cartesian coordinate system.\n"
        elif (gridCoordsType == "cylindrical"):
            genScript += "CSX = InitCSX('CoordSystem',1); # Cylindrical coordinate system.\n"
        else:
            genScript += "%%%%%% ERROR GRID COORDINATION SYSTEM TYPE UNKNOWN"				
        """

        genScript += "def mesh():\n"
        genScript += "\tx,y,z\n"
        genScript += "\n"
        genScript += "mesh.x = np.array([]) # mesh variable initialization (Note: x y z implies type Cartesian).\n"
        genScript += "mesh.y = np.array([])\n"
        genScript += "mesh.z = np.array([])\n"
        genScript += "\n"
        genScript += "openEMS_grid = CSX.GetGrid()\n"
        genScript += "openEMS_grid.SetDeltaUnit(unit) # First call with empty mesh to set deltaUnit attribute.\n"
        genScript += "\n"

        return genScript

    def getMaterialDefinitionsScriptLines(self, items, outputDir=None):
        genScript = ""

        genScript += "#######################################################################################################################################\n"
        genScript += "# MATERIALS AND GEOMETRY\n"
        genScript += "#######################################################################################################################################\n"

        # PEC is created by default due it's used when microstrip port is defined, so it's here to have it here.
        # Note that the user will need to create a metal named 'PEC' and populate it to avoid a warning
        # about "no primitives assigned to metal 'PEC'".
        genScript += "materialList = {}\n"                              # !!!THIS IS ON PURPOSE NOT LITERAL {} brackets are generated into code for python
        genScript += "\n"

        if not items:
            return genScript

        materialCounter = -1    #increment of this variable is at beginning f for loop so start at 0
        simObjectCounter = 0
        for [item, currSetting] in items:

            #
            #   Materials are stored in variables in python script, so this is counter to create universal name ie. material_1, material_2, ...
            #
            materialCounter += 1

            print(currSetting)
            if (currSetting.getName() == 'Material Default'):
                print("#Material Default")
                print("---")
                continue

            print("#")
            print("#MATERIAL")
            print("#name: " + currSetting.getName())
            print("#epsilon, mue, kappa, sigma")
            print("#" + str(currSetting.constants['epsilon']) + ", " + str(currSetting.constants['mue']) + ", " + str(
                currSetting.constants['kappa']) + ", " + str(currSetting.constants['sigma']))

            genScript += f"## MATERIAL - {currSetting.getName()}\n"
            materialPythonVariable = f"materialList['{currSetting.getName()}']"

            if (currSetting.type == 'metal'):
                genScript += f"{materialPythonVariable} = CSX.AddMetal('{currSetting.getName()}')\n"
                self.internalMaterialIndexNamesList[currSetting.getName()] = materialPythonVariable
            elif (currSetting.type == 'userdefined'):
                self.internalMaterialIndexNamesList[currSetting.getName()] = materialPythonVariable
                genScript += f"{materialPythonVariable} = CSX.AddMaterial('{currSetting.getName()}')\n"

                smp_args = []
                if str(currSetting.constants['epsilon']) != "0":
                    smp_args.append(f"epsilon={str(currSetting.constants['epsilon'])}")
                if str(currSetting.constants['mue']) != "0":
                    smp_args.append(f"mue={str(currSetting.constants['mue'])}")
                if str(currSetting.constants['kappa']) != "0":
                    smp_args.append(f"kappa={str(currSetting.constants['kappa'])}")
                if str(currSetting.constants['sigma']) != "0":
                    smp_args.append(f"sigma={str(currSetting.constants['sigma'])}")

                genScript += f"{materialPythonVariable}.SetMaterialProperty(" + ", ".join(smp_args) + ")\n"
            elif (currSetting.type == 'conducting sheet'):
                genScript += f"{materialPythonVariable} = CSX.AddConductingSheet(" + \
                             f"'{currSetting.getName()}', " + \
                             f"conductivity={str(currSetting.constants['conductingSheetConductivity'])}, " + \
                             f"thickness={str(currSetting.constants['conductingSheetThicknessValue'])}*{str(currSetting.getUnitsAsNumber(currSetting.constants['conductingSheetThicknessUnits']))}" + \
                             f")\n"
                self.internalMaterialIndexNamesList[currSetting.getName()] = materialPythonVariable

            # first print all current material children names
            for k in range(item.childCount()):
                childName = item.child(k).text(0)
                print("##Children:")
                print("\t" + childName)

            # now export material children, if it's object export as STL, if it's curve export as curve
            for k in range(item.childCount()):
                simObjectCounter += 1               #counter for objects
                childName = item.child(k).text(0)

                #
                #	getting item priority
                #
                objModelPriorityItemName = item.parent().text(0) + ", " + item.text(0) + ", " + childName
                objModelPriority = self.getItemPriority(objModelPriorityItemName)

                # getting reference to FreeCAD object
                freeCadObj = [i for i in self.cadHelpers.getObjects() if (i.Label) == childName][0]

                if (freeCadObj.Name.find("Discretized_Edge") > -1):
                    #
                    #	Adding discretized curve
                    #

                    curvePoints = freeCadObj.Points
                    genScript += "points = [];\n"
                    for k in range(0, len(curvePoints)):
                        genScript += "points(1," + str(k + 1) + ") = " + str(curvePoints[k].x) + ";"
                        genScript += "points(2," + str(k + 1) + ") = " + str(curvePoints[k].y) + ";"
                        genScript += "points(3," + str(k + 1) + ") = " + str(curvePoints[k].z) + ";"
                        genScript += "\n"

                    genScript += "CSX = AddCurve(CSX,'" + currSetting.getName() + "'," + str(
                        objModelPriority) + ", points);\n"
                    print("Curve added to generated script using its points.")

                elif (freeCadObj.Name.find("Sketch") > -1):
                    #
                    #	Adding JUST LINE SEGMENTS FROM SKETCH, THIS NEED TO BE IMPROVED TO PROPERLY GENERATE CURVE FROM SKETCH,
                    #	there can be circle, circle arc and maybe something else in sketch geometry
                    #

                    genScript += f"points_x = np.array([])\n"
                    genScript += f"points_y = np.array([])\n"
                    genScript += f"points_z = np.array([])\n"
                    for geometryObj in freeCadObj.Geometry:
                        if (str(type(geometryObj)).find("LineSegment") > -1):
                            genScript += f"points_x.append({str(geometryObj.StartPoint.x)})\n"
                            genScript += f"points_y.append({str(geometryObj.StartPoint.y)})\n"
                            genScript += f"points_z.append({str(geometryObj.StartPoint.z)})\n"

                            genScript += f"points_x.append({str(geometryObj.EndPoint.x)})\n"
                            genScript += f"points_y.append({str(geometryObj.EndPoint.y)})\n"
                            genScript += f"points_z.append({str(geometryObj.EndPoint.z)})\n"

                    genScript += f"points = np.array([{str(geometryObj.StartPoint.x)}, {str(geometryObj.StartPoint.y)}, {str(geometryObj.StartPoint.z)}])\n"

                    genScript += "\n"
                    genScript += f"{self.internalMaterialIndexNamesList[currSetting.getName()]}.AddCurve(points, priority={str(objModelPriority)})\n"

                    print("Line segments from sketch added.")

                else:
                    #
                    #	Adding part as STL model, first export it into file and that file load using octave openEMS function
                    #

                    currDir, baseName = self.getCurrDir()
                    stlModelFileName = childName + "_gen_model.stl"

                    #genScript += "CSX = ImportSTL( CSX, '" + currSetting.getName() + "'," + str(
                    #    objModelPriority) + ", [currDir '/" + stlModelFileName + "'],'Transform',{'Scale', fc_unit/unit} );\n"
                    genScript += f"{materialPythonVariable}.AddPolyhedronReader(os.path.join(currDir,'{stlModelFileName}'), priority={objModelPriority}).ReadFile()\n"

                    #   _____ _______ _                                        _   _
                    #  / ____|__   __| |                                      | | (_)
                    # | (___    | |  | |        __ _  ___ _ __   ___ _ __ __ _| |_ _  ___  _ __
                    #  \___ \   | |  | |       / _` |/ _ \ '_ \ / _ \ '__/ _` | __| |/ _ \| '_ \
                    #  ____) |  | |  | |____  | (_| |  __/ | | |  __/ | | (_| | |_| | (_) | | | |
                    # |_____/   |_|  |______|  \__, |\___|_| |_|\___|_|  \__,_|\__|_|\___/|_| |_|
                    #                           __/ |
                    #                          |___/
                    #
                    # going through each concrete material items and generate their .stl files

                    currDir = os.path.dirname(self.cadHelpers.getCurrDocumentFileName())
                    partToExport = [i for i in self.cadHelpers.getObjects() if (i.Label) == childName]

                    #output directory path construction, if there is no parameter for output dir then output is in current freecad file dir
                    if (not outputDir is None):
                        exportFileName = os.path.join(outputDir, stlModelFileName)
                    else:
                        exportFileName = os.path.join(currDir, stlModelFileName)

                    self.cadHelpers.exportSTL(partToExport, exportFileName)
                    print("Material object exported as STL into: " + stlModelFileName)

            genScript += "\n"

        return genScript

    def getCartesianOrCylindricalScriptLinesFromStartStop(self, bbCoords, startPointName=None, stopPointName=None):
        genScript = "";
        refUnit = self.getUnitLengthFromUI_m()  # Coordinates need to be given in drawing units
        sf = self.getFreeCADUnitLength_m() / refUnit  # scaling factor for FreeCAD units to drawing units

        strPortCoordsCartesianToCylindrical = ""
        strPortCoordsCartesianToCylindrical += "[generatedAuxTheta, generatedAuxR, generatedAuxZ] = cart2pol(portStart);\n"
        strPortCoordsCartesianToCylindrical += "portStart = [generatedAuxR, generatedAuxTheta, generatedAuxZ];\n"
        strPortCoordsCartesianToCylindrical += "[generatedAuxTheta, generatedAuxR, generatedAuxZ] = cart2pol(portStop);\n"
        strPortCoordsCartesianToCylindrical += "portStop = [generatedAuxR, generatedAuxTheta, generatedAuxZ];\n"

        if (self.getModelCoordsType() == "cylindrical"):
            # CYLINDRICAL COORDINATE TYPE USED
            if ((bbCoords.XMin <= 0 and bbCoords.YMin <= 0 and bbCoords.XMax >= 0 and bbCoords.YMax >= 0) or
                (bbCoords.XMin >= 0 and bbCoords.YMin >= 0 and bbCoords.XMax <= 0 and bbCoords.YMax <= 0)
            ):
                if (bbCoords.XMin != bbCoords.XMax and bbCoords.YMin != bbCoords.YMax):
                    #
                    # origin [0,0,0] is contained inside boundary box, so now must used theta 0-360deg
                    #
                    radius1 = math.sqrt((sf * bbCoords.XMin) ** 2 + (sf * bbCoords.YMin) ** 2)
                    radius2 = math.sqrt((sf * bbCoords.XMax) ** 2 + (sf * bbCoords.YMax) ** 2)

                    genScript += 'portStart = [ 0, -math.pi, {0:g} ]\n'.format(_r(sf * bbCoords.ZMin))
                    genScript += 'portStop  = [ {0:g}, math.pi, {1:g} ]\n'.format(_r(max(radius1, radius2)),
                                                                              _r(sf * bbCoords.ZMax))
                else:
                    #
                    #   Object is thin it's plane or line crossing origin
                    #
                    radius1 = math.sqrt((sf * bbCoords.XMin) ** 2 + (sf * bbCoords.YMin) ** 2)
                    theta1 = math.atan2(bbCoords.YMin, bbCoords.XMin)
                    radius2 = -math.sqrt((sf * bbCoords.XMax) ** 2 + (sf * bbCoords.YMax) ** 2)

                    genScript += 'portStart = [{0:g}, {1:g}, {2:g}]\n'.format(_r(radius1), _r(theta1), _r(sf * bbCoords.ZMin))
                    genScript += 'portStop = [{0:g}, {1:g}, {2:g}]\n'.format(_r(radius2), _r(theta1), _r(sf * bbCoords.ZMax))
                    genScript += '\n'
            else:
                #
                # port is lying outside origin
                #
                genScript += 'portStart = [ {0:g}, {1:g}, {2:g} ]\n'.format(_r(sf * bbCoords.XMin),
                                                                             _r(sf * bbCoords.YMin),
                                                                             _r(sf * bbCoords.ZMin))
                genScript += 'portStop  = [ {0:g}, {1:g}, {2:g} ]\n'.format(_r(sf * bbCoords.XMax),
                                                                             _r(sf * bbCoords.YMax),
                                                                             _r(sf * bbCoords.ZMax))
                genScript += strPortCoordsCartesianToCylindrical

        else:
            # CARTESIAN GRID USED
            genScript += 'portStart = [ {0:g}, {1:g}, {2:g} ]\n'.format(_r(sf * bbCoords.XMin),
                                                                         _r(sf * bbCoords.YMin),
                                                                         _r(sf * bbCoords.ZMin))
            genScript += 'portStop  = [ {0:g}, {1:g}, {2:g} ]\n'.format(_r(sf * bbCoords.XMax),
                                                                         _r(sf * bbCoords.YMax),
                                                                         _r(sf * bbCoords.ZMax))

        if (not startPointName is None):
            genScript = genScript.replace("portStart", startPointName)
        if (not stopPointName is None):
            genScript = genScript.replace("portStop", stopPointName)

        return genScript

    def getPortDefinitionsScriptLines(self, items):
        genScript = ""
        if not items:
            return genScript

        refUnit = self.getUnitLengthFromUI_m()  # Coordinates need to be given in drawing units
        sf = self.getFreeCADUnitLength_m() / refUnit  # scaling factor for FreeCAD units to drawing units

        # port index counter, they are generated into port{} cell variable for octave, cells index starts at 1
        genScriptPortCount = 1

        # nf2ff box counter, they are stored inside octave cell variable {} so this is to index them properly, in octave cells index starts at 1
        genNF2FFBoxCounter = 1

        #
        #   This here generates string for port excitation field, ie. for z+ generates [0 0 1], for y- generates [0 -1 0]
        #       Options for select field x,y,z were removed from GUI, but left here due there could be saved files from previous versions
        #       with these options so to keep backward compatibility they are treated as positive direction in that directions.
        #

        #baseVectorStr = {'x': '[1 0 0]', 'y': '[0 1 0]', 'z': '[0 0 1]', 'x+': '[1 0 0]', 'y+': '[0 1 0]', 'z+': '[0 0 1]', 'x-': '[-1 0 0]', 'y-': '[0 -1 0]', 'z-': '[0 0 -1]', 'XY plane, top layer': '[0 0 -1]', 'XY plane, bottom layer': '[0 0 1]', 'XZ plane, front layer': '[0 -1 0]', 'XZ plane, back layer': '[0 1 0]', 'YZ plane, right layer': '[-1 0 0]', 'YZ plane, left layer': '[1 0 0]',}
        #ERROR: followed baseVectorStr is just to generate something but need to take into consideration also sign of propagation direction
        baseVectorStr = {'x': "'x'", 'y': "'y'", 'z': "'z'", 'x+': "'x'", 'y+': "'y'", 'z+': "'z'", 'x-': "'x'", 'y-': "'y'", 'z-': "'z'", 'XY plane, top layer': "'z'", 'XY plane, bottom layer': "'z'", 'XZ plane, front layer': "'y'", 'XZ plane, back layer': "'y'", 'YZ plane, right layer': "'z'", 'YZ plane, left layer': "'x'",}

        mslDirStr = {'x': "'x'", 'y': "'y'", 'z': "'z'", 'x+': "'x'", 'y+': "'y'", 'z+': "'z'", 'x-': "'x'", 'y-': "'y'", 'z-': "'z'",}
        coaxialDirStr = {'x': '0', 'y': '1', 'z': '2', 'x+': '0', 'y+': '1', 'z+': '2', 'x-': '0', 'y-': '1', 'z-': '2',}
        coplanarDirStr = {'x': '0', 'y': '1', 'z': '2', 'x+': '0', 'y+': '1', 'z+': '2', 'x-': '0', 'y-': '1', 'z-': '2',}
        striplineDirStr = {'x': '0', 'y': '1', 'z': '2', 'x+': '0', 'y+': '1', 'z+': '2', 'x-': '0', 'y-': '1', 'z-': '2',}
        probeDirStr = {'x': '0', 'y': '1', 'z': '2', 'x+': '0', 'y+': '1', 'z+': '2', 'x-': '0', 'y-': '1', 'z-': '2',}

        genScript += "#######################################################################################################################################\n"
        genScript += "# PORTS\n"
        genScript += "#######################################################################################################################################\n"
        genScript += "port = {}\n"
        genScript += "portNamesAndNumbersList = {}\n"

        for [item, currSetting] in items:

            print(f"#PORT - {currSetting.getName()} - {currSetting.getType()}")

            objs = self.cadHelpers.getObjects()
            for k in range(item.childCount()):
                childName = item.child(k).text(0)

                genScript += "## PORT - " + currSetting.getName() + " - " + childName + "\n"

                freecadObjects = [i for i in objs if (i.Label) == childName]

                # print(freecadObjects)
                for obj in freecadObjects:
                    # BOUNDING BOX
                    bbCoords = obj.Shape.BoundBox
                    print('\tFreeCAD lumped port BoundBox: ' + str(bbCoords))

                    #
                    #	getting item priority
                    #
                    priorityItemName = item.parent().text(0) + ", " + item.text(0) + ", " + childName
                    priorityIndex = self.getItemPriority(priorityItemName)

                    #
                    # PORT openEMS GENERATION INTO VARIABLE
                    #
                    if (currSetting.getType() == 'lumped'):
                        genScript += self.getCartesianOrCylindricalScriptLinesFromStartStop(bbCoords)

                        if currSetting.infiniteResistance:
                            genScript += 'portR = inf\n'
                        else:
                            genScript += 'portR = ' + str(currSetting.R) + '\n'

                        genScript += 'portUnits = ' + str(currSetting.getRUnits()) + '\n'
                        genScript += "portExcitationAmplitude = " + str(currSetting.excitationAmplitude) + "\n"
                        genScript += 'portDirection = \'' + currSetting.direction + '\'\n'

                        genScript += 'port[' + str(genScriptPortCount) + '] = FDTD.AddLumpedPort(' + \
                                     'port_nr=' + str(genScriptPortCount) + ', ' + \
                                     'R=portR*portUnits, start=portStart, stop=portStop, p_dir=portDirection, ' + \
                                     'priority=' + str(priorityIndex) + ', ' + \
                                     'excite=' + ('1.0*portExcitationAmplitude' if currSetting.isActive else '0') + ')\n'

                        internalPortName = currSetting.name + " - " + obj.Label
                        self.internalPortIndexNamesList[internalPortName] = genScriptPortCount
                        genScript += f'portNamesAndNumbersList["{obj.Label}"] = {genScriptPortCount};\n'
                        genScriptPortCount += 1

                    #
                    #   ERROR - BELOW STILL NOT REWRITTEN INTO PYTHON!!!
                    #

                    elif (currSetting.getType() == 'microstrip'):
                        portStartX, portStartY, portStartZ, portStopX, portStopY, portStopZ = currSetting.getMicrostripStartStopCoords(bbCoords, sf)
                        bbCoords.Xmin = portStartX
                        bbCoords.Ymin = portStartY
                        bbCoords.Zmin = portStartZ
                        bbCoords.Xmax = portStopX
                        bbCoords.Ymax = portStopY
                        bbCoords.Zmax = portStopZ
                        genScript += self.getCartesianOrCylindricalScriptLinesFromStartStop(bbCoords)

                        if currSetting.infiniteResistance:
                            genScript += 'portR = inf\n'
                        else:
                            genScript += 'portR = ' + str(currSetting.R) + '\n'

                        genScript += 'portUnits = ' + str(currSetting.getRUnits()) + '\n'

                        #
                        #   if currSetting.isActive == False then excitation is 0
                        #
                        genScript += f"portExcitationAmplitude = {str(currSetting.excitationAmplitude)} * {'1' if currSetting.isActive else '0'}\n"

                        genScript += 'mslDir = {}\n'.format(mslDirStr.get(currSetting.mslPropagation[0], '?')) #use just first letter of propagation direction
                        genScript += 'mslEVec = {}\n'.format(baseVectorStr.get(currSetting.direction, '?'))

                        feedShiftStr = {False: "", True: ", FeedShift=" + str(_r(currSetting.mslFeedShiftValue / self.getUnitLengthFromUI_m() * currSetting.getUnitsAsNumber(currSetting.mslFeedShiftUnits)))}
                        measPlaneStr = {False: "", True: ", MeasPlaneShift=" + str(_r(currSetting.mslMeasPlaneShiftValue / self.getUnitLengthFromUI_m() * currSetting.getUnitsAsNumber(currSetting.mslMeasPlaneShiftUnits)))}

                        isActiveMSLStr = {False: "", True: ", 'ExcitePort', true"}

                        genScript_R = ", 'Feed_R', portR*portUnits"

                        genScript += f'port[{str(genScriptPortCount)}] = FDTD.AddMSLPort(' + \
                                         f'{str(genScriptPortCount)}, ' + \
                                         f"{self.internalMaterialIndexNamesList[currSetting.mslMaterial]}, " + \
                                         f'portStart, ' + \
                                         f'portStop, ' + \
                                         f'mslDir, ' + \
                                         f'mslEVec, ' + \
                                         f"excite=portExcitationAmplitude, " + \
                                         f'priority={str(priorityIndex)}, ' + \
                                         f'Feed_R=portR*portUnits' + \
                                         feedShiftStr.get(True) + \
                                         measPlaneStr.get(True) + \
                                   f")\n"

                        internalPortName = currSetting.name + " - " + obj.Label
                        self.internalPortIndexNamesList[internalPortName] = genScriptPortCount
                        genScript += f'portNamesAndNumbersList["{obj.Label}"] = {genScriptPortCount};\n'
                        genScriptPortCount += 1

                    elif (currSetting.getType() == 'circular waveguide'):
                        #
                        #   NOV 2023 - PYTHON API NOT IMPLEMENTED
                        #
                        genScript += "%% circular port openEMS code should be here, NOT IMPLEMENTED python API for it\n"

                    elif (currSetting.getType() == 'rectangular waveguide'):
                        portStartX, portStartY, portStartZ, portStopX, portStopY, portStopZ, waveguideWidth, waveguideHeight = currSetting.getRectangularWaveguideStartStopWidthHeight(bbCoords, sf)
                        bbCoords.Xmin = portStartX
                        bbCoords.Ymin = portStartY
                        bbCoords.Zmin = portStartZ
                        bbCoords.Xmax = portStopX
                        bbCoords.Ymax = portStopY
                        bbCoords.Zmax = portStopZ
                        genScript += self.getCartesianOrCylindricalScriptLinesFromStartStop(bbCoords)

                        genScript += f"portExcitationAmplitude = {str(currSetting.excitationAmplitude)} * {'1' if currSetting.isActive else '0'}\n"

                        genScript += f'port[{str(genScriptPortCount)}] = FDTD.AddRectWaveGuidePort(' + \
                                     f'{str(genScriptPortCount)}, ' + \
                                     f'portStart, ' + \
                                     f'portStop, ' + \
                                     f'"{currSetting.waveguideRectDir[0]}", ' + \
                                     f'{waveguideWidth}, ' + \
                                     f'{waveguideHeight}, ' + \
                                     f'"{currSetting.modeName}", ' + \
                                     f"excite=portExcitationAmplitude, " + \
                                     f'priority={str(priorityIndex)}, ' + \
                                     f")\n"

                        internalPortName = currSetting.name + " - " + obj.Label
                        self.internalPortIndexNamesList[internalPortName] = genScriptPortCount
                        genScript += f'portNamesAndNumbersList["{obj.Label}"] = {genScriptPortCount};\n'
                        genScriptPortCount += 1
                    elif (currSetting.getType() == 'coaxial'):
                        #
                        #   NOV 2023 - PYTHON API NOT IMPLEMENTED
                        #
                        genScript += '# ERROR: NOT IMPLEMENTED IN PYTHON INTERFACE coaxial port\n'

                    elif (currSetting.getType() == 'coplanar'):
                        #
                        #   NOV 2023 - PYTHON API NOT IMPLEMENTED
                        #
                        genScript += '# ERROR: NOT IMPLEMENTED IN PYTHON INTERFACE coplanar port\n'

                    elif (currSetting.getType() == 'stripline'):
                        #
                        #   NOV 2023 - PYTHON API NOT IMPLEMENTED
                        #
                        genScript += '# ERROR: NOT IMPLEMENTED IN PYTHON INTERFACE stripline port\n'

                    elif (currSetting.getType() == 'curve'):
                        genScript += '# ERROR: NOT IMPLEMENTED IN PYTHON INTERFACE curve port\n'

                    else:
                        genScript += '% Unknown port type. Nothing was generated. \n'

            genScript += "\n"

        return genScript

    def getProbeDefinitionsScriptLines(self, items):
        genScript = ""
        if not items:
            return genScript

        refUnit = self.getUnitLengthFromUI_m()  # Coordinates need to be given in drawing units
        sf = self.getFreeCADUnitLength_m() / refUnit  # scaling factor for FreeCAD units to drawing units

        # counters for indexing generated python code variables containing list of generated object by their type
        genProbeCounter = 1
        genDumpBoxCounter = 1

        # nf2ff box counter, they are stored inside octave cell variable nf2ff{} so this is to index them properly, in octave cells index starts at 1
        genNF2FFBoxCounter = 1

        #
        #   This here generates string for port excitation field, ie. for z+ generates [0 0 1], for y- generates [0 -1 0]
        #       Options for select field x,y,z were removed from GUI, but left here due there could be saved files from previous versions
        #       with these options so to keep backward compatibility they are treated as positive direction in that directions.
        #
        baseVectorStr = {'x': '0', 'y': '1', 'z': '2', 'x+': '0', 'y+': '1', 'z+': '2', 'x-': '0', 'y-': '1', 'z-': '2', 'XY plane, top layer': '2', 'XY plane, bottom layer': '2', 'XZ plane, front layer': '1', 'XZ plane, back layer': '1', 'YZ plane, right layer': '0', 'YZ plane, left layer': '0',}
        probeDirStr = {'x': '0', 'y': '1', 'z': '2', 'x+': '0', 'y+': '1', 'z+': '2', 'x-': '0', 'y-': '1', 'z-': '2',}

        genScript += "#######################################################################################################################################\n"
        genScript += "# PROBES\n"
        genScript += "#######################################################################################################################################\n"
        genScript += "nf2ffBoxList = {}\n"
        genScript += "dumpBoxList = {}\n"
        genScript += "probeList = {}\n"
        genScript += "\n"

        for [item, currSetting] in items:

            print(f"#PROBE - {currSetting.getName()} - {currSetting.getType()}")

            objs = self.cadHelpers.getObjects()
            for k in range(item.childCount()):
                childName = item.child(k).text(0)

                genScript += "# PROBE - " + currSetting.getName() + " - " + childName + "\n"

                freecadObjects = [i for i in objs if (i.Label) == childName]

                # print(freecadObjects)
                for obj in freecadObjects:
                    print(f"\t{obj.Label}")
                    # BOUNDING BOX
                    bbCoords = obj.Shape.BoundBox
                    print(f"\t\t{bbCoords}")

                    #
                    # PROBE openEMS GENERATION INTO VARIABLE
                    #
                    if (currSetting.getType() == "probe"):
                        probeName = f"{currSetting.name}_{childName}"
                        genScript += f'probeName = "{probeName}"\n'

                        genScript += 'probeDirection = {}\n'.format(baseVectorStr.get(currSetting.direction, '?'))

                        if currSetting.probeType == "voltage":
                            genScript += 'probeType = 0\n'
                        elif currSetting.probeType == "current":
                            genScript += 'probeType = 1\n'
                        elif currSetting.probeType == "E field":
                            genScript += 'probeType = 2\n'
                        elif currSetting.probeType == "H field":
                            genScript += 'probeType = 3\n'
                        else:
                            genScript += 'probeType = ?    #ERROR probe code generate don\'t know type\n'

                        argStr = ""
                        if not (bbCoords.XMin == bbCoords.XMax or bbCoords.YMin == bbCoords.YMax or bbCoords.ZMin == bbCoords.ZMax):
                            argStr += f", norm_dir=probeDirection"

                        if (currSetting.probeDomain == "frequency"):
                            argStr += f", frequency=["

                            if (len(currSetting.probeFrequencyList) > 0):
                                for freqStr in currSetting.probeFrequencyList:
                                    freqStr = freqStr.strip()
                                    result = re.search(r"([+,\,\-,.,0-9]+)([A-Za-z]+)$", freqStr)
                                    if result:
                                        freqValue = float(result.group(1))
                                        freqUnits = result.group(2)
                                        freqValue = freqValue * currSetting.getUnitsAsNumber(freqUnits)
                                        argStr += str(freqValue) + ","
                                argStr += "]"
                            else:
                                argStr += "f0]#{ERROR NO FREQUENCIES FOR PROBE FOUND, SO INSTEAD USED f0#}"
                                self.cadHelpers.printWarning(f"probe octave code generator error, no frequencies defined for '{probeName}', using f0 instead\n")

                        genScript += f"probeList[probeName] = CSX.AddProbe(probeName, probeType" + argStr + ")\n"
                        genScript += self.getCartesianOrCylindricalScriptLinesFromStartStop(bbCoords, "probeStart", "probeStop")
                        genScript += f"probeList[probeName].AddBox(probeStart, probeStop )\n"
                        genScript += "\n"
                        genProbeCounter += 1

                    elif (currSetting.getType() == "dumpbox"):
                        dumpboxName = f"{currSetting.name}_{childName}"
                        genScript += f'dumpboxName = "{dumpboxName}"\n'

                        dumpType = currSetting.getDumpType()
                        genScript += f'dumpboxType = {dumpType}\n'

                        argStr = ""
                        #
                        #   dump file type:
                        #       0 = vtk (default)
                        #       1 = hdf5
                        #
                        if (currSetting.dumpboxFileType == "hdf5"):
                            argStr += f", file_type=1"

                        emptyFrequencyListError = False
                        if (currSetting.dumpboxDomain == "frequency"):
                            argStr += ", frequency=["

                            if (len(currSetting.dumpboxFrequencyList) > 0):
                                for freqStr in currSetting.dumpboxFrequencyList:
                                    freqStr = freqStr.strip()
                                    result = re.search(r"([+,\,\-,.,0-9]+)([A-Za-z]+)$", freqStr)
                                    if result:
                                        freqValue = float(result.group(1))
                                        freqUnits = result.group(2)
                                        freqValue = freqValue * currSetting.getUnitsAsNumber(freqUnits)
                                        argStr += str(freqValue) + ","
                                argStr += "]"
                            else:
                                emptyFrequencyListError = True
                                argStr += "f0]"
                                self.cadHelpers.printWarning(f"dumpbox octave code generator error, no frequencies defined for '{dumpboxName}', using f0 instead\n")

                        #if error put note about it into script
                        if emptyFrequencyListError:
                            genScript += f"dumpBoxList[dumpboxName] = CSX.AddDump(dumpboxName, dump_type=dumpboxType" + argStr + ") # ERROR script generation no frequencies for dumpbox, therefore using f0\n"
                        else:
                            genScript += f"dumpBoxList[dumpboxName] = CSX.AddDump(dumpboxName, dump_type=dumpboxType" + argStr + ")\n"

                        genScript += self.getCartesianOrCylindricalScriptLinesFromStartStop(bbCoords, "dumpboxStart", "dumpboxStop")
                        genScript += f"dumpBoxList[dumpboxName].AddBox(dumpboxStart, dumpboxStop )\n"
                        genScript += "\n"
                        genDumpBoxCounter += 1

                    elif (currSetting.getType() == 'et dump'):
                        dumpboxName = f"{currSetting.name}_{childName}"
                        genScript += f'dumpboxName = "{dumpboxName}"\n'

                        genScript += f"dumpBoxList[dumpboxName] = CSX.AddDump(dumpboxName, dump_type=0, dump_mode=2)\n"
                        genScript += self.getCartesianOrCylindricalScriptLinesFromStartStop(bbCoords, "dumpboxStart", "dumpboxStop")
                        genScript += f"dumpBoxList[dumpboxName].AddBox(dumpboxStart, dumpboxStop)\n"
                        genDumpBoxCounter += 1

                    elif (currSetting.getType() == 'ht dump'):
                        dumpboxName = f"{currSetting.name}_{childName}"
                        genScript += f'dumpboxName = "{dumpboxName}"\n'

                        genScript += f"dumpBoxList[dumpboxName] = CSX.AddDump(dumpboxName, dumnp_type=1, dump_mode=2)\n"
                        genScript += self.getCartesianOrCylindricalScriptLinesFromStartStop(bbCoords, "dumpboxStart", "dumpboxStop")
                        genScript += f"dumpBoxList[dumpboxName].AddBox(dumpboxStart, dumpboxStop );\n"
                        genDumpBoxCounter += 1

                    elif (currSetting.getType() == 'nf2ff box'):
                        dumpboxName = f"{currSetting.name} - {childName}"
                        dumpboxName = dumpboxName.replace(" ", "_")
                        genScript += f'dumpboxName = "{dumpboxName}"\n'

                        genScript += self.getCartesianOrCylindricalScriptLinesFromStartStop(bbCoords, "nf2ffStart", "nf2ffStop")

                        # genScript += 'nf2ffUnit = ' + currSetting.getUnitAsScriptLine() + ';\n'
                        genScript += f"nf2ffBoxList[dumpboxName] = FDTD.CreateNF2FFBox(dumpboxName, nf2ffStart, nf2ffStop)\n"
                        # NF2FF grid lines are generated below via getNF2FFDefinitionsScriptLines()

                        #
                        #   ATTENTION this is NF2FF box counter
                        #
                        self.internalNF2FFIndexNamesList[dumpboxName] = genNF2FFBoxCounter
                        genNF2FFBoxCounter += 1

                    else:
                        genScript += '# Unknown port type. Nothing was generated. \n'

            genScript += "\n"

        return genScript

    def getLumpedPartDefinitionsScriptLines(self, items):
        genScript = ""
        if not items:
            return genScript

        refUnit = self.getUnitLengthFromUI_m()  # Coordinates need to be given in drawing units
        sf = self.getFreeCADUnitLength_m() / refUnit  # scaling factor for FreeCAD units to drawing units

        genScript += "#######################################################################################################################################\n"
        genScript += "# LUMPED PART\n"
        genScript += "#######################################################################################################################################\n"

        for [item, currentSetting] in items:
            genScript += "# LUMPED PARTS " + currentSetting.getName() + "\n"

            # traverse through all children item for this particular lumped part settings
            objs = self.cadHelpers.getObjects()
            objsExport = []
            for k in range(item.childCount()):
                childName = item.child(k).text(0)
                print("#LUMPED PART " + currentSetting.getType())

                freecadObjects = [i for i in objs if (i.Label) == childName]
                for obj in freecadObjects:
                    # obj = FreeCAD Object class

                    # BOUNDING BOX
                    bbCoords = obj.Shape.BoundBox

                    genScript += self.getCartesianOrCylindricalScriptLinesFromStartStop(bbCoords, "lumpedPartStart", "lumpedPartStop")

                    lumpedPartName = currentSetting.name
                    lumpedPartParams = ''
                    if ('r' in currentSetting.getType().lower()):
                        lumpedPartParams += ",R=" + str(currentSetting.getR())
                    if ('l' in currentSetting.getType().lower()):
                        lumpedPartParams += ",L=" + str(currentSetting.getL())
                    if ('c' in currentSetting.getType().lower()):
                        lumpedPartParams += ",C=" + str(currentSetting.getC())
                    lumpedPartParams = lumpedPartParams.strip(',')

                    #
                    #	getting item priority
                    #
                    priorityItemName = item.parent().text(0) + ", " + item.text(0) + ", " + childName
                    priorityIndex = self.getItemPriority(priorityItemName)

                    # WARNING: Caps param has hardwired value 1, will be generated small metal caps to connect part with circuit !!!
                    genScript += f"lumpedPart = CSX.AddLumpedElement('{lumpedPartName}', ny='z', caps=True{lumpedPartParams});\n"
                    genScript += f"lumpedPart.AddBox(lumpedPartStart, lumpedPartStop, priority={str(priorityIndex)});\n"

            genScript += "\n"

        return genScript

    def getNF2FFDefinitionsScriptLines(self, items):
        genScript = ""
        if not items:
            return genScript

        refUnit = self.getUnitLengthFromUI_m()  # Coordinates need to be given in drawing units
        sf = self.getFreeCADUnitLength_m() / refUnit  # scaling factor for FreeCAD units to drawing units
        nf2ff_gridlines = {'x': [], 'y': [], 'z': []}

        for [item, currSetting] in items:

            objs = self.cadHelpers.getObjects()
            for k in range(item.childCount()):
                childName = item.child(k).text(0)

                freecadObjects = [i for i in objs if (i.Label) == childName]

                # print(freecadObjects)
                for obj in freecadObjects:
                    # BOUNDING BOX
                    bbCoords = obj.Shape.BoundBox

                    if (currSetting.getType() == 'nf2ff box'):
                        nf2ff_gridlines['x'].append("{0:g}".format(_r(sf * bbCoords.XMin)))
                        nf2ff_gridlines['x'].append("{0:g}".format(_r(sf * bbCoords.XMax)))
                        nf2ff_gridlines['y'].append("{0:g}".format(_r(sf * bbCoords.YMin)))
                        nf2ff_gridlines['y'].append("{0:g}".format(_r(sf * bbCoords.YMax)))
                        nf2ff_gridlines['z'].append("{0:g}".format(_r(sf * bbCoords.ZMin)))
                        nf2ff_gridlines['z'].append("{0:g}".format(_r(sf * bbCoords.ZMax)))

        writeNF2FFlines = (len(nf2ff_gridlines['x']) > 0) or (len(nf2ff_gridlines['y']) > 0) or (
                    len(nf2ff_gridlines['z']) > 0)

        if writeNF2FFlines:
            genScript += "#######################################################################################################################################\n"
            genScript += "# NF2FF PROBES GRIDLINES\n"
            genScript += "#######################################################################################################################################\n"

            genScript += "mesh.x = np.array([])\n"
            genScript += "mesh.y = np.array([])\n"
            genScript += "mesh.z = np.array([])\n"

            if (len(nf2ff_gridlines['x']) > 0):
                genScript += "mesh.x = np.append(mesh.x, [" + ", ".join(str(i) for i in nf2ff_gridlines['x']) + "])\n"
            if (len(nf2ff_gridlines['y']) > 0):
                genScript += "mesh.y = np.append(mesh.y, [" + ", ".join(str(i) for i in nf2ff_gridlines['y']) + "])\n"
            if (len(nf2ff_gridlines['z']) > 0):
                genScript += "mesh.z = np.append(mesh.z, [" + ", ".join(str(i) for i in nf2ff_gridlines['z']) + "])\n"

            genScript += "openEMS_grid.AddLine('x', mesh.x)\n"
            genScript += "openEMS_grid.AddLine('y', mesh.y)\n"
            genScript += "openEMS_grid.AddLine('z', mesh.z)\n"
            genScript += "\n"

        return genScript

    def getOrderedGridDefinitionsScriptLines(self, items):
        genScript = ""
        meshPrioritiesCount = self.form.meshPriorityTreeView.topLevelItemCount()

        if (not items) or (meshPrioritiesCount == 0):
            return genScript

        refUnit = self.getUnitLengthFromUI_m()  # Coordinates need to be given in drawing units
        refUnitStr = self.form.simParamsDeltaUnitList.currentText()
        sf = self.getFreeCADUnitLength_m() / refUnit  # scaling factor for FreeCAD units to drawing units

        genScript += "#######################################################################################################################################\n"
        genScript += "# GRID LINES\n"
        genScript += "#######################################################################################################################################\n"
        genScript += "\n"

        # Create lists and dict to be able to resolve ordered list of (grid settings instance <-> FreeCAD object) associations.
        # In its current form, this implies user-defined grid lines have to be associated with the simulation volume.
        _assoc = lambda idx: list(map(str.strip, self.form.meshPriorityTreeView.topLevelItem(idx).text(0).split(',')))
        orderedAssociations = [_assoc(k) for k in reversed(range(meshPrioritiesCount))]
        gridSettingsNodeNames = [gridSettingsNode.text(0) for [gridSettingsNode, gridSettingsInst] in items]
        fcObjects = {obj.Label: obj for obj in self.cadHelpers.getObjects()}

        for gridSettingsNodeName in gridSettingsNodeNames:
            print("Grid type : " + gridSettingsNodeName)

        for k, [categoryName, gridName, FreeCADObjectName] in enumerate(orderedAssociations):

            print("Grid priority level {} : {} :: {}".format(k, FreeCADObjectName, gridName))

            if not (gridName in gridSettingsNodeNames):
                print("Failed to resolve '{}'.".format(gridName))
                continue
            itemListIdx = gridSettingsNodeNames.index(gridName)

            #GridSettingsItem object from GUI
            gridSettingsInst = items[itemListIdx][1]

            #Grid category object from GUI
            gridCategoryObj = items[itemListIdx][0]

            #
            #   Fixed Distance, Fixed Count mesh boundaries coords obtain
            #
            if (gridSettingsInst.getType() in ['Fixed Distance', 'Fixed Count']):
                fcObject = fcObjects.get(FreeCADObjectName, None)
                if (not fcObject):
                    print("Failed to resolve '{}'.".format(FreeCADObjectName))
                    continue

                ### Produce script output.

                if (not "Shape" in dir(fcObject)):
                    continue

                bbCoords = fcObject.Shape.BoundBox

                # If generateLinesInside is selected, grid line region is shifted inward by lambda/20.
                if gridSettingsInst.generateLinesInside:
                    delta = self.maxGridResolution_m * sf * 0.001   #LuboJ, added multiply by 0.001 because still lambda/20 for 4GHz is 3.75mm too much
                    print("GRID generateLinesInside object detected, setting correction constant to " + str(delta) + "m (meters)")
                else:
                    delta = 0

                xmax = sf * bbCoords.XMax - np.sign(bbCoords.XMax - bbCoords.XMin) * delta
                ymax = sf * bbCoords.YMax - np.sign(bbCoords.YMax - bbCoords.YMin) * delta
                zmax = sf * bbCoords.ZMax - np.sign(bbCoords.ZMax - bbCoords.ZMin) * delta
                xmin = sf * bbCoords.XMin + np.sign(bbCoords.XMax - bbCoords.XMin) * delta
                ymin = sf * bbCoords.YMin + np.sign(bbCoords.YMax - bbCoords.YMin) * delta
                zmin = sf * bbCoords.ZMin + np.sign(bbCoords.ZMax - bbCoords.ZMin) * delta

                # Write grid definition.
                genScript += "## GRID - " + gridSettingsInst.getName() + " - " + FreeCADObjectName + ' (' + gridSettingsInst.getType() + ")\n"

            #
            #   Smooth Mesh boundaries coords obtain
            #
            elif (gridSettingsInst.getType() == "Smooth Mesh"):

                xList = []
                yList = []
                zList = []

                #iterate over grid smooth mesh category freecad children
                for k in range(gridCategoryObj.childCount()):
                    FreeCADObjectName = gridCategoryObj.child(k).text(0)

                    fcObject = fcObjects.get(FreeCADObjectName, None)
                    if (not fcObject):
                        print("Smooth Mesh - Failed to resolve '{}'.".format(FreeCADObjectName))
                        continue

                    ### Produce script output.

                    if (not "Shape" in dir(fcObject)):
                        continue

                    bbCoords = fcObject.Shape.BoundBox

                    # If generateLinesInside is selected, grid line region is shifted inward by lambda/20.
                    if gridSettingsInst.generateLinesInside:
                        delta = self.maxGridResolution_m * sf * 0.001  # LuboJ, added multiply by 0.001 because still lambda/20 for 4GHz is 3.75mm too much
                        print("GRID generateLinesInside object detected, setting correction constant to " + str(delta) + "m (meters)")
                    else:
                        delta = 0

                    #append boundary coordinates into list
                    xList.append(sf * bbCoords.XMax - np.sign(bbCoords.XMax - bbCoords.XMin) * delta)
                    yList.append(sf * bbCoords.YMax - np.sign(bbCoords.YMax - bbCoords.YMin) * delta)
                    zList.append(sf * bbCoords.ZMax - np.sign(bbCoords.ZMax - bbCoords.ZMin) * delta)
                    xList.append(sf * bbCoords.XMin + np.sign(bbCoords.XMax - bbCoords.XMin) * delta)
                    yList.append(sf * bbCoords.YMin + np.sign(bbCoords.YMax - bbCoords.YMin) * delta)
                    zList.append(sf * bbCoords.ZMin + np.sign(bbCoords.ZMax - bbCoords.ZMin) * delta)

                    # Write grid definition.
                    genScript += "## GRID - " + gridSettingsInst.getName() + " - " + FreeCADObjectName + ' (' + gridSettingsInst.getType() + ")\n"

                #order from min -> max coordinates in each list
                xList.sort()
                yList.sort()
                zList.sort()

            #
            #   Real octave mesh lines code generate starts here
            #

            #in case of cylindrical coordinates convert xyz to theta,r,z
            if (gridSettingsInst.coordsType == "cylindrical"):
                #FROM GUI ARE GOING DEGREES

                #
                #   Here calculate right r, theta, z from boundaries of object, it depends if origin lays inside boundaries or where object is positioned.
                #
                xmin, xmax, ymin, ymax, zmin, zmax = gridSettingsInst.getCartesianAsCylindricalCoords(bbCoords, xmin, xmax, ymin, ymax, zmin, zmax)

                if (gridSettingsInst.getType() == 'Smooth Mesh' and gridSettingsInst.unitsAngle == "deg"):
                    yParam = math.radians(gridSettingsInst.smoothMesh['yMaxRes'])
                elif (gridSettingsInst.getType() == 'Fixed Distance' and gridSettingsInst.unitsAngle == "deg"):
                    yParam = math.radians(gridSettingsInst.getXYZ(refUnit)['y'])
                elif (gridSettingsInst.getType() == 'User Defined'):
                    pass  # user defined is jaust text, doesn't have ['y']
                else:
                    yParam = gridSettingsInst.getXYZ(refUnit)['y']

                #z coordinate stays as was

            else:
                if (gridSettingsInst.getType() == 'Smooth Mesh'):
                    yParam = gridSettingsInst.smoothMesh['yMaxRes']
                elif (gridSettingsInst.getType() == 'User Defined'):
                    pass                                                #user defined is just text, doesn't have ['y']
                else:
                    yParam = gridSettingsInst.getXYZ(refUnit)['y']

            if (gridSettingsInst.getType() == 'Fixed Distance'):
                if gridSettingsInst.xenabled:
                    if gridSettingsInst.topPriorityLines:
                        genScript += "mesh.x = np.delete(mesh.x, np.argwhere((mesh.x >= {0:g}) & (mesh.x <= {1:g})))\n".format(_r(xmin), _r(xmax))
                    genScript += "mesh.x = np.concatenate((mesh.x, np.arange({0:g},{1:g},{2:g})))\n".format(_r(xmin), _r(xmax), _r(gridSettingsInst.getXYZ(refUnit)['x']))
                if gridSettingsInst.yenabled:
                    if gridSettingsInst.topPriorityLines:
                        genScript += "mesh.y = np.delete(mesh.y, np.argwhere((mesh.y >= {0:g}) & (mesh.y <= {1:g})))\n".format(_r(ymin), _r(ymax))
                    genScript += "mesh.y = np.concatenate((mesh.y, np.arange({0:g},{1:g},{2:g})))\n".format(_r(ymin),_r(ymax),_r(yParam))
                if gridSettingsInst.zenabled:
                    if gridSettingsInst.topPriorityLines:
                        genScript += "mesh.z = np.delete(mesh.z, np.argwhere((mesh.z >= {0:g}) & (mesh.z <= {1:g})))\n".format(_r(zmin), _r(zmax))
                    genScript += "mesh.z = np.concatenate((mesh.z, np.arange({0:g},{1:g},{2:g})))\n".format(_r(zmin),_r(zmax),_r(gridSettingsInst.getXYZ(refUnit)['z']))

            elif (gridSettingsInst.getType() == 'Fixed Count'):
                if gridSettingsInst.xenabled:
                    if gridSettingsInst.topPriorityLines:
                        genScript += "mesh.x = np.delete(mesh.x, np.argwhere((mesh.x >= {0:g}) & (mesh.x <= {1:g})))\n".format(_r(xmin), _r(xmax))
                    if (not gridSettingsInst.getXYZ()['x'] == 1):
                        genScript += "mesh.x = np.concatenate((mesh.x, linspace({0:g},{1:g},{2:g})))\n".format(_r(xmin), _r(xmax), _r(gridSettingsInst.getXYZ(refUnit)['x']))
                    else:
                        genScript += "mesh.x = np.append(mesh.x, {0:g})\n".format(_r((xmin + xmax) / 2))

                if gridSettingsInst.yenabled:
                    if gridSettingsInst.topPriorityLines:
                        genScript += "mesh.y = np.delete(mesh.y, np.argwhere((mesh.y >= {0:g}) & (mesh.y <= {1:g})))\n".format(_r(ymin), _r(ymax))
                    if (not gridSettingsInst.getXYZ()['y'] == 1):
                        genScript += "mesh.y = np.concatenate((mesh.y, linspace({0:g},{1:g},{2:g})))\n".format(_r(ymin), _r(ymax), _r(yParam))
                    else:
                        genScript += "mesh.y = np.append(mesh.y, {0:g})\n".format(_r((ymin + ymax) / 2))

                if gridSettingsInst.zenabled:
                    if gridSettingsInst.topPriorityLines:
                        genScript += "mesh.z = np.delete(mesh.z, np.argwhere((mesh.z >= {0:g}) & (mesh.z <= {1:g})))\n".format(_r(zmin), _r(zmax))
                    if (not gridSettingsInst.getXYZ()['z'] == 1):
                        genScript += "mesh.z = np.concatenate((mesh.z, linspace({0:g},{1:g},{2:g})))\n".format(_r(zmin), _r(zmax), _r(gridSettingsInst.getXYZ(refUnit)['z']))
                    else:
                        genScript += "mesh.z = np.append(mesh.z, {0:g})\n".format(_r((zmin + zmax) / 2))

            elif (gridSettingsInst.getType() == 'User Defined'):
                if gridSettingsInst.xenabled:
                    if gridSettingsInst.topPriorityLines:
                        genScript += "mesh.x = np.delete(mesh.x, np.argwhere((mesh.x >= {0:g}) & (mesh.x <= {1:g})))\n".format(_r(xmin), _r(xmax))
                if gridSettingsInst.yenabled:
                    if gridSettingsInst.topPriorityLines:
                        genScript += "mesh.y = np.delete(mesh.y, np.argwhere((mesh.y >= {0:g}) & (mesh.y <= {1:g})))\n".format(_r(ymin), _r(ymax))
                if gridSettingsInst.zenabled:
                    if gridSettingsInst.topPriorityLines:
                        genScript += "mesh.z = np.delete(mesh.z, np.argwhere((mesh.z >= {0:g}) & (mesh.z <= {1:g})))\n".format(_r(zmin), _r(zmax))

                genScript += "xmin = {0:g}\n".format(_r(xmin))
                genScript += "xmax = {0:g}\n".format(_r(xmax))
                genScript += "ymin = {0:g}\n".format(_r(ymin))
                genScript += "ymax = {0:g}\n".format(_r(ymax))
                genScript += "zmin = {0:g}\n".format(_r(zmin))
                genScript += "zmax = {0:g}\n".format(_r(zmax))
                genScript += gridSettingsInst.getXYZ() + "\n"

            elif (gridSettingsInst.getType() == 'Smooth Mesh'):
                genScript += "smoothMesh = {}\n"
                if gridSettingsInst.xenabled:

                    #when top priority lines setting set, remove lines between min and max in ax direction
                    if gridSettingsInst.topPriorityLines:
                        genScript += "mesh.x = np.delete(mesh.x, np.argwhere((mesh.x >= {0:g}) & (mesh.x <= {1:g})))\n".format(_r(xList[0]), _r(xList[-1]))

                    genScript += f"smoothMesh.x = {str(xList)};\n"
                    if gridSettingsInst.smoothMesh['xMaxRes'] == 0:
                        genScript += "smoothMesh.x = CSXCAD.SmoothMeshLines.SmoothMeshLines(smoothMesh.x, max_res/unit) #max_res calculated in excitation part\n"
                    else:
                        genScript += f"smoothMesh.x = CSXCAD.SmoothMeshLines.SmoothMeshLines(smoothMesh.x, {gridSettingsInst.smoothMesh['xMaxRes']})\n"
                    genScript += "mesh.x = np.concatenate((mesh.x, smoothMesh.x))\n"
                if gridSettingsInst.yenabled:

                    #when top priority lines setting set, remove lines between min and max in ax direction
                    if gridSettingsInst.topPriorityLines:
                        genScript += "mesh.y = np.delete(mesh.y, np.argwhere((mesh.y >= {0:g}) & (mesh.y <= {1:g})))\n".format(_r(yList[0]), _r(yList[-1]))

                    genScript += f"smoothMesh.y = {str(yList)};\n"
                    if gridSettingsInst.smoothMesh['yMaxRes'] == 0:
                        genScript += "smoothMesh.y = CSXCAD.SmoothMeshLines.SmoothMeshLines(smoothMesh.y, max_res/unit) #max_res calculated in excitation part\n"
                    else:
                        genScript += f"smoothMesh.y = CSXCAD.SmoothMeshLines.SmoothMeshLines(smoothMesh.y, {yParam})\n"
                    genScript += "mesh.y = np.concatenate((mesh.y, smoothMesh.y))\n"
                if gridSettingsInst.zenabled:

                    #when top priority lines setting set, remove lines between min and max in ax direction
                    if gridSettingsInst.topPriorityLines:
                        genScript += "mesh.z = np.delete(mesh.z, np.argwhere((mesh.z >= {0:g}) & (mesh.z <= {1:g})))\n".format(_r(zList[0]), _r(zList[-1]))

                    genScript += f"smoothMesh.z = {str(zList)};\n"
                    if gridSettingsInst.smoothMesh['zMaxRes'] == 0:
                        genScript += "smoothMesh.z = CSXCAD.SmoothMeshLines.SmoothMeshLines(smoothMesh.z, max_res/unit) #max_res calculated in excitation part\n"
                    else:
                        genScript += f"smoothMesh.z = CSXCAD.SmoothMeshLines.SmoothMeshLines(smoothMesh.z, {gridSettingsInst.smoothMesh['zMaxRes']})\n"
                    genScript += "mesh.z = np.concatenate((mesh.z, smoothMesh.z))\n"

            genScript += "\n"

        genScript += "openEMS_grid.AddLine('x', mesh.x)\n"
        genScript += "openEMS_grid.AddLine('y', mesh.y)\n"
        genScript += "openEMS_grid.AddLine('z', mesh.z)\n"
        genScript += "\n"

        return genScript

    def getOrderedGridDefinitionsScriptLines_old_01(self, items):
        genScript = ""
        meshPrioritiesCount = self.form.meshPriorityTreeView.topLevelItemCount()

        if (not items) or (meshPrioritiesCount == 0):
            return genScript

        refUnit = self.getUnitLengthFromUI_m()  # Coordinates need to be given in drawing units
        refUnitStr = self.form.simParamsDeltaUnitList.currentText()
        sf = self.getFreeCADUnitLength_m() / refUnit  # scaling factor for FreeCAD units to drawing units

        genScript += "#######################################################################################################################################\n"
        genScript += "# GRID LINES\n"
        genScript += "#######################################################################################################################################\n"
        genScript += "\n"

        # Create lists and dict to be able to resolve ordered list of (grid settings instance <-> FreeCAD object) associations.
        # In its current form, this implies user-defined grid lines have to be associated with the simulation volume.
        _assoc = lambda idx: list(map(str.strip, self.form.meshPriorityTreeView.topLevelItem(idx).text(0).split(',')))
        orderedAssociations = [_assoc(k) for k in reversed(range(meshPrioritiesCount))]
        gridSettingsNodeNames = [gridSettingsNode.text(0) for [gridSettingsNode, gridSettingsInst] in items]
        fcObjects = {obj.Label: obj for obj in self.cadHelpers.getObjects()}

        for gridSettingsNodeName in gridSettingsNodeNames:
            print("Grid type : " + gridSettingsNodeName)

        for k, [categoryName, gridName, FreeCADObjectName] in enumerate(orderedAssociations):

            print("Grid priority level {} : {} :: {}".format(k, FreeCADObjectName, gridName))

            if not (gridName in gridSettingsNodeNames):
                print("Failed to resolve '{}'.".format(gridName))
                continue
            itemListIdx = gridSettingsNodeNames.index(gridName)
            gridSettingsInst = items[itemListIdx][1]

            fcObject = fcObjects.get(FreeCADObjectName, None)
            if (not fcObject):
                print("Failed to resolve '{}'.".format(FreeCADObjectName))
                continue

            ### Produce script output.

            if (not "Shape" in dir(fcObject)):
                continue

            bbCoords = fcObject.Shape.BoundBox

            # If generateLinesInside is selected, grid line region is shifted inward by lambda/20.
            if gridSettingsInst.generateLinesInside:
                delta = self.maxGridResolution_m / refUnit
                print("GRID generateLinesInside object detected, setting correction constant to " + str(
                    delta) + " " + refUnitStr)
            else:
                delta = 0

            #
            #	THIS IS HARD WIRED HERE, NEED TO BE CHANGED, LuboJ, September 2022
            #
            # DEBUG - DISABLED - generate grid inside using 1/20 of maximum lambda, it's not that equation,
            #	ie. for 3.4GHz simulation 1/20th is 4mm what is wrong for delta to generate
            #	gridlines inside object, must be much much lower like 10times
            delta = 0
            debugHardLimit = 0.1e-3  # debug hard limit to get gridlines inside STL objects

            xmax = sf * bbCoords.XMax - np.sign(bbCoords.XMax - bbCoords.XMin) * delta - debugHardLimit
            ymax = sf * bbCoords.YMax - np.sign(bbCoords.YMax - bbCoords.YMin) * delta - debugHardLimit
            zmax = sf * bbCoords.ZMax - np.sign(bbCoords.ZMax - bbCoords.ZMin) * delta - debugHardLimit
            xmin = sf * bbCoords.XMin + np.sign(bbCoords.XMax - bbCoords.XMin) * delta + debugHardLimit
            ymin = sf * bbCoords.YMin + np.sign(bbCoords.YMax - bbCoords.YMin) * delta + debugHardLimit
            zmin = sf * bbCoords.ZMin + np.sign(bbCoords.ZMax - bbCoords.ZMin) * delta + debugHardLimit

            # Write grid definition.

            genScript += "## GRID - " + gridSettingsInst.getName() + " - " + FreeCADObjectName + ' (' + gridSettingsInst.getType() + ")\n"

            if (gridSettingsInst.getType() == 'Fixed Distance'):
                if gridSettingsInst.xenabled:
                    if gridSettingsInst.topPriorityLines:
                        genScript += "mesh.x = np.delete(mesh.x, np.argwhere((mesh.x >= {0:g}) & (mesh.x <= {1:g})))\n".format(_r(xmin), _r(xmax))
                    genScript += "mesh.x = np.concatenate((mesh.x, np.arange({0:g},{1:g},{2:g})))\n".format(_r(xmin), _r(xmax), _r(gridSettingsInst.getXYZ(refUnit)['x']))
                if gridSettingsInst.yenabled:
                    if gridSettingsInst.topPriorityLines:
                        genScript += "mesh.y = np.delete(mesh.y, np.argwhere((mesh.y >= {0:g}) & (mesh.y <= {1:g})))\n".format(_r(ymin), _r(ymax))
                    genScript += "mesh.y = np.concatenate((mesh.y, np.arange({0:g},{1:g},{2:g})))\n".format(_r(ymin),_r(ymax),_r(gridSettingsInst.getXYZ(refUnit)['y']))
                if gridSettingsInst.zenabled:
                    if gridSettingsInst.topPriorityLines:
                        genScript += "mesh.z = np.delete(mesh.z, np.argwhere((mesh.z >= {0:g}) & (mesh.z <= {1:g})))\n".format(_r(zmin), _r(zmax))
                    genScript += "mesh.z = np.concatenate((mesh.z, np.arange({0:g},{1:g},{2:g})))\n".format(_r(zmin),_r(zmax),_r(gridSettingsInst.getXYZ(refUnit)['z']))

            elif (gridSettingsInst.getType() == 'Fixed Count'):
                if gridSettingsInst.xenabled:
                    if gridSettingsInst.topPriorityLines:
                        genScript += "mesh.x = np.delete(mesh.x, np.argwhere((mesh.x >= {0:g}) & (mesh.x <= {1:g})))\n".format(_r(xmin), _r(xmax))
                    if (not gridSettingsInst.getXYZ()['x'] == 1):
                        genScript += "mesh.x = np.concatenate((mesh.x, linspace({0:g},{1:g},{2:g})))\n".format(_r(xmin), _r(xmax), _r(gridSettingsInst.getXYZ(refUnit)['x']))
                    else:
                        genScript += "mesh.x = np.append(mesh.x, {0:g})\n".format(_r((xmin + xmax) / 2))

                if gridSettingsInst.yenabled:
                    if gridSettingsInst.topPriorityLines:
                        genScript += "mesh.y = np.delete(mesh.y, np.argwhere((mesh.y >= {0:g}) & (mesh.y <= {1:g})))\n".format(_r(ymin), _r(ymax))
                    if (not gridSettingsInst.getXYZ()['y'] == 1):
                        genScript += "mesh.y = np.concatenate((mesh.y, linspace({0:g},{1:g},{2:g})))\n".format(_r(ymin), _r(ymax), _r(
                            gridSettingsInst.getXYZ(refUnit)['y']))
                    else:
                        genScript += "mesh.y = np.append(mesh.y, {0:g})\n".format(_r((ymin + ymax) / 2))

                if gridSettingsInst.zenabled:
                    if gridSettingsInst.topPriorityLines:
                        genScript += "mesh.z = np.delete(mesh.z, np.argwhere((mesh.z >= {0:g}) & (mesh.z <= {1:g})))\n".format(_r(zmin), _r(zmax))
                    if (not gridSettingsInst.getXYZ()['z'] == 1):
                        genScript += "mesh.z = np.concatenate((mesh.z, linspace({0:g},{1:g},{2:g})))\n".format(_r(zmin), _r(zmax), _r(
                            gridSettingsInst.getXYZ(refUnit)['z']))
                    else:
                        genScript += "mesh.z = np.append(mesh.z, {0:g})\n".format(_r((zmin + zmax) / 2))

            elif (gridSettingsInst.getType() == 'User Defined'):
                genScript += "mesh = " + gridSettingsInst.getXYZ() + ";\n"

            genScript += "\n"

        genScript += "openEMS_grid.AddLine('x', mesh.x)\n"
        genScript += "openEMS_grid.AddLine('y', mesh.y)\n"
        genScript += "openEMS_grid.AddLine('z', mesh.z)\n"
        genScript += "\n"

        return genScript


    def getInitScriptLines(self):
        genScript = ""
        genScript += "# To be run with python.\n"
        genScript += "# FreeCAD to OpenEMS plugin by Lubomir Jagos, \n"
        genScript += "# see https://github.com/LubomirJagos/FreeCAD-OpenEMS-Export\n"
        genScript += "#\n"
        genScript += "# This file has been automatically generated. Manual changes may be overwritten.\n"
        genScript += "#\n"
        genScript += "### Import Libraries\n"
        genScript += "import math\n"
        genScript += "import numpy as np\n"
        genScript += "import os, tempfile, shutil\n"
        genScript += "from pylab import *\n"
        genScript += "import CSXCAD\n"
        genScript += "from openEMS import openEMS\n"
        genScript += "from openEMS.physical_constants import *\n"
        genScript += "\n"

        genScript += "#\n"
        genScript += "# FUNCTION TO CONVERT CARTESIAN TO CYLINDRICAL COORDINATES\n"
        genScript += "#     returns coordinates in order [theta, r, z]\n"
        genScript += "#\n"
        genScript += "def cart2pol(pointCoords):\n"
        genScript += "\ttheta = np.arctan2(pointCoords[1], pointCoords[0])\n"
        genScript += "\tr = np.sqrt(pointCoords[0] ** 2 + pointCoords[1] ** 2)\n"
        genScript += "\tz = pointCoords[2]\n"
        genScript += "\treturn theta, r, z\n"
        genScript += "\n"

        genScript += "# Change current path to script file folder\n"
        genScript += "#\n"
        genScript += "abspath = os.path.abspath(__file__)\n"
        genScript += "dname = os.path.dirname(abspath)\n"
        genScript += "os.chdir(dname)\n"

        genScript += "## constants\n"
        genScript += "unit    = " + str(
            self.getUnitLengthFromUI_m()) + " # Model coordinates and lengths will be specified in " + self.form.simParamsDeltaUnitList.currentText() + ".\n"
        genScript += "fc_unit = " + str(
            self.getFreeCADUnitLength_m()) + " # STL files are exported in FreeCAD standard units (mm).\n"
        genScript += "\n"

        return genScript

    def getExcitationScriptLines(self, definitionsOnly=False):
        genScript = ""

        excitationCategory = self.form.objectAssignmentRightTreeWidget.findItems("Excitation",
                                                                                 QtCore.Qt.MatchFixedString)
        if len(excitationCategory) >= 0:
            print("Excitation Settings detected")
            print("#")
            print("#EXCITATION")

            # FOR WHOLE SIMULATION THERE IS JUST ONE EXCITATION DEFINED, so first is taken!
            if (excitationCategory[0].childCount() > 0):
                item = excitationCategory[0].child(0)
                currSetting = item.data(0, QtCore.Qt.UserRole)  # At index 0 is Default Excitation.
                # Currently only 1 excitation is allowed. Multiple excitations could be managed by setting one of them as "selected" or "active", while all others are deactivated.
                # This would help the user to manage different analysis scenarios / excitation ranges.

                print("#name: " + currSetting.getName())
                print("#type: " + currSetting.getType())

                genScript += "#######################################################################################################################################\n"
                genScript += "# EXCITATION " + currSetting.getName() + "\n"
                genScript += "#######################################################################################################################################\n"

                # EXCITATION FREQUENCY AND CELL MAXIMUM RESOLUTION CALCULATION (1/20th of minimal lambda - calculated based on maximum simulation frequency)
                # maximum grid resolution is generated into script but NOT USED IN OCTAVE SCRIPT, instead is also calculated here into python variable and used in bounding box correction
                if (currSetting.getType() == 'sinusodial'):
                    genScript += "f0 = " + str(currSetting.sinusodial['f0']) + "*" + str(
                        currSetting.getUnitsAsNumber(currSetting.units)) + "\n"
                    if not definitionsOnly:
                        genScript += "FDTD.SetSinusExcite(fc);\n"
                    genScript += "max_res = C0 / f0 / 20\n"
                    self.maxGridResolution_m = 3e8 / (
                                currSetting.sinusodial['f0'] * currSetting.getUnitsAsNumber(currSetting.units) * 20)
                    pass
                elif (currSetting.getType() == 'gaussian'):
                    genScript += "f0 = " + str(currSetting.gaussian['f0']) + "*" + str(
                        currSetting.getUnitsAsNumber(currSetting.units)) + "\n"
                    genScript += "fc = " + str(currSetting.gaussian['fc']) + "*" + str(
                        currSetting.getUnitsAsNumber(currSetting.units)) + "\n"
                    if not definitionsOnly:
                        genScript += "FDTD.SetGaussExcite(f0, fc)\n"
                    genScript += "max_res = C0 / (f0 + fc) / 20\n"
                    self.maxGridResolution_m = 3e8 / ((currSetting.gaussian['f0'] + currSetting.gaussian[
                        'fc']) * currSetting.getUnitsAsNumber(currSetting.units) * 20)
                    pass
                elif (currSetting.getType() == 'custom'):
                    f0 = currSetting.custom['f0'] * currSetting.getUnitsAsNumber(currSetting.units)
                    genScript += "f0 = " + str(currSetting.custom['f0']) + "*" + str(
                        currSetting.getUnitsAsNumber(currSetting.units)) + "\n"
                    genScript += "fc = 0.0;\n"
                    if not definitionsOnly:
                        genScript += "FDTD.SetCustomExcite(f0, '" + currSetting.custom['functionStr'].replace(
                            'f0', str(f0)) + "' )\n"
                    genScript += "max_res = 0\n"
                    self.maxGridResolution_m = 0
                    pass
                pass

                genScript += "\n"
            else:
                self.guiHelpers.displayMessage("Missing excitation, please define one.")
                pass
            pass
        return genScript

    def getBoundaryConditionsScriptLines(self):
        genScript = ""

        genScript += "#######################################################################################################################################\n"
        genScript += "# BOUNDARY CONDITIONS\n"
        genScript += "#######################################################################################################################################\n"

        _bcStr = lambda pml_val, text: '\"PML_{}\"'.format(str(pml_val)) if text == 'PML' else '\"{}\"'.format(text)
        strBC = ""
        strBC += _bcStr(self.form.PMLxmincells.value(), self.form.BCxmin.currentText()) + ","
        strBC += _bcStr(self.form.PMLxmaxcells.value(), self.form.BCxmax.currentText()) + ","
        strBC += _bcStr(self.form.PMLymincells.value(), self.form.BCymin.currentText()) + ","
        strBC += _bcStr(self.form.PMLymaxcells.value(), self.form.BCymax.currentText()) + ","
        strBC += _bcStr(self.form.PMLzmincells.value(), self.form.BCzmin.currentText()) + ","
        strBC += _bcStr(self.form.PMLzmaxcells.value(), self.form.BCzmax.currentText())

        genScript += "BC = [" + strBC + "]\n"
        genScript += "FDTD.SetBoundaryCond(BC)\n"
        genScript += "\n"

        return genScript

    def getMinimalGridlineSpacingScriptLines(self):
        genScript = ""

        if (self.form.genParamMinGridSpacingEnable.isChecked()):
            minSpacingX = self.form.genParamMinGridSpacingX.value() / 1000 / self.getUnitLengthFromUI_m()
            minSpacingY = self.form.genParamMinGridSpacingY.value() / 1000 / self.getUnitLengthFromUI_m()
            minSpacingZ = self.form.genParamMinGridSpacingZ.value() / 1000 / self.getUnitLengthFromUI_m()

            genScript += "#######################################################################################################################################\n"
            genScript += "# MINIMAL GRIDLINES SPACING, removing gridlines which are closer as defined in GUI\n"
            genScript += "#######################################################################################################################################\n"
            genScript += 'mesh.x = openEMS_grid.GetLines("x", True)\n'
            genScript += 'mesh.y = openEMS_grid.GetLines("y", True)\n'
            genScript += 'mesh.z = openEMS_grid.GetLines("z", True)\n'
            genScript += '\n'
            genScript += 'openEMS_grid.ClearLines("x")\n'
            genScript += 'openEMS_grid.ClearLines("y")\n'
            genScript += 'openEMS_grid.ClearLines("z")\n'
            genScript += '\n'
            genScript += 'for k in range(len(mesh.x)-1):\n'
            genScript += '\tif (not np.isinf(mesh.x[k]) and abs(mesh.x[k+1]-mesh.x[k]) <= ' + str(minSpacingX) + '):\n'
            genScript += '\t\tprint("Removnig line at x: " + str(mesh.x[k+1]))\n'
            genScript += '\t\tmesh.x[k+1] = np.inf\n'
            genScript += '\n'
            genScript += 'for k in range(len(mesh.y)-1):\n'
            genScript += '\tif (not np.isinf(mesh.y[k]) and abs(mesh.y[k+1]-mesh.y[k]) <= ' + str(minSpacingY) + '):\n'
            genScript += '\t\tprint("Removnig line at y: " + str(mesh.y[k+1]))\n'
            genScript += '\t\tmesh.y[k+1] = np.inf\n'
            genScript += '\n'
            genScript += 'for k in range(len(mesh.z)-1):\n'
            genScript += '\tif (not np.isinf(mesh.z[k]) and abs(mesh.z[k+1]-mesh.z[k]) <= ' + str(minSpacingZ) + '):\n'
            genScript += '\t\tprint("Removnig line at z: " + str(mesh.z[k+1]))\n'
            genScript += '\t\tmesh.z[k+1] = np.inf\n'
            genScript += '\n'

            genScript += 'mesh.x = mesh.x[~np.isinf(mesh.x)]\n'
            genScript += 'mesh.y = mesh.y[~np.isinf(mesh.y)]\n'
            genScript += 'mesh.z = mesh.z[~np.isinf(mesh.z)]\n'
            genScript += '\n'

            genScript += "openEMS_grid.AddLine('x', mesh.x)\n"
            genScript += "openEMS_grid.AddLine('y', mesh.y)\n"
            genScript += "openEMS_grid.AddLine('z', mesh.z)\n"
            genScript += '\n'

        return genScript

    #########################################################################################################################
    #                                  _                       _       _          _ _      _            _
    #                                 | |                     (_)     | |        | (_)    | |          | |
    #   __ _  ___ _ __   ___ _ __ __ _| |_ ___   ___  ___ _ __ _ _ __ | |_    ___| |_  ___| | _____  __| |
    #  / _` |/ _ \ '_ \ / _ \ '__/ _` | __/ _ \ / __|/ __| '__| | '_ \| __|  / __| | |/ __| |/ / _ \/ _` |
    # | (_| |  __/ | | |  __/ | | (_| | ||  __/ \__ \ (__| |  | | |_) | |_  | (__| | | (__|   <  __/ (_| |
    #  \__, |\___|_| |_|\___|_|  \__,_|\__\___| |___/\___|_|  |_| .__/ \__|  \___|_|_|\___|_|\_\___|\__,_|
    #   __/ |                                                   | |
    #  |___/
    #
    #	GENERATE SCRIPT CLICKED - go through object assignment tree categories, output child item data.
    #
    def generateOpenEMSScript(self, outputDir=None):

        # Create outputDir relative to local FreeCAD file if output dir does not exists
        #   if outputDir is set to same value
        #   if outputStr is None then folder with name as FreeCAD file with suffix _openEMS_simulation is created
        outputDir = self.createOuputDir(outputDir)

        # Update status bar to inform user that exporting has begun.
        if self.statusBar is not None:
            self.statusBar.showMessage("Generating OpenEMS script and geometry files ...", 5000)
            QtWidgets.QApplication.processEvents()

        # Constants and variable initialization.

        refUnit = self.getUnitLengthFromUI_m()  # Coordinates need to be given in drawing units
        refUnitStr = self.form.simParamsDeltaUnitList.currentText()
        sf = self.getFreeCADUnitLength_m() / refUnit  # scaling factor for FreeCAD units to drawing units

        # List categories and items.

        itemsByClassName = self.getItemsByClassName()

        # Write script header.

        genScript = ""

        genScript += "# OpenEMS FDTD Analysis Automation Script\n"
        genScript += "#\n"

        genScript += self.getInitScriptLines()

        genScript += "## switches & options\n"
        genScript += "draw_3d_pattern = 0  # this may take a while...\n"
        genScript += "use_pml = 0          # use pml boundaries instead of mur\n"
        genScript += "\n"
        genScript += "currDir = os.getcwd()\n"
        genScript += "print(currDir)\n"
        genScript += "\n"

        genScript += "# setup_only : dry run to view geometry, validate settings, no FDTD computations\n"
        genScript += "# debug_pec  : generated PEC skeleton (use ParaView to inspect)\n"
        genScript += f"debug_pec = {'True' if self.form.generateDebugPECCheckbox.isChecked() else 'False'}\n"
        genScript += f"setup_only = {'True' if self.form.generateJustPreviewCheckbox.isChecked() else 'False'}\n"
        genScript += "\n"

        # Write simulation settings.

        genScript += "## prepare simulation folder\n"
        genScript += "Sim_Path = os.path.join(currDir, 'simulation_output')\n"
        genScript += "Sim_CSX = '" + os.path.splitext(os.path.basename(self.cadHelpers.getCurrDocumentFileName()))[0] + ".xml'\n"

        genScript += "if os.path.exists(Sim_Path):\n"
        genScript += "\tshutil.rmtree(Sim_Path)   # clear previous directory\n"
        genScript += "\tos.mkdir(Sim_Path)    # create empty simulation folder\n"
        genScript += "\n"

        genScript += "## setup FDTD parameter & excitation function\n"
        genScript += "max_timesteps = " + str(self.form.simParamsMaxTimesteps.value()) + "\n"
        genScript += "min_decrement = " + str(self.form.simParamsMinDecrement.value()) + " # 10*log10(min_decrement) dB  (i.e. 1E-5 means -50 dB)\n"

        if (self.getModelCoordsType() == "cylindrical"):
            genScript += "CSX = CSXCAD.ContinuousStructure(CoordSystem=1)\n"
            genScript += "FDTD = openEMS(NrTS=max_timesteps, EndCriteria=min_decrement, CoordSystem=1)\n"
        else:
            genScript += "CSX = CSXCAD.ContinuousStructure()\n"
            genScript += "FDTD = openEMS(NrTS=max_timesteps, EndCriteria=min_decrement)\n"

        genScript += "FDTD.SetCSX(CSX)\n"
        genScript += "\n"

        print("======================== REPORT BEGIN ========================\n")

        self.reportFreeCADItemSettings(itemsByClassName.get("FreeCADSettingsItem", None))

        # Write boundary conditions definitions.
        genScript += self.getBoundaryConditionsScriptLines()

        # Write coordinate system definitions.
        genScript += self.getCoordinateSystemScriptLines()

        # Write excitation definition.
        genScript += self.getExcitationScriptLines()

        # Write material definitions.
        genScript += self.getMaterialDefinitionsScriptLines(itemsByClassName.get("MaterialSettingsItem", None), outputDir)

        # Write grid definitions.
        genScript += self.getOrderedGridDefinitionsScriptLines(itemsByClassName.get("GridSettingsItem", None))

        # Write port definitions.
        genScript += self.getPortDefinitionsScriptLines(itemsByClassName.get("PortSettingsItem", None))

        # Write lumped part definitions.
        genScript += self.getLumpedPartDefinitionsScriptLines(itemsByClassName.get("LumpedPartSettingsItem", None))

        # Write probes definitions
        genScript += self.getProbeDefinitionsScriptLines(itemsByClassName.get("ProbeSettingsItem", None))

        # Write NF2FF probe grid definitions.
        genScript += self.getNF2FFDefinitionsScriptLines(itemsByClassName.get("ProbeSettingsItem", None))

        # Write scriptlines which removes gridline too close, must be enabled in GUI, it's checking checkbox inside
        genScript += self.getMinimalGridlineSpacingScriptLines()

        print("======================== REPORT END ========================\n")

        # Finalize script.

        genScript += "#######################################################################################################################################\n"
        genScript += "# RUN\n"
        genScript += "#######################################################################################################################################\n"

        genScript += "### Run the simulation\n"
        genScript += "CSX_file = os.path.join(Sim_Path, Sim_CSX)\n"
        genScript += "if not os.path.exists(Sim_Path):\n"
        genScript += "\tos.mkdir(Sim_Path)\n"
        genScript += "CSX.Write2XML(CSX_file)\n"
        genScript += "from CSXCAD import AppCSXCAD_BIN\n"
        genScript += "os.system(AppCSXCAD_BIN + ' \"{}\"'.format(CSX_file))\n"
        genScript += "\n"
        genScript += "if not postprocessing_only:\n"
        genScript += "\tFDTD.Run(Sim_Path, verbose=3, cleanup=True, setup_only=setup_only, debug_pec=debug_pec)\n"

        # Write _OpenEMS.py script file to current directory.
        currDir, nameBase = self.getCurrDir()

        if (not outputDir is None):
            fileName = f"{outputDir}/{nameBase}_openEMS.py"
        else:
            fileName = f"{currDir}/{nameBase}_openEMS.py"

        f = open(fileName, "w", encoding='utf-8')
        f.write(genScript)
        f.close()

        # Show message or update status bar to inform user that exporting has finished.

        self.guiHelpers.displayMessage('Simulation script written to: ' + fileName, forceModal=False)
        print('Simulation script written to: ' + fileName)

        return

    #
    #	Write NF2FF Button clicked, generate script to display far field pattern
    #
    def writeNf2ffButtonClicked(self, outputDir=None):
        genScript = ""
        genScript += """close all
clear
clc

Sim_Path = "simulation_output";
CSX = InitCSX();

"""

        refUnit = self.getUnitLengthFromUI_m()  # Coordinates need to be given in drawing units
        sf = self.getFreeCADUnitLength_m() / refUnit  # scaling factor for FreeCAD units to drawing units

        excitationCategory = self.form.objectAssignmentRightTreeWidget.findItems("Excitation",
                                                                                 QtCore.Qt.MatchFixedString)
        if len(excitationCategory) >= 0:
            # FOR WHOLE SIMULATION THERE IS JUST ONE EXCITATION DEFINED, so first is taken!
            item = excitationCategory[0].child(0)
            currSetting = item.data(0, QtCore.Qt.UserRole)  # at index 0 is Default Excitation

            if (currSetting.getType() == 'sinusodial'):
                genScript += "f0 = " + str(currSetting.sinusodial['f0']) + ";\n"
                pass
            elif (currSetting.getType() == 'gaussian'):
                genScript += "f0 = " + str(currSetting.gaussian['f0']) + "*" + str(
                    currSetting.getUnitsAsNumber(currSetting.units)) + ";\n"
                genScript += "fc = " + str(currSetting.gaussian['fc']) + "*" + str(
                    currSetting.getUnitsAsNumber(currSetting.units)) + ";\n"
                pass
            elif (currSetting.getType() == 'custom'):
                genScript += "%custom\n"
                pass
            pass

        genScript += """
freq = linspace( max([0,f0-fc]), f0+fc, 501 );
f_res = f0;
"""
        genScriptPortCount = 1
        genNF2FFBoxCounter = 1
        currentNF2FFBoxIndex = 1

        allItems = []
        childCount = self.form.objectAssignmentRightTreeWidget.invisibleRootItem().childCount()
        for k in range(childCount):
            allItems.append(self.form.objectAssignmentRightTreeWidget.topLevelItem(k))

        for m in range(len(allItems)):
            currItem = allItems[m]

            for k in range(currItem.childCount()):
                item = currItem.child(k)
                itemData = item.data(0, QtCore.Qt.UserRole)
                if (itemData):
                    if (itemData.__class__.__name__ == "PortSettingsItem"):
                        print("Port Settings detected")
                        currSetting = item.data(0, QtCore.Qt.UserRole)
                        print("#")
                        print("#PORT")
                        print("#name: " + currSetting.getName())
                        print("#type: " + currSetting.getType())

                        objs = self.cadHelpers.getObjects()
                        for k in range(item.childCount()):
                            childName = item.child(k).text(0)

                            genScript += "%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%\n"
                            genScript += "% PORT - " + currSetting.getName() + " - " + childName + "\n"
                            genScript += "%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%\n"

                            print("##Children:")
                            print("\t" + childName)
                            freecadObjects = [i for i in objs if (i.Label) == childName]

                            # print(freecadObjects)
                            for obj in freecadObjects:
                                # BOUNDING BOX
                                bbCoords = obj.Shape.BoundBox

                                #
                                #	getting item priority
                                #
                                priorityItemName = item.parent().text(0) + ", " + item.text(0) + ", " + childName
                                priorityIndex = self.getItemPriority(priorityItemName)

                                #
                                # PORT openEMS GENERATION INTO VARIABLE
                                #
                                if (currSetting.getType() == 'lumped' and currSetting.isActive):
                                    genScript += 'portStart = [' + str(bbCoords.XMin) + ', ' + str(
                                        bbCoords.YMin) + ', ' + str(bbCoords.ZMin) + '];\n'
                                    genScript += 'portStop = [' + str(bbCoords.XMax) + ', ' + str(
                                        bbCoords.YMax) + ', ' + str(bbCoords.ZMax) + '];\n'
                                    genScript += 'portR = ' + str(currSetting.R) + ';\n'
                                    genScript += 'portUnits = ' + str(currSetting.getRUnits()) + ';\n'

                                    if (currSetting.direction == 'x'):
                                        genScript += 'portDirection = [1 0 0];\n'
                                    elif (currSetting.direction == 'y'):
                                        genScript += 'portDirection = [0 1 0];\n'
                                    elif (currSetting.direction == 'z'):
                                        genScript += 'portDirection = [0 0 1];\n'

                                    genScript_isActive = ""
                                    if (currSetting.isActive):
                                        genScript_isActive = " , true"

                                    genScript += '[CSX port{' + str(
                                        genScriptPortCount) + '}] = AddLumpedPort(CSX, ' + str(
                                        priorityIndex) + ', ' + str(
                                        genScriptPortCount) + ', portR*portUnits, portStart, portStop, portDirection' + genScript_isActive + ');\n'
                                    genScript += 'port{' + str(genScriptPortCount) + '} = calcPort( port{' + str(
                                        genScriptPortCount) + '}, Sim_Path, freq);\n'

                                    genScriptPortCount += 1
                                elif (currSetting.getType() == 'nf2ff box'):
                                    genScript += 'nf2ffStart = [' + str(bbCoords.XMin) + ', ' + str(
                                        bbCoords.YMin) + ', ' + str(bbCoords.ZMin) + '];\n'
                                    genScript += 'nf2ffStop = [' + str(bbCoords.XMax) + ', ' + str(
                                        bbCoords.YMax) + ', ' + str(bbCoords.ZMax) + '];\n'
                                    genScript += "[CSX nf2ffBox{" + str(
                                        genNF2FFBoxCounter) + "}] = CreateNF2FFBox(CSX, '" + currSetting.name + "', nf2ffStart, nf2ffStop);\n"

                                    # update nf2ffBox index for which far field diagram will be calculated in octave script
                                    if self.form.portNf2ffObjectList.currentText() == currSetting.name:
                                        currentNF2FFBoxIndex = genNF2FFBoxCounter

                                    # increase nf2ff port counter
                                    genNF2FFBoxCounter += 1

        thetaStart = str(self.form.portNf2ffThetaStart.value())
        thetaStop = str(self.form.portNf2ffThetaStop.value())
        thetaStep = str(self.form.portNf2ffThetaStep.value())

        phiStart = str(self.form.portNf2ffPhiStart.value())
        phiStop = str(self.form.portNf2ffPhiStop.value())
        phiStep = str(self.form.portNf2ffPhiStep.value())

        genScript += """
%% NFFF contour plots %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
% get accepted antenna power at frequency f0
%
%	WARNING - hardwired 1st port
%
P_in_0 = interp1(freq, port{1}.P_acc, f0);

% calculate the far field at phi=0 degrees and at phi=90 degrees

%thetaRange = unique([0:0.5:90 90:180]);
thetaRange = unique([""" + thetaStart + """:""" + thetaStep + """:""" + thetaStop + """]);

%phiRange = (0:2:360) - 180;
phiRange = (""" + phiStart + """:""" + phiStep + """:""" + phiStop + """) - 180;

disp( 'calculating the 3D far field...' );

%
%	nf2ffBox{index} - index is set based on GUI option choosed which NF2FF box should be calculated
%
%	'Mode',1 - always recalculate data
%		url: https://github.com/thliebig/openEMS/blob/master/matlab/CalcNF2FF.m
%
nf2ff = CalcNF2FF(nf2ffBox{""" + str(currentNF2FFBoxIndex) + """}, Sim_Path, f_res, thetaRange*pi/180, phiRange*pi/180, 'Mode', 1, 'Outfile', '3D_Pattern.h5', 'Verbose', 1);

theta_HPBW = interp1(nf2ff.E_norm{1}(:,1)/max(nf2ff.E_norm{1}(:,1)),thetaRange,1/sqrt(2))*2;

% display power and directivity
disp( ['radiated power: Prad = ' num2str(nf2ff.Prad) ' Watt']);
disp( ['directivity: Dmax = ' num2str(nf2ff.Dmax) ' (' num2str(10*log10(nf2ff.Dmax)) ' dBi)'] );
disp( ['efficiency: nu_rad = ' num2str(100*nf2ff.Prad./P_in_0) ' %']);
disp( ['theta_HPBW = ' num2str(theta_HPBW) ' Â°']);


%%
directivity = nf2ff.P_rad{1}/nf2ff.Prad*4*pi;
directivity_CPRH = abs(nf2ff.E_cprh{1}).^2./max(nf2ff.E_norm{1}(:)).^2*nf2ff.Dmax;
directivity_CPLH = abs(nf2ff.E_cplh{1}).^2./max(nf2ff.E_norm{1}(:)).^2*nf2ff.Dmax;

%%
figure
plot(thetaRange, 10*log10(directivity(:,1)'),'k-','LineWidth',2);
hold on
grid on
xlabel('theta (deg)');
ylabel('directivity (dBi)');
plot(thetaRange, 10*log10(directivity_CPRH(:,1)'),'g--','LineWidth',2);
plot(thetaRange, 10*log10(directivity_CPLH(:,1)'),'r-.','LineWidth',2);
legend('norm','CPRH','CPLH');

%% dump to vtk
DumpFF2VTK([Sim_Path '/3D_Pattern.vtk'],directivity,thetaRange,phiRange,'scale',1e-3);
DumpFF2VTK([Sim_Path '/3D_Pattern_CPRH.vtk'],directivity_CPRH,thetaRange,phiRange,'scale',1e-3);
DumpFF2VTK([Sim_Path '/3D_Pattern_CPLH.vtk'],directivity_CPLH,thetaRange,phiRange,'scale',1e-3);

E_far_normalized = nf2ff.E_norm{1} / max(nf2ff.E_norm{1}(:)) * nf2ff.Dmax;
DumpFF2VTK([Sim_Path '/3D_Pattern_normalized.vtk'],E_far_normalized,thetaRange,phiRange,1e-3);
"""
        #
        # WRITE OpenEMS Script file into current dir
        #
        currDir, nameBase = self.getCurrDir()

        self.createOuputDir(outputDir)
        if (not outputDir is None):
            fileName = f"{outputDir}/{nameBase}_draw_NF2FF.py"
        else:
            fileName = f"{currDir}/{nameBase}_draw_NF2FF.py"

        f = open(fileName, "w", encoding='utf-8')
        f.write(genScript)
        f.close()
        print('Script to display far field written into: ' + fileName)
        self.guiHelpers.displayMessage('Script to display far field written into: ' + fileName, forceModal=False)

    def drawS11ButtonClicked(self, outputDir=None):
        genScript = ""

        excitationCategory = self.form.objectAssignmentRightTreeWidget.findItems("Excitation",
                                                                                 QtCore.Qt.MatchFixedString)
        if len(excitationCategory) >= 0:
            # FOR WHOLE SIMULATION THERE IS JUST ONE EXCITATION DEFINED, so first is taken!
            item = excitationCategory[0].child(0)
            currSetting = item.data(0, QtCore.Qt.UserRole)  # at index 0 is Default Excitation

            if (currSetting.getType() == 'sinusodial'):
                genScript += "f0 = " + str(currSetting.sinusodial['f0']) + ";\n"
                pass
            elif (currSetting.getType() == 'gaussian'):
                genScript += "f0 = " + str(currSetting.gaussian['f0']) + "*" + str(
                    currSetting.getUnitsAsNumber(currSetting.units)) + ";\n"
                genScript += "fc = " + str(currSetting.gaussian['fc']) + "*" + str(
                    currSetting.getUnitsAsNumber(currSetting.units)) + ";\n"
                pass
            elif (currSetting.getType() == 'custom'):
                genScript += "%custom\n"
                pass
            pass

        genScript += """%% postprocessing & do the plots
freq = linspace( max([0,f0-fc]), f0+fc, 501 );
U = ReadUI( {'port_ut1','et'}, 'simulation_output/', freq ); % time domain/freq domain voltage
I = ReadUI( 'port_it1', 'simulation_output/', freq ); % time domain/freq domain current (half time step is corrected)

% plot time domain voltage
figure
[ax,h1,h2] = plotyy( U.TD{1}.t/1e-9, U.TD{1}.val, U.TD{2}.t/1e-9, U.TD{2}.val );
set( h1, 'Linewidth', 2 );
set( h1, 'Color', [1 0 0] );
set( h2, 'Linewidth', 2 );
set( h2, 'Color', [0 0 0] );
grid on
title( 'time domain voltage' );
xlabel( 'time t / ns' );
ylabel( ax(1), 'voltage ut1 / V' );
ylabel( ax(2), 'voltage et / V' );
% now make the y-axis symmetric to y=0 (align zeros of y1 and y2)
y1 = ylim(ax(1));
y2 = ylim(ax(2));
ylim( ax(1), [-max(abs(y1)) max(abs(y1))] );
ylim( ax(2), [-max(abs(y2)) max(abs(y2))] );

% plot feed point impedance
figure
Zin = U.FD{1}.val ./ I.FD{1}.val;
plot( freq/1e6, real(Zin), 'k-', 'Linewidth', 2 );
hold on
grid on
plot( freq/1e6, imag(Zin), 'r--', 'Linewidth', 2 );
title( 'feed point impedance' );
xlabel( 'frequency f / MHz' );
ylabel( 'impedance Z_{in} / Ohm' );
legend( 'real', 'imag' );

% plot reflection coefficient S11
figure
uf_inc = 0.5*(U.FD{1}.val + I.FD{1}.val * 50);
if_inc = 0.5*(I.FD{1}.val - U.FD{1}.val / 50);
uf_ref = U.FD{1}.val - uf_inc;
if_ref = I.FD{1}.val - if_inc;
s11 = uf_ref ./ uf_inc;
plot( freq/1e6, 20*log10(abs(s11)), 'k-', 'Linewidth', 2 );
grid on
title( 'reflection coefficient S_{11}' );
xlabel( 'frequency f / MHz' );
ylabel( 'reflection coefficient |S_{11}|' );

P_in = 0.5*U.FD{1}.val .* conj( I.FD{1}.val );

%
%   Write S11, real and imag Z_in into CSV file separated by ';'
%
filename = 'openEMS_simulation_s11_dB.csv';
fid = fopen(filename, 'w');
fprintf(fid, 'freq (MHz);s11 (dB);real Z_in (Ohm); imag Z_in (Ohm)\\n');
fclose(fid)
s11_dB = horzcat((freq/1e6)', 20*log10(abs(s11))', real(Zin)', imag(Zin)');
dlmwrite(filename, s11_dB, '-append', 'delimiter', ';');
"""

        #
        # WRITE OpenEMS Script file into current dir
        #
        currDir, nameBase = self.getCurrDir()

        self.createOuputDir(outputDir)
        if (not outputDir is None):
            fileName = f"{outputDir}/{nameBase}_draw_S11.py"
        else:
            fileName = f"{currDir}/{nameBase}_draw_S11.py"

        f = open(fileName, "w", encoding='utf-8')
        f.write(genScript)
        f.close()
        print('Draw result from simulation file written into: ' + fileName)
        self.guiHelpers.displayMessage('Draw result from simulation file written into: ' + fileName, forceModal=False)

        # run octave script using command shell
        cmdToRun = self.getOctaveExecCommand(fileName, '-q --persist')
        print('Running command: ' + cmdToRun)
        result = os.system(cmdToRun)
        #print(result)

    def drawS21ButtonClicked(self, outputDir=None):
        genScript = ""
        genScript += "% Plot S11, S21 parameters from OpenEMS results.\n"
        genScript += "%\n"

        genScript += self.getInitScriptLines()

        genScript += "Sim_Path = 'simulation_output';\n"
        genScript += "CSX = InitCSX('CoordSystem',0);\n"
        genScript += "\n"

        # List categories and items.

        itemsByClassName = self.getItemsByClassName()

        # Write excitation definition.

        genScript += self.getExcitationScriptLines(definitionsOnly=True)

        # Write port definitions.

        genScript += self.getPortDefinitionsScriptLines(itemsByClassName.get("PortSettingsItem", None))

        # Post-processing and plot generation.

        genScript += "%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%\n"
        genScript += "% POST-PROCESSING AND PLOT GENERATION\n"
        genScript += "%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%\n"
        genScript += "\n"
        genScript += "freq = linspace( max([0,f0-fc]), f0+fc, 501 );\n"
        genScript += "port = calcPort( port, Sim_Path, freq);\n"
        genScript += "\n"
        genScript += "s11 = port{1}.uf.ref./ port{1}.uf.inc;\n"
        genScript += "s21 = port{2}.uf.ref./ port{1}.uf.inc;\n"
        genScript += "\n"
        genScript += "s11_dB = 20*log10(abs(s11));\n"
        genScript += "s21_dB = 20*log10(abs(s21));\n"
        genScript += "\n"
        genScript += "plot(freq/1e9,s11_dB,'k-','LineWidth',2);\n"
        genScript += "hold on;\n"
        genScript += "grid on;\n"
        genScript += "plot(freq/1e9,s21_dB,'r--','LineWidth',2);\n"
        genScript += "legend('S_{11}','S_{21}');\n"
        genScript += "ylabel('S-Parameter (dB)','FontSize',12);\n"
        genScript += "xlabel('frequency (GHz) \\rightarrow','FontSize',12);\n"
        genScript += "ylim([-40 2]);\n"
        genScript += "\n"

        genScript += "%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%\n"
        genScript += "% SAVE PLOT DATA\n"
        genScript += "%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%\n"
        genScript += "\n"
        genScript += "save_plot_data = 0;\n"
        genScript += "\n"
        genScript += "if (save_plot_data != 0)\n"
        genScript += "	mfile_name = mfilename('fullpath');\n"
        genScript += "	[pathstr,name,ext] = fileparts(mfile_name);\n"
        genScript += "	output_fn = strcat(pathstr, '/', name, '.csv')\n"
        genScript += "	\n"
        genScript += "	%% write header to file\n"
        genScript += "	textHeader = '#f(Hz)\\tS11(dB)\\tS21(dB)';\n"
        genScript += "	fid = fopen(output_fn, 'w');\n"
        genScript += "	fprintf(fid, '%s\\n', textHeader);\n"
        genScript += "	fclose(fid);\n"
        genScript += "	\n"
        genScript += "	%% write data to end of file\n"
        genScript += "	dlmwrite(output_fn, [abs(freq)', s11_dB', s21_dB'],'delimiter','\\t','precision',6, '-append');\n"
        genScript += "end\n"
        genScript += "\n"

        # Write OpenEMS Script file into current dir.

        currDir, nameBase = self.getCurrDir()

        self.createOuputDir(outputDir)
        if (not outputDir is None):
            fileName = f"{outputDir}/{nameBase}_draw_S21.py"
        else:
            fileName = f"{currDir}/{nameBase}_draw_S21.py"

        f = open(fileName, "w", encoding='utf-8')
        f.write(genScript)
        f.close()
        print('Draw result from simulation file written to: ' + fileName)
        self.guiHelpers.displayMessage('Draw result from simulation file written to: ' + fileName, forceModal=False)

        # Run octave script using command shell.

        cmdToRun = self.getOctaveExecCommand(fileName, '-q --persist')
        print('Running command: ' + cmdToRun)
        result = os.system(cmdToRun)
        print(result)

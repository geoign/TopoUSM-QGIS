# -*- coding: utf-8 -*-
"""
/***************************************************************************
 TopoUSM2 QGIS Plugin (main)
                                 
 Generating ambient shading layers for raster terrain data.
 See https://github.com/geoign/TopoUSM-QGIS/

                              -------------------
        begin                : 2018-04-30
        git sha              : $Format:%H$
        copyright            : (C) 2018 by Fumihiko Ikegami
        email                : f.ikegami@gmail.com
/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/

## Future TODO:
- aaaa

"""


from qgis.gui import (QgsFieldComboBox, QgsMapLayerComboBox)
from qgis.core import QgsMapLayerProxyModel, QgsColorRampShader, QgsRasterMinMaxOrigin, QgsContrastEnhancement, QgsRasterShader, QgsSingleBandPseudoColorRenderer, QgsSingleBandGrayRenderer
from PyQt5.QtCore import QSettings, QTranslator, qVersion, QCoreApplication, QFile, QIODevice
from PyQt5.QtGui import *
#from PyQt5.QtXml import QDomDocument, QDomElement
from PyQt5.QtWidgets import QAction, QMessageBox

# Initialize Qt resources from file resources.py
from .resources import *
# Import the code for the dialog
from .topousm2_dialog import TopoUSM2Dialog

## Custom imports ##
import os.path, sys, glob
import xml.etree.ElementTree as ET
from numpy import *
from time import time
from .topousm_processing import Grid



class TopoUSM2:
    def __init__(self, iface):
        # Save reference to the QGIS interface
        self.iface = iface
        # initialize plugin directory
        self.plugin_dir = os.path.dirname(__file__)
        # initialize locale
        locale = QSettings().value('locale/userLocale')[0:2]
        locale_path = os.path.join(
            self.plugin_dir,
            'i18n',
            'TopoUSM2_{}.qm'.format(locale))

        if os.path.exists(locale_path):
            self.translator = QTranslator()
            self.translator.load(locale_path)

            if qVersion() > '4.3.3':
                QCoreApplication.installTranslator(self.translator)

        # Create the dialog (after translation) and keep reference
        self.dlg = TopoUSM2Dialog()

        # Declare instance attributes
        self.actions = []
        self.menu = self.tr(u'&TopoUSM2')
        # TODO: We are going to let the user set this up in a future iteration
        self.toolbar = self.iface.addToolBar(u'TopoUSM2')
        self.toolbar.setObjectName(u'TopoUSM2')

        ################################################################
        ## Custom UIs ##
        ################################################################
        self.usmlayers = []
        ## Raster only in the Combo Manager for specifying input layer
        self.dlg.mMapLayerComboBox.setFilters(QgsMapLayerProxyModel.RasterLayer)
        ## Push run to trigger self.processing
        self.dlg.pushButton.clicked.connect(self.processing)
        ## Tab-changed action
        self.dlg.tabWidget.currentChanged.connect(self.tabChanged)
        ## Tables
        self.model = QStandardItemModel()
        self.dlg.tableView.setModel(self.model)
        ## Textedit cursor
        self.cursor = self.dlg.textEdit.textCursor()
        ## Sliders
        self.dlg.horizontalSlider.valueChanged.connect(self.slider1Changed)
        self.dlg.horizontalSlider_2.valueChanged.connect(self.slider2Changed)
        ## Push to apply styles
        self.dlg.pushButton_2.clicked.connect(self.doApply_styles_USMs)
        
    # noinspection PyMethodMayBeStatic
    def tr(self, message):
        """Get the translation for a string using Qt translation API.

        We implement this ourselves since we do not inherit QObject.

        :param message: String for translation.
        :type message: str, QString

        :returns: Translated version of message.
        :rtype: QString
        """
        # noinspection PyTypeChecker,PyArgumentList,PyCallByClass
        return QCoreApplication.translate('TopoUSM2', message)


    def add_action(
        self,
        icon_path,
        text,
        callback,
        enabled_flag=True,
        add_to_menu=True,
        add_to_toolbar=True,
        status_tip=None,
        whats_this=None,
        parent=None):
        """Add a toolbar icon to the toolbar.

        :param icon_path: Path to the icon for this action. Can be a resource
            path (e.g. ':/plugins/foo/bar.png') or a normal file system path.
        :type icon_path: str

        :param text: Text that should be shown in menu items for this action.
        :type text: str

        :param callback: Function to be called when the action is triggered.
        :type callback: function

        :param enabled_flag: A flag indicating if the action should be enabled
            by default. Defaults to True.
        :type enabled_flag: bool

        :param add_to_menu: Flag indicating whether the action should also
            be added to the menu. Defaults to True.
        :type add_to_menu: bool

        :param add_to_toolbar: Flag indicating whether the action should also
            be added to the toolbar. Defaults to True.
        :type add_to_toolbar: bool

        :param status_tip: Optional text to show in a popup when mouse pointer
            hovers over the action.
        :type status_tip: str

        :param parent: Parent widget for the new action. Defaults None.
        :type parent: QWidget

        :param whats_this: Optional text to show in the status bar when the
            mouse pointer hovers over the action.

        :returns: The action that was created. Note that the action is also
            added to self.actions list.
        :rtype: QAction
        """

        icon = QIcon(icon_path)
        action = QAction(icon, text, parent)
        action.triggered.connect(callback)
        action.setEnabled(enabled_flag)

        if status_tip is not None:
            action.setStatusTip(status_tip)

        if whats_this is not None:
            action.setWhatsThis(whats_this)

        if add_to_toolbar:
            self.toolbar.addAction(action)

        if add_to_menu:
            self.iface.addPluginToMenu(
                self.menu,
                action)

        self.actions.append(action)

        return action

    def initGui(self):
        """Create the menu entries and toolbar icons inside the QGIS GUI."""
        icon_path = ':/plugins/topousm2/icon.png'
        self.add_action(
            icon_path,
            text=self.tr(u'Create TopoUSM layer'),
            callback=self.run,
            parent=self.iface.mainWindow())

    def unload(self):
        """Removes the plugin menu item and icon from QGIS GUI."""
        for action in self.actions:
            self.iface.removePluginMenu(
                self.tr(u'&TopoUSM2'),
                action)
            self.iface.removeToolBarIcon(action)
        # remove the toolbar
        del self.toolbar

    def run(self):
        """Run method that performs all the real work"""
        # show the dialog
        self.dlg.show()
        # Run the dialog event loop
        result = self.dlg.exec_()
        # See if OK was pressed
        if result: pass

    ### Custom event functions @@@@
    def slider1Changed(self):
        val1 = self.dlg.horizontalSlider.value()
        self.dlg.label_11.setText('%.2f' % (float(val1) * 0.1))
        self.doTableRefresh()
    def slider2Changed(self):
        val2 = self.dlg.horizontalSlider_2.value()
        self.dlg.label_13.setText('%.2f' % (10**(float(val2)/10)))
        self.doTableRefresh()
    def usm_cap(self, r):
        val1, val2 = self.dlg.horizontalSlider.value(), self.dlg.horizontalSlider_2.value()
        a = float(val1) * 0.1
        b = 10**(float(val2)/10)
        return (r ** a) * b

    def tabChanged(self, i):
        if i==1: self.doTableRefresh()

    def doTableRefresh(self):
        ## Find usmfiles
        if self.usmlayers:
            usmfiles = [usmlayer.dataProvider().dataSourceUri() for usmlayer in self.usmlayers]
        else:
            usmfiles = self.find_usmfiles()
        ## Make it a table
        radius, self.amps = [], []
        radius = [self.fname2usmradius(usmfile) for usmfile in usmfiles]
        amps = [('%.2f' % self.usm_cap(r)) for r in radius]
        fnames = [os.path.basename(usmfile) for usmfile in usmfiles]
        DB = c_[radius, amps, fnames, usmfiles]
        DB = sorted(DB, key=lambda r: r[0])
        self.model.clear()
        self.model.setHorizontalHeaderLabels(['radius', 'cap', 'Name', 'Path'])
        for item in DB:
            self.model.appendRow([QStandardItem(vals) for vals in item])

    def __log__(self, text, end='\n'):
        self.dlg.textEdit.append(text + end)
        self.cursor.movePosition(QTextCursor.End)
        self.dlg.textEdit.setTextCursor(self.cursor)
        
    def fname2usmradius(self, fname):
        return int(fname[fname.rindex('_')+8 : fname.rindex('.')])
    def find_usmfiles(self, fname='auto'):
        if fname=='auto':
            srclayer = self.dlg.mMapLayerComboBox.currentLayer()
            if not srclayer: return
            fname = srclayer.dataProvider().dataSourceUri()
        fbody = fname[:fname.rindex('.')] ## Get filename without extention
        usmfiles = glob.glob(fbody+'_TopoUSM*.tif')
        usmfiles = [usmfile for usmfile in usmfiles if ('Composite' not in usmfile) and ('Blurred' not in usmfile)]
        return usmfiles

    def doApply_styles_USMs(self):
        if not self.usmlayers:
            usmfiles = self.find_usmfiles()
            for usmfile in usmfiles:
                self.usmlayers.append(self.iface.addRasterLayer(usmfile))
        for usmlayer in self.usmlayers: self.apply_styles(usmlayer)
    def apply_styles(self, layer, cap=None):
        if not layer: return
        fname = os.path.basename(layer.dataProvider().dataSourceUri())
        if cap==None:
            if ('Composite' not in fname) and ('Blurred' not in fname):
                radius = self.fname2usmradius(fname)
                cap = self.usm_cap(radius)
        ## Pesudocolor method <- It works except legend ##
        #shader, colorramp = QgsRasterShader(), QgsColorRampShader()
        #colorramp.setClassificationMode(1)
        #colorramp.setColorRampType(QgsColorRampShader.Interpolated)
        #colorramp.setColorRampItemList([ \
        #    QgsColorRampShader.ColorRampItem(-100, QColor(0,0,0)), \
        #    QgsColorRampShader.ColorRampItem(100, QColor(255,255,255))])
        #shader.setRasterShaderFunction(colorramp)
        #render = QgsSingleBandPseudoColorRenderer(usmlayer.dataProvider(), usmlayer.type(), shader)
        #usmlayer.setRenderer(render)
        #usmlayer.renderer().setClassificationMin(-100)
        #usmlayer.renderer().setClassificationMin(100)

        ## Grayscale method ##
        render = QgsSingleBandGrayRenderer(layer.dataProvider(), layer.type())

        ## Create a custom QGIS style file (QML)
        path_defaultQML = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'USM_styletemplate.qml')
        path_tmpQML = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'tmp.qml')
        tree = ET.parse(path_defaultQML)
        root = tree.getroot()
        minval = root.find('./pipe/rasterrenderer/contrastEnhancement/minValue')
        maxval = root.find('./pipe/rasterrenderer/contrastEnhancement/maxValue')
        minval.text, maxval.text = str(-1*cap), str(cap)
        tree.write(path_tmpQML)

        ## Another failed atteampt to set minmax
        #fp = QFile(path_tmpQML); fp.open(QIODevice.ReadOnly)
        #doc = QDomDocument(); doc.setContent(fp); fp.close()
        #elem = doc.documentElement() #QDOMElement
        #contrast = QgsContrastEnhancement()
        #contrast.readXml(elem)
        #contrast.setContrastEnhancementAlgorithm(QgsContrastEnhancement.StretchToMinimumMaximum, False)
        #contrast.setMaximumValue(100, False); contrast.setMinimumValue(-100, True) # <- Completely broken
        #render.setContrastEnhancement(contrast)
        #render.setGradient(QgsSingleBandGrayRenderer.BlackToWhite)
        #usmlayer.setRenderer(render)

        ## Another failed attempt to set minmax ##
        #bounds = QgsRasterMinMaxOrigin()
        #bounds.setExtent(QgsRasterMinMaxOrigin.WholeRaster)
        #bounds.setLimits(QgsRasterMinMaxOrigin.StdDev)
        #bounds.setStatAccuracy(QgsRasterMinMaxOrigin.Estimated)
        #usmlayer.renderer().setMinMaxOrigin(bounds)
        
        ## Then import it to the layer
        layer.setBlendMode(QPainter.CompositionMode_Overlay)
        layer.loadNamedStyle(path_tmpQML)
        layer.setCrs(self.dlg.mMapLayerComboBox.currentLayer().crs())
        layer.emitStyleChanged() # <- Broken?
        layer.triggerRepaint()
            
    def processing(self):
        ################################################################
        ## Custom Ops ##
        ################################################################
        srclayer = self.dlg.mMapLayerComboBox.currentLayer()
        if not srclayer: return
        srcfname = srclayer.dataProvider().dataSourceUri()
        if not os.path.exists(srcfname): return
        fbody = srcfname[:srcfname.rindex('.')] ## Get filename without extention

        ## Disable interface during the processing
        self.dlg.pushButton.setEnabled(False)
        self.dlg.tabWidget.setEnabled(False) 
        self.dlg.textEdit.clear()

        ## Setup handling of NaNs
        nodata = []
        for val in self.dlg.lineEdit_3.text().split(','):
            if val=='$floatmin': nodata.append(sys.float_info.min)
            elif val=='$floatmax': nodata.append(sys.float_info.max)
            elif val=='$intmax': nodata.append(sys.maxsize)
            elif val=='$intmin': nodata.append(-sys.maxsize-1)
            else: nodata.append(float(nodata))
        bounds = [float(i) for i in self.dlg.lineEdit_2.text().split(',')]
        replacenan = nan if self.dlg.lineEdit_4.text()=='NaN' else float(self.dlg.lineEdit_4.text())

        ## Read source grid
        G = Grid(self.dlg, srcfname, nodata)
        self.__log__(G.fname)
        G.Z[G.Z<bounds[0]] = nan
        G.Z[G.Z>bounds[1]] = nan
        G.Z[isnan(G.Z)] = replacenan
        original_stdev = nanstd(G.Z)
        
        if self.dlg.tabWidget.currentIndex() == 0:
            ## TopoUSM processing ##    
            radius = map(int, self.dlg.lineEdit.text().split(','))
            iterations = int(self.dlg.mQgsSpinBox.value())
            Z0 = G.Z.copy() ##Backup original array so that no need to reopen
            
            usmfiles = []
            for r in radius:
                G.Z = Z0.copy()
                G.TopoUSM2(r, iterations)
                if self.dlg.checkBox_4.isChecked():
                    G.log10(amp=1) ## Apply logarithmic dynamic range compression if specified
                ## Save TopoUSM rasters
                fname = (fbody+'_TopoUSM%d.tif' % r)
                usmfiles.append(fname)
                if self.dlg.checkBox_2.isChecked():
                    G.save_asint16(fname, nodata=nan)
                else:
                    G.save(fname, nodata=nan)
                if self.dlg.checkBox_3.isChecked():
                    ## Save blurred rasters if specified
                    fname = (fbody+'_Blurred%d.tif' % r)
                    usmfiles.append(fname)
                    G.Z = G.Z_blurred
                    G.save(fname, nodata=nan)
                self.__log__('T + %d seconds.' % (time() - G.timestart))
            QMessageBox.information(self.dlg, "Done!", "Done!"); G=None
            self.__log__('Following files were generated:\n' + '\n'.join(usmfiles))
            self.__log__('Tips: After the completion, you may set optimal value ranges (e.g. -100,100) for each TopoUSM layers and then change the color blending mode to overlay or hardlight. Currently, automatically estimated values are set. Following layering is the quickest choice: Color gradation (Normal) > TopoUSM layers (hardlight) > hillshade, slope, or contours (multiply)')
    
            ## Open files after completion ##
            if self.dlg.checkBox.isChecked():
                for usmfile in usmfiles:
                    self.usmlayers.append(self.iface.addRasterLayer(usmfile))
                    
        elif self.dlg.tabWidget.currentIndex() == 1:
            ## TopoUSM stacking ##
            if self.usmlayers:
                usmfiles = [usmlayer.dataProvider().dataSourceUri() for usmlayer in self.usmlayers]
            else:
                usmfiles = self.find_usmfiles()
            outfile = srcfname[:srcfname.rindex('.')] + '_TopoUSM-Composite.tif'
            radius = [self.fname2usmradius(usmfile) for usmfile in usmfiles]
            caps = [self.usm_cap(r) for r in radius]
            amps = [max(caps)/cap for cap in caps]
            G0 = Grid(self.dlg, usmfiles[0], nodata=[]); G0.Z[isnan(G0.Z)]=0
            Z = array(G0.Z.copy(), dtype=float) * amps[0] / len(amps)
            for i in arange(1, len(usmfiles)):
                self.__log__('[Stack] %s amp=%.2f' % (usmfiles[i],amps[i]))
                G1 = Grid(self.dlg, usmfiles[i], nodata=[nan]); G1.Z[isnan(G1.Z)]=0
                Z += G1.Z * amps[i] / len(amps)
            G0.Z = Z
            if self.dlg.checkBox_2.isChecked():
                G0.save_asint16(outfile, nodata=nan)
            else: G0.save(outfile, nodata=nan)
            self.__log__('Composite USM file was successfully baked:\n' + outfile)
            if self.dlg.checkBox.isChecked():
                composite_layer = self.iface.addRasterLayer(outfile)
                self.apply_styles(composite_layer, cap=max(caps))
            G0, G1 = None, None ## Clear memory

        ##Enalbe interface ater the processing
        self.dlg.pushButton.setEnabled(True)
        self.dlg.tabWidget.setEnabled(True) 


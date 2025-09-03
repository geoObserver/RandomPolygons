import os
from PyQt5.QtWidgets import QAction, QMessageBox, QPushButton, QDialog, QVBoxLayout, QFormLayout, QLabel, QLineEdit, \
    QSpinBox, QHBoxLayout, QToolBar
from PyQt5.QtGui import QIcon, QColor
from qgis.utils import iface
import time
####
from qgis.PyQt.QtWidgets import QInputDialog
from qgis.PyQt.QtCore import QMetaType, QVariant
from qgis.PyQt.QtGui import QColor
from qgis.core import (
    QgsProject, QgsVectorLayer, QgsField, QgsPointXY,
    QgsFeature, QgsGeometry, QgsGeometryValidator,
    QgsFillSymbol, QgsSingleSymbolRenderer, QgsLayerTreeGroup, QgsExpressionContextUtils
)
import random
import string

plugin_dir = os.path.dirname(__file__)


class MultiInputDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("RandomPolygons: Choose your parameters ...")

        self.layout = QVBoxLayout(self)

        # Eingabefelder
        self.count_polygons_input = QSpinBox()
        self.count_polygons_input.setRange(1, 2000)
        self.count_polygons_input.setValue(100)
        self.max_corners_input = QSpinBox()
        self.max_corners_input.setRange(3, 20)
        self.max_corners_input.setValue(10)
        self.max_notvalid_polygons_input = QSpinBox()
        self.max_notvalid_polygons_input.setRange(1, 50)
        self.max_notvalid_polygons_input.setValue(10)
        self.max_extent_polygons_input = QSpinBox()
        self.max_extent_polygons_input.setRange(1, 50)
        self.max_extent_polygons_input.setValue(10)

        self.layout.addWidget(QLabel("Count of polygons [1 ... 2000]:"))
        self.layout.addWidget(self.count_polygons_input)
        self.layout.addWidget(QLabel(f"Max.{' ' * 2}corners per polygon [3 ... 20]:"))
        self.layout.addWidget(self.max_corners_input)
        self.layout.addWidget(QLabel(f"Max.{' ' * 2}count of NOT valid polygons [1 ... 50%]:"))
        self.layout.addWidget(self.max_notvalid_polygons_input)
        self.layout.addWidget(QLabel(f"Max.{' ' * 2}extent of a polygon in relation to canvas [10 ... 50%]:"))
        self.layout.addWidget(self.max_extent_polygons_input)

        # OK-Button
        self.button_layout = QHBoxLayout()
        self.ok_button = QPushButton("OK")
        self.cancel_button = QPushButton("Cancel")
        self.ok_button.clicked.connect(self.accept)
        self.cancel_button.clicked.connect(self.reject)
        self.layout.addWidget(self.ok_button)
        self.layout.addWidget(self.cancel_button)

    def getInputs(self):
        return self.count_polygons_input.text(), self.max_corners_input.text(), self.max_notvalid_polygons_input.text(), self.max_extent_polygons_input.text()


class RandomPolygons:
    def __init__(self, iface):
        self.iface = iface
        self.toolbar = None
        self.actions = []

    def initGui(self):
        from PyQt5.QtWidgets import QToolBar
        # Prüfen, ob gemeinsame Toolbar schon existiert
        self.toolbar = self.iface.mainWindow().findChild(QToolBar, "#geoObserverTools")
        if not self.toolbar:
            # Nur beim ersten Plugin anlegen
            self.toolbar = self.iface.addToolBar("#geoObserver Tools")
            self.toolbar.setObjectName("#geoObserverTools")

        # Button/Aktion erstellen
        icon = os.path.join(plugin_dir, 'logo.png')
        self.action = QAction(QIcon(icon), 'RandomPolygons', self.iface.mainWindow())
        self.action.triggered.connect(self.run)

        # Aktion in gemeinsame Toolbar einfügen
        self.toolbar.addAction(self.action)
        self.actions.append(self.action)

    def unload(self):
        # Nur eigene Buttons entfernen
        for action in self.actions:
            self.toolbar.removeAction(action)
        self.actions.clear()

    def run(self):
        starttime = time.time()
        formatted_time = time.strftime("%y.%m.%d %H:%M:%S", time.localtime(starttime))
        print('\n\n+--- RandomPolygons: S T A R T --- ' + str(formatted_time) + ' -------------------------------')

        # (Rest deines run()-Codes unverändert)
        # ...

        #############################################################################################################
        # ---------------------------------------------------------------------------
        # 1) Benutzer nach Parametern fragen
        # ---------------------------------------------------------------------------
        dialog = MultiInputDialog()
        if dialog.exec_():
            count_polygons, max_corners, max_notvalid_polygons, max_extent_polygons = dialog.getInputs()
            print(" M1: count_polygons = ", count_polygons)
            print(" M2: max_corners = ", max_corners)
            print(" M3: max_notvalid_polygons = ", max_notvalid_polygons)
            print(" M4: max_extent_polygons = ", max_extent_polygons)
        else:
            print(' M0: Cancelled by user.')
            self.iface.messageBar().pushMessage("RandomPolygons: ", 'Cancelled by user.' ,3,3)
            return
        
        # ---------------------------------------------------------------------------
        # 2) Karten‑Parameter holen
        # ---------------------------------------------------------------------------
        canvas  = iface.mapCanvas()
        extent  = canvas.extent()
        crs     = canvas.mapSettings().destinationCrs()
        print(' M6: Extent: ' + str(extent))
        print(' M7: CRS: ' + str(crs))
        
        # Max. Breite/Höhe eines Polygons bezogen auf Kartenbreite/-höhe
        #max_w   = extent.width()  / 10.0
        #max_h   = extent.height() / 10.0
        max_w   = extent.width()  / 100 * (int(max_extent_polygons))
        max_h   = extent.height() / 100 * (int(max_extent_polygons))
        print(' M8: max_w: ' + str(max_w))
        print(' M9: max_h: ' + str(max_h))
        
        # ---------------------------------------------------------------------------
        # 3) Ziel‑Layer im Speicher anlegen
        # ---------------------------------------------------------------------------
        layername = 'RandomPolygons (' + str(formatted_time) + ')'
        print('M10: Layername: ' + layername)
        layer = QgsVectorLayer(f'Polygon?crs={crs.authid()}', layername , 'memory')
        prov  = layer.dataProvider()
        prov.addAttributes([QgsField('id', QMetaType.Int)])
        layer.updateFields()
        
        # ---------------------------------------------------------------------------
        # 4) Hilfsfunktionen
        # ---------------------------------------------------------------------------
        
        def random_polygon(ext, max_w, max_h):
            """Erzeugt ein einzelnes (potenziell ungültiges) Polygon,
               dessen Ausdehnung max_w × max_h nicht überschreitet."""
            cx = random.uniform(ext.xMinimum(), ext.xMaximum())
            cy = random.uniform(ext.yMinimum(), ext.yMaximum())
            
            #n_pts = random.randint(3, 20)
            n_pts = random.randint(3, int(max_corners))  # Anzahl der Ecken 3 ... max. Eckenzahl
            pts   = []
            #pts_counter = 0
            for _ in range(n_pts):
                #print('pts_counter: ' + str(pts_counter))
                dx = random.uniform(-max_w/2, max_w/2)
                dy = random.uniform(-max_h/2, max_h/2)
                pts.append(QgsPointXY(cx + dx, cy + dy))
                #pts_counter = pts_counter + 1

                
            random.shuffle(pts)                 # erzeugt häufiger Selbstüberschneidungen
            if random.random() < 0.3:           # ca. 30 %: Duplikat einschleusen
                pts.insert(random.randrange(len(pts)), random.choice(pts))
            
            if pts[0] != pts[-1]:               # zu Polygon schließen
                pts.append(pts[0])
                
            return QgsGeometry.fromPolygonXY([pts])
            
        def is_valid(geom: QgsGeometry) -> bool:
            """Schnelle, versionskompatible Gültigkeitsprüfung."""
            if hasattr(geom, 'isGeosValid'):    # QGIS ≥ 3.36
                return geom.isGeosValid()
            return len(QgsGeometryValidator.validateGeometry(geom)) == 0
            
        # ---------------------------------------------------------------------------
        # 5) Polygone erzeugen (max. 10 % ungültig)
        # ---------------------------------------------------------------------------
        #invalid_target  = 0.30                     # x % zulassen
        invalid_target  = int(max_notvalid_polygons) / 100
        invalid_limit   = int(int(count_polygons) * invalid_target)
        invalid_count   = 0
        feats           = []
        tries           = 0
        max_tries       = 100000                   # Sicherheitsbremse
        
        while len(feats) < int(count_polygons) and tries < max_tries:
            tries += 1
            geom  = random_polygon(extent, max_w, max_h)
            valid = is_valid(geom)
            
            if valid or invalid_count < invalid_limit:
                feat = QgsFeature()
                feat.setAttributes([len(feats)+1])
                feat.setGeometry(geom)
                feats.append(feat)
                if not valid:
                    invalid_count += 1
            # sonst wird das ungültige Polygon verworfen und neu versucht
            
        if len(feats) < int(count_polygons):
            print('M9: Abbruch: zu viele Fehlversuche (max_tries erreicht)')
            return
            #raise RuntimeError('Abbruch: zu viele Fehlversuche (max_tries erreicht)')
        
        prov.addFeatures(feats)
        layer.updateExtents()
        QgsProject.instance().addMapLayer(layer)
        
        # ---------------------------------------------------------------------------
        # 6) Symbolisierung: Rot, 50 % transparent, schwarzer Rand
        # ---------------------------------------------------------------------------
        symbol   = QgsFillSymbol.createSimple({'outline_color': '0,0,0', 'outline_width': '0.4'})
        #symbol.setColor(QColor(255, 0, 0, 128))     # RGBA (Alpha 128 = 50 %)
        symbol.setColor(QColor(int(random.uniform(100,255)), int(random.uniform(100,255)), int(random.uniform(100,255)), 50))  # Rot + 50 % Transparenz (Alpha=128)
        renderer = QgsSingleSymbolRenderer(symbol)
        layer.setRenderer(renderer)
        layer.triggerRepaint()
        
        # ---------------------------------------------------------------------------
        # 7) Feature‑Zähler im Layer‑Baum aktivieren
        # ---------------------------------------------------------------------------
        node = QgsProject.instance().layerTreeRoot().findLayer(layer.id())
        if node:
            node.setCustomProperty('showFeatureCount', True) 

        # ---------------------------------------------------------------------------
        # 9) Spalten "test_text" und "count_corners" anlegen und befüllen
        # ---------------------------------------------------------------------------
        print('M11: Layer: ' + str(layer))
        
        # Layer editieren (falls noch nicht im Bearbeitungsmodus)
        if not layer.isEditable():
            layer.startEditing()
        
        # Felder hinzufügen, falls sie noch nicht existieren
        field_names = [field.name() for field in layer.fields()]
        
        if "test_text" not in field_names:
            layer.dataProvider().addAttributes([QgsField("test_text", QVariant.String)])
        if "count_corners" not in field_names:
            layer.dataProvider().addAttributes([QgsField("count_nodes", QVariant.Int)])
        layer.updateFields()
        
        # Hilfsfunktion für zufälligen Text
        def random_string(length=30):
            myString = "Lorem ipsum dolor sit amet, consetetur sadipscing elitr"
            myStart = int(random.uniform(0,9))
            myLength = int(random.uniform(3,40))
            myEnd = myStart + myLength
            myString = (myString[myStart:myEnd]).lstrip()  # trimmen
            #print('myStart: ' + str(myStart) + '  myLength: ' + str(myLength) + '  myString: ' + myString)
            #return ''.join(random.choices(string.ascii_letters + string.digits, k=int(random.uniform(3,length))))
            return ''.join(myString)
            
        # Indexe der neuen Felder holen
        idx_text = layer.fields().indexFromName("test_text")
        print('M12: idx_text: ' + str(idx_text))
        idx_count = layer.fields().indexFromName("count_nodes")
        print('M13: idx_count: ' + str(idx_count))
        
        # Features durchlaufen und Felder füllen
        for feature in layer.getFeatures():
            geom = feature.geometry()
            
            # Alle Eckpunkte zählen (auch bei MultiPolygons)
            if geom.isMultipart():
                parts = geom.asMultiPolygon()
                point_count = sum([len(ring) for poly in parts for ring in poly])
            else:
                poly = geom.asPolygon()
                point_count = sum([len(ring) for ring in poly])
        
            #print('M14: point_count: ' + str(point_count))
            #point_count = point_count - 1
            #print('M15: point_count: ' + str(point_count) + ' <--')
            layer.changeAttributeValue(feature.id(), idx_text, random_string())
            layer.changeAttributeValue(feature.id(), idx_count, point_count)
            
        # Änderungen speichern
        layer.commitChanges()
        print("M16: items 'test_text' and 'count_nodes' were successfully filled.")

        # ---------------------------------------------------------------------------
        # 10) Zusammenfassung
        # ---------------------------------------------------------------------------
        print('M17: ' + f'{len(feats)} polygons created – thereof {invalid_count} with invalid geometries '
              f'({invalid_count/len(feats):.0%}).')
        # print(len(feats))
        myText = str(len(feats)) + ' polygons created – thereof ' + str(invalid_count) + ' with invalid geometries (=' + str(invalid_count/len(feats)*100) +'%)'
        self.iface.messageBar().pushMessage("RandomPolygons: ", myText ,3,3)

#############################################################################################################
        endtime = time.time()
        formatted_time = time.strftime("%y.%m.%d %H:%M:%S", time.localtime(endtime))
        print('+--- RandomPolygons: E N D ------- ' + str(formatted_time) + ' -------------------------------')


                



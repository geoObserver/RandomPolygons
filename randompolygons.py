import os
from PyQt5.QtWidgets import QAction, QMessageBox, QPushButton, QDialog, QVBoxLayout, QFormLayout, QLabel, QLineEdit, QSpinBox, QHBoxLayout
from PyQt5.QtGui import QIcon, QColor
from qgis.utils import iface
import time
####
from qgis.PyQt.QtWidgets import QInputDialog
from qgis.PyQt.QtCore    import QMetaType
from qgis.PyQt.QtGui     import QColor
from qgis.core import (
    QgsProject, QgsVectorLayer, QgsField, QgsPointXY,
    QgsFeature, QgsGeometry, QgsGeometryValidator,
    QgsFillSymbol, QgsSingleSymbolRenderer
)
import random


plugin_dir = os.path.dirname(__file__)

class MultiInputDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("RandomPolygons: Parameters ...")

        self.layout = QVBoxLayout(self)

        # Eingabefelder
        #self.name_input = QLineEdit(self)
        #self.age_input = QLineEdit(self)
        #self.alter_input = QSpinBox()
        #self.alter_input.setRange(0, 120)
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

        #self.layout.addWidget(QLabel("Name:"))
        #self.layout.addWidget(self.name_input)
        #self.layout.addWidget(QLabel("Age:"))
        #self.layout.addWidget(self.age_input)
        self.layout.addWidget(QLabel("Count of polygons [1 ... 2000]:"))
        self.layout.addWidget(self.count_polygons_input)
        self.layout.addWidget(QLabel(f"Max.{' ' * 2}corners per polygon [3 ... 20]:"))
        self.layout.addWidget(self.max_corners_input)
        self.layout.addWidget(QLabel(f"Max.{' ' * 2}NOT valid polygon [1 ... 50%]:"))
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
        
    def initGui(self):
        # Create an action (i.e. a button) with Logo
        icon = os.path.join(os.path.join(plugin_dir, 'logo.png'))
        self.action = QAction(QIcon(icon), 'RandomPolygons', self.iface.mainWindow())
        # Add the action to the toolbar
        self.iface.addToolBarIcon(self.action)
        # Connect the run() method to the action
        self.action.triggered.connect(self.run)
      
    def unload(self):
        self.iface.removeToolBarIcon(self.action)
        del self.action
        
    def run(self):
        starttime = time.time()
        formatted_time = time.strftime("%y.%m.%d %H:%M:%S", time.localtime(starttime))
        print('\n\n+--- RandomPolygons: S T A R T --- ' + str(formatted_time) + ' -------------------------------')

#############################################################################################################
        # ---------------------------------------------------------------------------
        # 1) Benutzer nach Parametern fragen
        # ---------------------------------------------------------------------------
        dialog = MultiInputDialog()
        if dialog.exec_():
            count_polygons, max_corners, max_notvalid_polygons, max_extent_polygons = dialog.getInputs()
            print("M1: count_polygons = ", count_polygons)
            print("M2: max_corners = ", max_corners)
            print("M3: max_notvalid_polygons = ", max_notvalid_polygons)
            print("M4: max_extent_polygons = ", max_extent_polygons)
        else:
            print('M0: Cancelled by user.')
            self.iface.messageBar().pushMessage("RandomPolygons: ", 'Cancelled by user.' ,3,3)
            return
        
        # ---------------------------------------------------------------------------
        # 2) Karten‑Parameter holen
        # ---------------------------------------------------------------------------
        canvas  = iface.mapCanvas()
        extent  = canvas.extent()
        crs     = canvas.mapSettings().destinationCrs()
        print('M6: Extent: ' + str(extent))
        print('M7: CRS: ' + str(crs))
        
        # Max. Breite/Höhe eines Polygons bezogen auf Kartenbreite/-höhe
        #max_w   = extent.width()  / 10.0
        #max_h   = extent.height() / 10.0
        max_w   = extent.width()  / 100 * (int(max_extent_polygons))
        max_h   = extent.height() / 100 * (int(max_extent_polygons))
        print('M8: max_w: ' + str(max_w))
        print('M9: max_h: ' + str(max_h))
        
        # ---------------------------------------------------------------------------
        # 3) Ziel‑Layer im Speicher anlegen
        # ---------------------------------------------------------------------------
        layer = QgsVectorLayer(f'Polygon?crs={crs.authid()}', 'RandomPolygons (' + str(formatted_time) + ')', 'memory')
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
            for _ in range(n_pts):
                dx = random.uniform(-max_w/2, max_w/2)
                dy = random.uniform(-max_h/2, max_h/2)
                pts.append(QgsPointXY(cx + dx, cy + dy))
                
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
        symbol.setColor(QColor(random.uniform(100,255), random.uniform(100,255), random.uniform(100,255), 50))  # Rot + 50 % Transparenz (Alpha=128)
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
        # 8) Zusammenfassung
        # ---------------------------------------------------------------------------
        print('M10: ' + f'{len(feats)} polygons created – thereof {invalid_count} with invalid geometries '
              f'({invalid_count/len(feats):.0%}).')
        # print(len(feats))
        myText = str(len(feats)) + ' polygons created – thereof ' + str(invalid_count) + ' with invalid geometries (=' + str(invalid_count/len(feats)*100) +'%)'
        self.iface.messageBar().pushMessage("RandomPolygons: ", myText ,3,3)

#############################################################################################################
        endtime = time.time()
        formatted_time = time.strftime("%y.%m.%d %H:%M:%S", time.localtime(endtime))
        print('+--- RandomPolygons: E N D ------- ' + str(formatted_time) + ' -------------------------------')


                



import os
import time
import random
import string

from qgis.PyQt.QtWidgets import (
    QAction, QMessageBox, QPushButton, QDialog, QVBoxLayout, QFormLayout,
    QLabel, QLineEdit, QSpinBox, QHBoxLayout, QToolBar
)
from qgis.PyQt.QtGui import QIcon, QColor
from qgis.PyQt.QtCore import QVariant
from qgis.utils import iface
from qgis.core import (
    Qgis, QgsProject, QgsVectorLayer, QgsField, QgsPointXY,
    QgsFeature, QgsGeometry, QgsGeometryValidator,
    QgsFillSymbol, QgsSingleSymbolRenderer, QgsLayerTreeGroup, QgsExpressionContextUtils
)

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
        self.layout.addWidget(QLabel("Max. corners per polygon [3 ... 20]:"))
        self.layout.addWidget(self.max_corners_input)
        self.layout.addWidget(QLabel("Max. count of NOT valid polygons [1 ... 50%]:"))
        self.layout.addWidget(self.max_notvalid_polygons_input)
        self.layout.addWidget(QLabel("Max. extent of a polygon in relation to canvas [10 ... 50%]:"))
        self.layout.addWidget(self.max_extent_polygons_input)

        # OK/Cancel
        self.ok_button = QPushButton("OK")
        self.cancel_button = QPushButton("Cancel")
        self.ok_button.clicked.connect(self.accept)
        self.cancel_button.clicked.connect(self.reject)
        self.layout.addWidget(self.ok_button)
        self.layout.addWidget(self.cancel_button)

        self.layout.addWidget(QLabel("RandomPolygons v0.3 (Qt6)"))

    def getInputs(self):
        return (
            self.count_polygons_input.text(),
            self.max_corners_input.text(),
            self.max_notvalid_polygons_input.text(),
            self.max_extent_polygons_input.text(),
        )

class RandomPolygons:
    def __init__(self, iface):
        self.iface = iface
        self.toolbar = None
        self.actions = []

    def initGui(self):
        # Prüfen, ob gemeinsame Toolbar schon existiert
        self.toolbar = self.iface.mainWindow().findChild(QToolBar, "#geoObserverTools")
        if not self.toolbar:
            self.toolbar = self.iface.addToolBar("#geoObserver Tools")
            self.toolbar.setObjectName("#geoObserverTools")
            self.toolbar.setToolTip("#geoObserver Tools ...")

        # Button/Aktion erstellen
        icon = os.path.join(plugin_dir, "logo.png")
        self.action = QAction(QIcon(icon), "RandomPolygons", self.iface.mainWindow())
        self.action.triggered.connect(self.run)

        # Aktion in gemeinsame Toolbar einfügen
        self.toolbar.addAction(self.action)
        self.actions.append(self.action)

    def unload(self):
        for action in self.actions:
            self.toolbar.removeAction(action)
        self.actions.clear()

    def run(self):
        starttime = time.time()
        formatted_time = time.strftime("%y.%m.%d %H:%M:%S", time.localtime(starttime))
        print(
            "\n\n+--- RandomPolygons: S T A R T --- "
            + str(formatted_time)
            + " -------------------------------"
        )

        # 1) Benutzer nach Parametern fragen
        dialog = MultiInputDialog()
        if dialog.exec():  # Qt6: exec() statt exec_()
            count_polygons, max_corners, max_notvalid_polygons, max_extent_polygons = (
                dialog.getInputs()
            )
            print(" M1: count_polygons = ", count_polygons)
            print(" M2: max_corners = ", max_corners)
            print(" M3: max_notvalid_polygons = ", max_notvalid_polygons)
            print(" M4: max_extent_polygons = ", max_extent_polygons)
        else:
            print(" M0: Cancelled by user.")
            self.iface.messageBar().pushMessage("RandomPolygons:", "Cancelled by user.", Qgis.Success, duration=3)
            return

        # 2) Karten-Parameter holen
        canvas = iface.mapCanvas()
        extent = canvas.extent()
        crs = canvas.mapSettings().destinationCrs()
        print(" M6: Extent: " + str(extent))
        print(" M7: CRS: " + str(crs))

        max_w = extent.width() / 100 * (int(max_extent_polygons))
        max_h = extent.height() / 100 * (int(max_extent_polygons))
        print(" M8: max_w: " + str(max_w))
        print(" M9: max_h: " + str(max_h))

        # 3) Ziel-Layer im Speicher anlegen
        layername = "RandomPolygons (" + str(formatted_time) + ")"
        print("M10: Layername: " + layername)
        layer = QgsVectorLayer(f"Polygon?crs={crs.authid()}", layername, "memory")
        prov = layer.dataProvider()
        prov.addAttributes([QgsField("id", QVariant.Int)])
        layer.updateFields()

        # 4) Hilfsfunktionen
        def random_polygon(ext, max_w, max_h):
            cx = random.uniform(ext.xMinimum(), ext.xMaximum())
            cy = random.uniform(ext.yMinimum(), ext.yMaximum())

            n_pts = random.randint(3, int(max_corners))
            pts = []
            for _ in range(n_pts):
                dx = random.uniform(-max_w / 2, max_w / 2)
                dy = random.uniform(-max_h / 2, max_h / 2)
                pts.append(QgsPointXY(cx + dx, cy + dy))

            random.shuffle(pts)
            if random.random() < 0.3:
                pts.insert(random.randrange(len(pts)), random.choice(pts))

            if pts[0] != pts[-1]:
                pts.append(pts[0])

            return QgsGeometry.fromPolygonXY([pts])

        def is_valid(geom: QgsGeometry) -> bool:
            if hasattr(geom, "isGeosValid"):
                return geom.isGeosValid()
            return len(QgsGeometryValidator.validateGeometry(geom)) == 0

        # 5) Polygone erzeugen
        invalid_target = int(max_notvalid_polygons) / 100
        invalid_limit = int(int(count_polygons) * invalid_target)
        invalid_count = 0
        feats = []
        tries = 0
        max_tries = 100000

        while len(feats) < int(count_polygons) and tries < max_tries:
            tries += 1
            geom = random_polygon(extent, max_w, max_h)
            valid = is_valid(geom)

            if valid or invalid_count < invalid_limit:
                feat = QgsFeature()
                feat.setAttributes([len(feats) + 1])
                feat.setGeometry(geom)
                feats.append(feat)
                if not valid:
                    invalid_count += 1

        if len(feats) < int(count_polygons):
            print("M9: Abbruch: zu viele Fehlversuche (max_tries erreicht)")
            return

        prov.addFeatures(feats)
        layer.updateExtents()
        QgsProject.instance().addMapLayer(layer)

        # 6) Symbolisierung
        symbol = QgsFillSymbol.createSimple(
            {"outline_color": "0,0,0", "outline_width": "0.4"}
        )
        symbol.setColor(
            QColor(
                int(random.uniform(100, 255)),
                int(random.uniform(100, 255)),
                int(random.uniform(100, 255)),
                50,
            )
        )
        renderer = QgsSingleSymbolRenderer(symbol)
        layer.setRenderer(renderer)
        layer.triggerRepaint()

        # 7) Feature-Zähler
        node = QgsProject.instance().layerTreeRoot().findLayer(layer.id())
        if node:
            node.setCustomProperty("showFeatureCount", True)

        # 9) Zusatzfelder befüllen
        print("M11: Layer: " + str(layer))

        if not layer.isEditable():
            layer.startEditing()

        field_names = [field.name() for field in layer.fields()]
        if "test_text" not in field_names:
            layer.dataProvider().addAttributes([QgsField("test_text", QVariant.String)])
        if "count_nodes" not in field_names:
            layer.dataProvider().addAttributes([QgsField("count_nodes", QVariant.Int)])
        layer.updateFields()

        def random_string(length=30):
            myString = "Lorem ipsum dolor sit amet, consetetur sadipscing elitr"
            myStart = int(random.uniform(0, 9))
            myLength = int(random.uniform(3, 40))
            myEnd = myStart + myLength
            myString = (myString[myStart:myEnd]).lstrip()
            return "".join(myString)

        idx_text = layer.fields().indexFromName("test_text")
        idx_count = layer.fields().indexFromName("count_nodes")

        for feature in layer.getFeatures():
            geom = feature.geometry()
            if geom.isMultipart():
                parts = geom.asMultiPolygon()
                point_count = sum([len(ring) for poly in parts for ring in poly])
            else:
                poly = geom.asPolygon()
                point_count = sum([len(ring) for ring in poly])

            layer.changeAttributeValue(feature.id(), idx_text, random_string())
            layer.changeAttributeValue(feature.id(), idx_count, point_count)

        layer.commitChanges()
        print("M16: items 'test_text' and 'count_nodes' were successfully filled.")

        # 10) Zusammenfassung
        print(
            "M17: "
            + f"{len(feats)} polygons created – thereof {invalid_count} with invalid geometries "
            f"({invalid_count/len(feats):.0%})."
        )
        myText = (
            str(len(feats))
            + " polygons created – thereof "
            + str(invalid_count)
            + " with invalid geometries (="
            + str(invalid_count / len(feats) * 100)
            + "%)"
        )
        self.iface.messageBar().pushMessage("RandomPolygons:", myText, Qgis.Success, duration=3)
		
        endtime = time.time()
        formatted_time = time.strftime("%y.%m.%d %H:%M:%S", time.localtime(endtime))
        print(
            "+--- RandomPolygons: E N D ------- "
            + str(formatted_time)
            + " -------------------------------"
        )
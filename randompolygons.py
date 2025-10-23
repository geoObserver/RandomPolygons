import os
import time
import random
from qgis.PyQt.QtWidgets import (
    QAction, QDialog, QVBoxLayout, QLabel, QSpinBox, QHBoxLayout,
    QPushButton, QToolBar, QSlider, QProgressBar
)
from qgis.PyQt.QtGui import QIcon, QColor
from qgis.PyQt.QtCore import QVariant, Qt, QCoreApplication
from qgis.utils import iface
from qgis.core import (
    Qgis, QgsProject, QgsVectorLayer, QgsField, QgsPointXY,
    QgsFeature, QgsGeometry, QgsGeometryValidator,
    QgsFillSymbol, QgsSingleSymbolRenderer
)

plugin_dir = os.path.dirname(__file__)

# Wortliste für pseudo-Lorem-Zufallstexte
LOREM_WORDS = [
    "lorem", "ipsum", "dolor", "sit", "amet", "consetetur",
    "sadipscing", "elitr", "sed", "diam", "nonumy", "eirmod",
    "tempor", "invidunt", "ut", "labore", "et", "dolore",
    "magna", "aliquyam"
]


class MultiInputDialog(QDialog):
    """Dialog mit Slider + SpinBox für Parameterwahl"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("RandomPolygons: Choose your parameters ...")
        self.setFixedWidth(400)  # Fixe Breite

        self.layout = QVBoxLayout(self)

        # --- Hilfsfunktion: Slider + SpinBox ---
        def add_slider_spinbox(label_text, min_val, max_val, default_val, step):
            label = QLabel(f"{label_text}")
            try:
                orientation = Qt.Orientation.Horizontal  # Qt6
            except AttributeError:
                orientation = Qt.Horizontal  # Qt5

            slider = QSlider(orientation)
            slider.setRange(min_val, max_val)
            slider.setSingleStep(step)
            slider.setPageStep(step)
            slider.setValue(default_val)

            spin = QSpinBox()
            spin.setRange(min_val, max_val)
            spin.setValue(default_val)

            slider.valueChanged.connect(spin.setValue)
            spin.valueChanged.connect(slider.setValue)
            slider.valueChanged.connect(lambda val: label.setText(f"{label_text}"))

            h_layout = QHBoxLayout()
            h_layout.addWidget(slider)
            h_layout.addWidget(spin)

            self.layout.addWidget(label)
            self.layout.addLayout(h_layout)
            return spin

        # Eingabeparameter
        self.count_polygons_input = add_slider_spinbox("Count of polygons [1 ... 2000]:", 1, 2000, 1000, 100)
        self.max_corners_input = add_slider_spinbox("Max. corners per polygon [3 ... 20]:", 3, 20, 10, 5)
        self.max_notvalid_polygons_input = add_slider_spinbox("Max. count of NOT valid polygons [% 1 ... 50]:", 1, 50, 10, 10)
        self.max_extent_polygons_input = add_slider_spinbox("Max. extent of a polygon [% 10 ... 50]:", 10, 50, 10, 10)

        # OK / Cancel Buttons nebeneinander
        self.ok_button = QPushButton("OK")
        self.cancel_button = QPushButton("Cancel")
        self.ok_button.clicked.connect(self.accept)
        self.cancel_button.clicked.connect(self.reject)

        button_layout = QHBoxLayout()
        button_layout.addStretch()  # schiebt Buttons nach rechts
        button_layout.addWidget(self.ok_button)
        button_layout.addWidget(self.cancel_button)
        self.layout.addLayout(button_layout)

        self.layout.addWidget(QLabel("RandomPolygons v0.4 (Qt6-compatible)"))

    def getInputs(self):
        return (
            self.count_polygons_input.value(),
            self.max_corners_input.value(),
            self.max_notvalid_polygons_input.value(),
            self.max_extent_polygons_input.value(),
        )


class RandomPolygons:
    """Hauptklasse des Plugins"""
    def __init__(self, iface):
        self.iface = iface
        self.toolbar = None
        self.actions = []
        self.progress_bar = None

    def initGui(self):
        self.toolbar = self.iface.mainWindow().findChild(QToolBar, "#geoObserverTools")
        if not self.toolbar:
            self.toolbar = self.iface.addToolBar("#geoObserverTools")
            self.toolbar.setObjectName("#geoObserverTools")
            self.toolbar.setWindowTitle("#geoObserverTools")
            self.toolbar.setToolTip("#geoObserverTools – geoObserver plugin tools")

        icon = os.path.join(plugin_dir, "logo.png")
        self.action = QAction(QIcon(icon), "RandomPolygons", self.iface.mainWindow())
        self.action.setToolTip("Generate random polygons on the current map extent.")
        self.action.triggered.connect(self.run)
        self.toolbar.addAction(self.action)
        self.actions.append(self.action)

    def unload(self):
        for action in self.actions:
            self.toolbar.removeAction(action)
        self.actions.clear()

    def run(self):
        starttime = time.time()
        print(f"\n\n+--- RandomPolygons START --- {time.strftime('%y.%m.%d %H:%M:%S')} ---")

        dialog = MultiInputDialog()
        if not dialog.exec():
            self.iface.messageBar().pushMessage("RandomPolygons:", "Cancelled by user.", Qgis.Info, duration=3)
            return

        count_polygons, max_corners, max_notvalid_polygons, max_extent_polygons = dialog.getInputs()
        print("M1: count_polygons =", count_polygons)
        print("M2: max_corners =", max_corners)
        print("M3: max_notvalid_polygons =", max_notvalid_polygons)
        print("M4: max_extent_polygons =", max_extent_polygons)

        canvas = iface.mapCanvas()
        extent = canvas.extent()
        crs = canvas.mapSettings().destinationCrs()
        print("M6: Extent:", extent)
        print("M7: CRS:", crs)

        max_w = extent.width() / 100 * max_extent_polygons
        max_h = extent.height() / 100 * max_extent_polygons
        print("M8: max_w:", max_w)
        print("M9: max_h:", max_h)

        layername = f"RandomPolygons ({time.strftime('%y.%m.%d %H:%M:%S')})"
        layer = QgsVectorLayer(f"Polygon?crs={crs.authid()}", layername, "memory")
        prov = layer.dataProvider()
        prov.addAttributes([
            QgsField("id", QVariant.Int),
            QgsField("test_text", QVariant.String),
            QgsField("count_nodes", QVariant.Int)
        ])
        layer.updateFields()

        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximum(count_polygons)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.iface.mainWindow().statusBar().addWidget(self.progress_bar)

        def random_polygon(ext):
            cx = random.uniform(ext.xMinimum(), ext.xMaximum())
            cy = random.uniform(ext.yMinimum(), ext.yMaximum())
            n_pts = random.randint(3, max_corners)
            pts = [QgsPointXY(cx + random.uniform(-max_w / 2, max_w / 2),
                              cy + random.uniform(-max_h / 2, max_h / 2))
                   for _ in range(n_pts)]
            pts.append(pts[0])
            return QgsGeometry.fromPolygonXY([pts])

        def is_valid(geom):
            if hasattr(geom, "isGeosValid"):
                return geom.isGeosValid()
            return len(QgsGeometryValidator.validateGeometry(geom)) == 0

        def random_string():
            return " ".join(random.choices(LOREM_WORDS, k=random.randint(4, 12)))

        feats = []
        invalid_count = 0
        max_tries = 100000
        tries = 0
        invalid_limit = int(count_polygons * (max_notvalid_polygons / 100))

        while len(feats) < count_polygons and tries < max_tries:
            tries += 1
            geom = random_polygon(extent)
            valid = is_valid(geom)
            if valid or invalid_count < invalid_limit:
                feat = QgsFeature()
                feat.setAttributes([len(feats) + 1, random_string(), 0])
                feat.setGeometry(geom)
                feats.append(feat)
                if not valid:
                    invalid_count += 1
                self.progress_bar.setValue(len(feats))
                if len(feats) % 50 == 0:
                    QCoreApplication.processEvents()

        prov.addFeatures(feats)
        layer.updateExtents()
        QgsProject.instance().addMapLayer(layer)

        idx_count = layer.fields().indexFromName("count_nodes")
        layer.startEditing()
        for f in layer.getFeatures():
            geom = f.geometry()
            if geom.isMultipart():
                parts = geom.asMultiPolygon()
                point_count = sum([len(ring) for poly in parts for ring in poly])
            else:
                poly = geom.asPolygon()
                point_count = sum([len(ring) for ring in poly])
            layer.changeAttributeValue(f.id(), idx_count, point_count)
        layer.commitChanges()

        symbol = QgsFillSymbol.createSimple({"outline_color": "0,0,0", "outline_width": "0.4"})
        symbol.setColor(QColor(
            int(random.uniform(100, 255)),
            int(random.uniform(100, 255)),
            int(random.uniform(100, 255)),
            50,
        ))
        layer.setRenderer(QgsSingleSymbolRenderer(symbol))

        # 7) Feature-Zähler
        node = QgsProject.instance().layerTreeRoot().findLayer(layer.id())
        if node:
            node.setCustomProperty("showFeatureCount", True)

        self.iface.mainWindow().statusBar().removeWidget(self.progress_bar)
        self.progress_bar = None

        msg = (f"{len(feats)} polygons created – "
               f"{invalid_count} invalid ({invalid_count / len(feats) * 100:.1f}%)")
        self.iface.messageBar().pushMessage("RandomPolygons:", msg, Qgis.Success, duration=4)

        print(f"M17: {len(feats)} polygons created – thereof {invalid_count} with invalid geometries "
              f"({invalid_count/len(feats):.0%}).")
        print(f"+--- RandomPolygons END --- {time.strftime('%y.%m.%d %H:%M:%S')} ---")

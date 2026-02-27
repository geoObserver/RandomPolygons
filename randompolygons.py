# -----------------------------------------------------------------------------#
# Title:       RandomPolygons                                                  #
# Author:      Mike Elstermann (#geoObserver)                                  #
# Version:     v0.5                                                            #
# Created:     15.10.2025                                                      #
# Last Change: 27.02.2026                                                      #
# see also:    https://geoobserver.de/qgis-plugins/                            #
#                                                                              #
# This file contains code generated with assistance from an AI                 #
# No warranty is provided for AI-generated portions.                           #
# Human review and modification performed by: Mike Elstermann (#geoObserver)   #
# -----------------------------------------------------------------------------#

import os
import time
import random

from qgis.PyQt.QtWidgets import (
    QAction, QDialog, QVBoxLayout, QLabel, QSpinBox, QHBoxLayout,
    QPushButton, QToolBar, QSlider, QProgressBar
)
from qgis.PyQt.QtGui import QIcon, QColor
from qgis.PyQt.QtCore import QVariant, Qt, QCoreApplication
from qgis.core import (
    Qgis, QgsProject, QgsVectorLayer, QgsField, QgsPointXY,
    QgsFeature, QgsGeometry, QgsGeometryValidator,
    QgsFillSymbol, QgsSingleSymbolRenderer
)
from qgis.utils import iface
import processing

plugin_dir = os.path.dirname(__file__)

LOREM_WORDS = [
    "lorem", "ipsum", "dolor", "sit", "amet", "consetetur",
    "sadipscing", "elitr", "sed", "diam", "nonumy", "eirmod",
    "tempor", "invidunt", "ut", "labore", "et", "dolore",
    "magna", "aliquyam"
]

# -----------------------------------------------------------------------------#
# Qt5/Qt6-kompatible Enums
# -----------------------------------------------------------------------------#
from qgis.PyQt import QtCore

try:
    ORIENTATION_HORIZONTAL = Qt.Orientation.Horizontal  # Qt6
except AttributeError:
    ORIENTATION_HORIZONTAL = Qt.Horizontal  # Qt5

try:
    TEXT_BROWSER_INTERACTION = Qt.TextBrowserInteraction  # Qt5
except AttributeError:
    TEXT_BROWSER_INTERACTION = QtCore.Qt.TextInteractionFlag.TextBrowserInteraction  # Qt6

# -----------------------------------------------------------------------------#
# Dialog mit Parametern
# -----------------------------------------------------------------------------#
class MultiInputDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("RandomPolygons: Choose your parameters …")
        self.setFixedWidth(420)
        self.layout = QVBoxLayout(self)

        def add_slider_spinbox(label_text, min_val, max_val, default_val, step):
            label = QLabel(label_text)
            slider = QSlider(ORIENTATION_HORIZONTAL)
            slider.setRange(min_val, max_val)
            slider.setSingleStep(step)
            slider.setPageStep(step)
            slider.setValue(default_val)

            spin = QSpinBox()
            spin.setRange(min_val, max_val)
            spin.setValue(default_val)

            slider.valueChanged.connect(spin.setValue)
            spin.valueChanged.connect(slider.setValue)

            h_layout = QHBoxLayout()
            h_layout.addWidget(slider)
            h_layout.addWidget(spin)

            self.layout.addWidget(label)
            self.layout.addLayout(h_layout)
            return spin

        # --- Parameter-Slider ---
        self.count_polygons_input = add_slider_spinbox(
            "Count of polygons [1 … 2000]:", 1, 2000, 100, 100
        )
        self.max_corners_input = add_slider_spinbox(
            "Max. corners per polygon [3 … 20]:", 3, 20, 10, 1
        )
        self.max_notvalid_polygons_input = add_slider_spinbox(
            "Max. count of NOT valid polygons [% 1 … 50]:", 1, 50, 10, 5
        )
        self.max_extent_polygons_input = add_slider_spinbox(
            "Max. extent of a polygon [% 10 … 50]:", 10, 50, 20, 5
        )

        self.layout.addWidget(QLabel("———————————————————————————————————————————————"))

        self.generalize_input = add_slider_spinbox(
            "Generalization strength [0 … 100]:", 0, 100, 10, 5
        )

        self.smooth_iter_input = add_slider_spinbox(
            "Smoothing iterations [0 … 5]:", 0, 5, 2, 1
        )
        self.smooth_offset_input = add_slider_spinbox(
            "Smoothing offset [0 … 50]:", 0, 50, 10, 5
        )

        # --- OK/Cancel Buttons ---
        self.ok_button = QPushButton("OK")
        self.cancel_button = QPushButton("Cancel")
        self.ok_button.clicked.connect(self.accept)
        self.cancel_button.clicked.connect(self.reject)

        button_layout = QHBoxLayout()
        button_layout.addStretch()
        button_layout.addWidget(self.ok_button)
        button_layout.addWidget(self.cancel_button)
        self.layout.addLayout(button_layout)

        # --- Info Label mit klickbarem Link ---
        info_label = QLabel(
            '<b>RandomPolygons v0.5 by #geoObserver</b><br>'
            'more: <a href="https://geoobserver.de/qgis-plugins/" style="color:#0055FF;">geoobserver.de</a>'
        )
        info_label.setOpenExternalLinks(True)
        info_label.setTextInteractionFlags(TEXT_BROWSER_INTERACTION)
        self.layout.addWidget(info_label)

    def getInputs(self):
        return (
            self.count_polygons_input.value(),
            self.max_corners_input.value(),
            self.max_notvalid_polygons_input.value(),
            self.max_extent_polygons_input.value(),
            self.generalize_input.value(),
            self.smooth_iter_input.value(),
            self.smooth_offset_input.value(),
        )

# -----------------------------------------------------------------------------#
# Hauptklasse RandomPolygons
# -----------------------------------------------------------------------------#
class RandomPolygons:
    def __init__(self, iface):
        self.iface = iface
        self.toolbar = None
        self.actions = []
        self.progress_bar = None

    def initGui(self):
        self.toolbar = self.iface.mainWindow().findChild(QToolBar, "geoObserverTools")
        if not self.toolbar:
            self.toolbar = self.iface.addToolBar("geoObserverTools")
            self.toolbar.setObjectName("geoObserverTools")

        icon = os.path.join(plugin_dir, "logo.png")
        self.action = QAction(QIcon(icon), "RandomPolygons", self.iface.mainWindow())
        self.action.triggered.connect(self.run)
        self.toolbar.addAction(self.action)
        self.actions.append(self.action)

    def unload(self):
        for action in self.actions:
            self.toolbar.removeAction(action)
        self.actions.clear()

    def run(self):
        starttime = time.time()
        print(f"\n\n+--- RandomPolygons START --- {time.strftime('%H:%M:%S', time.localtime(starttime))}")

        dialog = MultiInputDialog()
        if not dialog.exec():
            self.iface.messageBar().pushMessage(
                "RandomPolygons", "Cancelled by user", Qgis.Info, duration=3
            )
            return

        (
            count_polygons,
            max_corners,
            max_notvalid_polygons,
            max_extent_polygons,
            generalize_strength,
            smooth_iterations,
            smooth_offset_raw,
        ) = dialog.getInputs()

        canvas = iface.mapCanvas()
        extent = canvas.extent()
        crs = canvas.mapSettings().destinationCrs()
        max_w = extent.width() / 100 * max_extent_polygons
        max_h = extent.height() / 100 * max_extent_polygons

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

        # --- Polygonerzeugung ---
        feats = []
        invalid_count = 0
        max_tries = 100000
        tries = 0
        invalid_limit = int(count_polygons * (max_notvalid_polygons / 100))
        print(f"+    Generating ...")

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

        # --- Generalize + Smooth ---
        tolerance = (extent.width() + extent.height()) / 2 * (generalize_strength / 1000)
        smooth_offset = smooth_offset_raw / 100.0

        if generalize_strength > 0 or smooth_iterations > 0:
            print(f"+    Generalizing/Smoothing ...")
            layer.startEditing()
            all_feats_list = list(layer.getFeatures())
            for i, f in enumerate(all_feats_list, 1):
                geom = f.geometry()

                if generalize_strength > 0 and tolerance > 0:
                    temp_layer = QgsVectorLayer(
                        f"Polygon?crs={layer.crs().authid()}", "temp_simpl", "memory"
                    )
                    temp_layer.dataProvider().addFeatures([f])
                    temp_layer.updateExtents()
                    res_simp = processing.run("native:simplifygeometries", {
                        "INPUT": temp_layer,
                        "METHOD": 0,
                        "TOLERANCE": tolerance,
                        "OUTPUT": "memory:"
                    })
                    geom = next(res_simp["OUTPUT"].getFeatures()).geometry()

                if smooth_iterations > 0 and smooth_offset > 0:
                    temp_layer2 = QgsVectorLayer(
                        f"Polygon?crs={layer.crs().authid()}", "temp_smooth", "memory"
                    )
                    temp_feat = QgsFeature()
                    temp_feat.setGeometry(geom)
                    temp_layer2.dataProvider().addFeatures([temp_feat])
                    temp_layer2.updateExtents()
                    res_smooth = processing.run("native:smoothgeometry", {
                        "INPUT": temp_layer2,
                        "ITERATIONS": smooth_iterations,
                        "OFFSET": smooth_offset,
                        "OUTPUT": "memory:"
                    })
                    geom = next(res_smooth["OUTPUT"].getFeatures()).geometry()

                layer.changeGeometry(f.id(), geom)
                self.progress_bar.setValue(i)
            layer.commitChanges()

        # --- count_nodes aktualisieren ---
        idx_count = layer.fields().indexFromName("count_nodes")
        layer.startEditing()
        for f in layer.getFeatures():
            geom = f.geometry()
            if geom.isMultipart():
                parts = geom.asMultiPolygon()
                pc = sum(len(ring) for poly in parts for ring in poly)
            else:
                poly = geom.asPolygon()
                pc = sum(len(ring) for ring in poly)
            layer.changeAttributeValue(f.id(), idx_count, pc)
        layer.commitChanges()

        # --- Styling ---
        symbol = QgsFillSymbol.createSimple({"outline_color": "0,0,0", "outline_width": "0.4"})
        symbol.setColor(QColor(
            random.randint(100, 255),
            random.randint(100, 255),
            random.randint(100, 255),
            50
        ))
        layer.setRenderer(QgsSingleSymbolRenderer(symbol))

        node = QgsProject.instance().layerTreeRoot().findLayer(layer.id())
        if node:
            node.setCustomProperty("showFeatureCount", True)

        self.iface.mainWindow().statusBar().removeWidget(self.progress_bar)
        self.progress_bar = None

        self.iface.messageBar().pushMessage(
            "RandomPolygons",
            f"{len(feats)} polygons created – {invalid_count} invalid "
            f"({invalid_count/len(feats)*100:.1f}%)",
            Qgis.Success, duration=5
        )
        print(f"+--- RandomPolygons END ----- {time.strftime('%H:%M:%S', time.localtime(time.time()))}")
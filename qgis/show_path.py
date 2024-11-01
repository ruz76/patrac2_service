from qgis.core import (
    QgsPointXY, QgsGeometry, QgsFeature, QgsVectorLayer, QgsProject, QgsLineString
)
from qgis.PyQt.QtGui import QColor
from qgis.core import QgsSimpleLineSymbolLayer, QgsRendererCategory, QgsCategorizedSymbolRenderer, QgsSymbol
import json
import time

with open("/data/patracdata/service/data/98c46f06-58fa-43ad-adcd-09cc04e7648f/2883069_solution.json") as pp:
    data = json.load(pp)

print(data)

# Vytvoření vektorové vrstvy pro uchování linie
layer = QgsVectorLayer("LineString?crs=EPSG:4326", "Line Layer", "memory")

# Přidání vrstvy do mapového projektu
QgsProject.instance().addMapLayer(layer)

# Vytvoření stylu pro linii
symbol = QgsSymbol.defaultSymbol(layer.geometryType())
symbol_layer = QgsSimpleLineSymbolLayer()
symbol_layer.setColor(QColor("red"))  # Nastavení barvy čáry
symbol_layer.setWidth(0.5)  # Nastavení tloušťky čáry
symbol.changeSymbolLayer(0, symbol_layer)

# Aplikace stylu na vrstvu
renderer = layer.renderer()
renderer.setSymbol(symbol)


for ring in data['rings']:
    for i in range(len(ring['coordinates']) - 1):
        # Přidání linie do vrstvy
        pr = layer.dataProvider()
        feature = QgsFeature()

        # Definice bodů (souřadnice X, Y)
        point1 = QgsPointXY(ring['coordinates'][i][0], ring['coordinates'][i][1])
        point2 = QgsPointXY(ring['coordinates'][i+1][0], ring['coordinates'][i+1][1])

        # Vytvoření linie mezi těmito dvěma body
        line = QgsGeometry.fromPolylineXY([point1, point2])

        feature.setGeometry(line)
        pr.addFeatures([feature])


layer.triggerRepaint()

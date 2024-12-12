from qgis.core import (
    QgsPointXY, QgsGeometry, QgsFeature, QgsVectorLayer, QgsProject, QgsLineString, QgsField
)
from qgis.PyQt.QtGui import QColor
from qgis.core import QgsSimpleLineSymbolLayer, QgsRendererCategory, QgsCategorizedSymbolRenderer, QgsSymbol
import json
from PyQt5.QtCore import QVariant, QDateTime
from datetime import datetime, timedelta

with open("/media/jencek/Elements1/patrac/patracdata_patrac2/service/data/cf3d7f48-5691-4f3c-9174-4f7351f8795b/1228436_solution.json") as pp:
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

current_time = datetime.now()  # Aktuální čas

pos = 0
time_shift = 0
for ring in data['rings']:
    for i in range(len(ring['coordinates']) - 1):
        # Přidání linie do vrstvy
        pr = layer.dataProvider()

        if not layer.fields().names():
            pr.addAttributes([
                QgsField("id", QVariant.Int),
                QgsField("start_time", QVariant.DateTime),
                QgsField("end_time", QVariant.DateTime)
            ])
            layer.updateFields()

        feature = QgsFeature()

        # Definice bodů (souřadnice X, Y)
        point1 = QgsPointXY(ring['coordinates'][i][0], ring['coordinates'][i][1])
        point2 = QgsPointXY(ring['coordinates'][i+1][0], ring['coordinates'][i+1][1])

        # Vytvoření linie mezi těmito dvěma body
        line = QgsGeometry.fromPolylineXY([point1, point2])
        feature.setGeometry(line)

        # Nastavení atributů
        start_time = current_time + timedelta(seconds=time_shift)
        time_shift += round(line.length() * 20000)
        end_time = current_time + timedelta(seconds=time_shift)

        # Konverze času na QDateTime
        qgis_start_time = QDateTime.fromString(start_time.strftime('%Y-%m-%d %H:%M:%S'), 'yyyy-MM-dd HH:mm:ss')
        qgis_end_time = QDateTime.fromString(end_time.strftime('%Y-%m-%d %H:%M:%S'), 'yyyy-MM-dd HH:mm:ss')
        feature.setAttributes([
            pos,
            qgis_start_time,
            qgis_end_time
        ])

        pr.addFeatures([feature])

        pos += 1
    break

layer.triggerRepaint()

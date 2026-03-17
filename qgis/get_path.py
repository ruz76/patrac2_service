import json
import urllib.request

from qgis.core import (
    QgsVectorLayer,
    QgsFeature,
    QgsGeometry,
    QgsPointXY,
    QgsProject,
    QgsField
)

from PyQt5.QtCore import QVariant


url = "http://localhost:5000/calculate_path_search"

payload = {
  "search_id": "bf67ec10-2102-424f-aedd-5d068a6e922a",
  "unit_type": "handler",
  "coordinates": [
    [15.51449,49.28418],
    [15.516798,49.270967]
  ]
}

# Sever 15.519,49.29938
# Jih 15.516798,49.270967
# Exclude "segments_exclude": [1098744, 10000043, 10000046, 10000049, 10000051, 634027, 634028, 1098675, 1098676, 1098677, 1098678, 1098679, 1098680, 1098681, 1098682, 1098683, 1098747, 1098746, 1098745, 1098744]
# "segments_exclude": [1433224, 10000045, 10000047, 10000048, 10000048, 10000047, 10000044, 10000044, 10000045, 1433225, 1433226, 1433157, 1433156, 1433155, 4602210, 4602210, 4602366, 4602367, 4602367, 3589700, 1433189, 1433190, 1433190, 1433189, 3589701, 4602365, 1832260, 579205, 579204, 579203, 579202, 579201, 1433175, 4602257, 4602256, 4602248, 4602247, 4602247, 4602248, 4602246, 4602245, 4602245, 4602244, 1433229, 1433230, 1098438, 1098437, 1098436, 1098436, 1098437, 4602189, 4602189, 1098438, 1433231, 1433232, 1098444, 1098443, 1098443, 1098444, 1433233, 1433234, 1433235, 1098428, 1098427, 1098427, 1098428, 1433236, 1433237, 1433238, 1433239, 1433240, 4602209, 10000050, 10000050, 4602209, 1433240, 1433239, 1098424, 3985510, 3985511, 3985511, 3985510, 1098425, 1098426, 1098426, 1098425, 1098424, 1433238, 1433237, 1098429, 1098430, 1098431, 1098432, 1098433, 1098433, 1098432, 1832257, 1832256, 1832256, 1832257, 1098431, 1098439, 1098440, 1098441, 1098442, 1098435, 1098435, 1098434, 1433229, 4602242, 4602243, 147432, 147431, 1094299, 1094300, 1094288, 1087584, 1087585, 3427831, 3427831, 1087585, 1087584, 1094289, 1094290, 1094291, 3427837, 3427836, 3427835, 3427834, 4602224, 4602223, 4602188, 4602187, 4602185, 4602185, 4602183, 4602182, 4602181, 1087572, 2594812, 2594808, 2594807, 4602184, 2594819, 2594818, 2594818, 3188964, 3188965, 3188967, 3188968, 3428129, 1083904, 1083905, 4602192, 4602193, 3968786, 3968787, 3968788, 3968790, 3968789, 2175569, 4602200, 4602201, 4602201, 4602203, 4602204, 4602206, 1227154, 1227154, 4602206, 4602204, 4602203, 4602200, 2175569, 2175568, 4602199, 4602202, 4602195, 4602194, 3968785, 3968786, 4602193, 4602192, 1083905, 1083904, 3428129, 3428128, 3428127, 3428126, 4602196, 10000014, 10000013, 634029, 1227153, 1227153, 634030, 634031, 3053355, 3053356, 3053357, 1098711, 1098712, 1098713, 4602402, 4602403, 4602403, 1433174, 1433173, 1433173, 1433174, 4602402, 4602404, 2175570, 2175571, 2175572, 1433195, 1433196, 1433196, 1433195, 2175573, 1433202, 1433203, 1433204, 4602408, 4602409, 4602410, 4602413, 1098749, 10000058, 10000059, 10000059, 10000057, 10000054, 10000056, 10000056, 10000055, 3967066, 3967067, 3967067, 3967066, 10000055, 10000053, 10000053, 10000054, 10000057, 10000058, 1098748, 1433218, 1433219, 1098633, 1098634, 1098634, 1098633, 1433220, 1433221, 1433222, 1433223]

data = json.dumps(payload).encode("utf-8")

req = urllib.request.Request(
    url,
    data=data,
    headers={"Content-Type": "application/json"},
    method="POST"
)

response = urllib.request.urlopen(req)
result = json.loads(response.read().decode("utf-8"))

with open("/tmp/current_result.json", "w") as rout:
    rout.write(json.dumps(result))

search = result["search_path"]


# -------------------------------------------------
# BODY UŽIVATELE
# -------------------------------------------------

user_layer = QgsVectorLayer("Point?crs=EPSG:4326", "user_points", "memory")
pr = user_layer.dataProvider()

pr.addAttributes([
    QgsField("type", QVariant.String)
])

user_layer.updateFields()

features = []

for ptype, coords in [
    ("start_user", search["start_point_user"]),
    ("end_user", search["end_point_user"])
]:

    f = QgsFeature(user_layer.fields())
    f.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(coords[0],coords[1])))
    f["type"] = ptype
    features.append(f)

pr.addFeatures(features)

QgsProject.instance().addMapLayer(user_layer)


# -------------------------------------------------
# ALTERNATIVY
# -------------------------------------------------

for i, alt in enumerate(search["search_path_alternatives"], start=1):

    # ---------- BODY ----------

    points_layer = QgsVectorLayer(
        "Point?crs=EPSG:4326",
        f"alt_{i}_points",
        "memory"
    )

    pr = points_layer.dataProvider()

    pr.addAttributes([
        QgsField("type", QVariant.String),
        QgsField("node_id", QVariant.Int)
    ])

    points_layer.updateFields()

    features = []

    for ptype, data_pt in [
        ("start_network", alt["start_point_network"]),
        ("end_network", alt["end_point_network"])
    ]:

        f = QgsFeature(points_layer.fields())

        coords = data_pt["coordinates"]

        f.setGeometry(QgsGeometry.fromPointXY(
            QgsPointXY(coords[0],coords[1])
        ))

        f["type"] = ptype
        f["node_id"] = data_pt["id"]

        features.append(f)

    pr.addFeatures(features)

    QgsProject.instance().addMapLayer(points_layer)


    # ---------- LINIE ----------

    lines_layer = QgsVectorLayer(
        "LineString?crs=EPSG:4326",
        f"alt_{i}_rings",
        "memory"
    )

    pr = lines_layer.dataProvider()

    pr.addAttributes([
        QgsField("ring_id", QVariant.String),
        QgsField("total_roads", QVariant.Int),
        QgsField("total_path", QVariant.Int),
        QgsField("duplicate_len", QVariant.Int)
    ])

    lines_layer.updateFields()

    features = []

    for ring in alt["rings"]:

        coords = ring["coordinates"]

        pts = [QgsPointXY(c[0],c[1]) for c in coords]

        f = QgsFeature(lines_layer.fields())

        f.setGeometry(QgsGeometry.fromPolylineXY(pts))

        f["ring_id"] = ring["id"]
        f["total_roads"] = ring.get("total_roads")
        f["total_path"] = ring.get("total_path")
        f["duplicate_len"] = ring.get("duplicate_length")

        features.append(f)

    pr.addFeatures(features)

    QgsProject.instance().addMapLayer(lines_layer)
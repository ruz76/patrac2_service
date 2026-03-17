# vrstvy
point_layer = QgsProject.instance().mapLayersByName('ways_nodes')[0]
line_layer = QgsProject.instance().mapLayersByName('ways')[0]

# vybrané prvky
points = point_layer.selectedFeatures()
lines = line_layer.selectedFeatures()

# kontrola výběru
if len(points) != 2:
    raise Exception("Musí být vybrány přesně 2 body")

if len(lines) != 1:
    raise Exception("Musí být vybrána přesně 1 linie")

line = lines[0]

# hodnoty source z bodů
source_val = points[0]['source']
target_val = points[1]['source']

# výpočet max(gid)
max_gid = max([f['gid'] for f in line_layer.getFeatures()])
new_gid = max_gid + 1

# indexy atributů
idx_source = line_layer.fields().indexOf('source')
idx_target = line_layer.fields().indexOf('target')
idx_gid = line_layer.fields().indexOf('gid')

# zápis
line_layer.startEditing()

line_layer.changeAttributeValue(line.id(), idx_source, source_val)
line_layer.changeAttributeValue(line.id(), idx_target, target_val)
line_layer.changeAttributeValue(line.id(), idx_gid, new_gid)

line_layer.commitChanges()

print(new_gid)
print('***DONE***')


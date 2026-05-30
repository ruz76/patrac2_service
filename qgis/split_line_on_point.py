from qgis.core import (
    QgsProject,
    QgsFeature,
    QgsGeometry,
    QgsVectorLayer,
    QgsWkbTypes,
    edit
)
from qgis.utils import iface

# Get layers
point_layer = QgsProject.instance().mapLayersByName('ways_nodes')[0]
line_layer = QgsProject.instance().mapLayersByName('ways')[0]

# Find point with highest "source" value
max_source = -1
point_max_source = None

for point in point_layer.getFeatures():
    source_value = point['source']
    if source_value is not None and source_value > max_source:
        max_source = source_value
        point_max_source = point

if point_max_source is None:
    print("No point found!")
else:
    print(f"Found point with source: {max_source}")

    # Extract point coordinates
    point_geom = point_max_source.geometry()
    point_xy = QgsPointXY(point_geom.asPoint().x(), point_geom.asPoint().y())
    search_geom = QgsGeometry.fromPointXY(point_xy)

    # Find line that intersects this point
    line_to_split = None
    tolerance = 0.0001

    for line in line_layer.getFeatures():
        line_geom = line.geometry()

        if line_geom.distance(search_geom) < tolerance:
            line_to_split = line
            print(f"Found line with ID: {line.id()}")
            break

    # Split line at point
    if line_to_split is not None:
        # Get line points
        line_geom = line_to_split.geometry()
        line_points = line_geom.asPolyline()

        # Find closest segment
        min_dist = float('inf')
        split_index = 0

        for i in range(len(line_points) - 1):
            segment_geom = QgsGeometry.fromPolylineXY([line_points[i], line_points[i+1]])
            dist = segment_geom.distance(search_geom)
            if dist < min_dist:
                min_dist = dist
                split_index = i

        # Create two new lines
        first_part = line_points[:split_index+1] + [point_xy]
        second_part = [point_xy] + line_points[split_index+1:]

        if len(first_part) >= 2 and len(second_part) >= 2:
            with edit(line_layer):
                # Get field names and values (excluding FID/ID fields)
                fields = line_layer.fields()
                original_attrs = {}

                for field in fields:
                    field_name = field.name()
                    # Skip ID/FID fields
                    if field_name.lower() not in ['fid', 'id', 'ogc_fid']:
                        original_attrs[field_name] = line_to_split[field_name]

                print(f"Copying attributes: {list(original_attrs.keys())}")

                # Create first feature
                feature1 = QgsFeature(line_layer.fields())
                feature1.setGeometry(QgsGeometry.fromPolylineXY(first_part))
                for field_name, value in original_attrs.items():
                    feature1[field_name] = value

                # Create second feature
                feature2 = QgsFeature(line_layer.fields())
                feature2.setGeometry(QgsGeometry.fromPolylineXY(second_part))
                for field_name, value in original_attrs.items():
                    feature2[field_name] = value

                # Add new features
                success1 = line_layer.addFeature(feature1)
                success2 = line_layer.addFeature(feature2)

                print(f"Feature 1 added: {success1}")
                print(f"Feature 2 added: {success2}")

                # Delete original line
                if success1 and success2:
                    line_layer.deleteFeature(line_to_split.id())
                    print("Original line deleted")
                else:
                    print("Error adding features")
                    raise Exception("Failed to add features")

            line_layer.updateExtents()
            line_layer.triggerRepaint()
            iface.mapCanvas().refresh()

            print("Operation completed!")
        else:
            print("Error creating split geometries")
    else:
        print("No line found intersecting this point")

import sys, json
places = []
with open(sys.argv[1], 'r') as f:
    lines = f.readlines()
    for line in lines:
        print(line.strip())
        items = line.strip().split(';')
        place = {
            "id": items[4],
            "name": items[5].strip('\'"'),
            "lat": items[0],
            "lon": items[1],
            "okres_id": items[6],
            "upresneni": items[7].strip('\'"'),
            "kraj_id": items[8],
        }
        places.append(place)

with open('../service/places.json', 'w') as f:
    json.dump(places, f)
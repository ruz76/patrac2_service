import sys, json
with open(sys.argv[2]) as r:
    region = r.read().rstrip()
    with open(sys.argv[1]) as g:
        data = json.load(g)
        data['metadata'] = {}
        data['metadata']['region'] = region
        data['metadata']['search_id'] = sys.argv[3]

with open(sys.argv[1], "w") as out:
    json.dump(data, out)

import sys
import json

person_types = [ "child_1_3", "child_4_6", "child_7_12", "child_13_15", "despondent", "psychical_illness", "retarded", "alzheimer", "tourist", "dementia"  ]
percentage = [10, 20, 30, 40, 50, 60, 70, 80, 95]
config = {}

person_type = 0
with open(sys.argv[1]) as a:
    lines = a.readlines()
    for line in lines:
        print(line.strip())
        items = line.strip().split(',')
        percentage_item = 0
        config[person_types[person_type]] = {}
        for item in items:
            config[person_types[person_type]][str(percentage[percentage_item])] = str(item)
            percentage_item += 1
        person_type += 1

print(config)

with open(sys.argv[2], 'w') as out:
    out.write(json.dumps(config))

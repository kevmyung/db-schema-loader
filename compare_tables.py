import json

# Compare Table Names
json1_path = 'spider_tables.json'
json2_path = 'metadata/spider_schemas.json'

with open(json1_path, 'r', encoding='utf-8') as f:
    data1 = json.load(f)

# with open(json2_path, 'r', encoding='utf-8') as f:
#     data2 = json.load(f)

with open(json2_path, 'r', encoding='utf-8') as f:
    content = f.read()
    content = "[" + content.rstrip(', \n') + "]"
    data2 = json.loads(content)


def compare_table_names(json1, json2):
    json1_tables = list(json1.keys())
    json2_tables = [list(item.keys())[0] for item in json2]
    
    discrepancies = []
    max_len = max(len(json1_tables), len(json2_tables))
    
    for i in range(max_len):
        if i < len(json1_tables) and i < len(json2_tables):
            if json1_tables[i].lower() != json2_tables[i].lower():
                discrepancies.append((json1_tables[i], json2_tables[i]))
        elif i < len(json1_tables):
            discrepancies.append((json1_tables[i], None))
        else:
            discrepancies.append((None, json2_tables[i]))
    
    return discrepancies

discrepancies = compare_table_names(data1, data2)

print("Table name discrepancies:")
for d in discrepancies:
    print(d)

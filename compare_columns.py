import json

# Compare Table Columns
json1_path = 'spider_tables.json'
json2_path = 'metadata/spider_schemas.json'

with open(json1_path, 'r', encoding='utf-8') as f:
    data1 = json.load(f)

with open(json2_path, 'r', encoding='utf-8') as f:
    data2 = json.load(f)

# Function to extract column list from JSON dictionary and convert to lowercase
def get_column_list_from_dict(json_data):
    columns_dict = {}
    for table_name, table_data in json_data.items():
        columns_dict[table_name.lower()] = [col["col"].lower() for col in table_data["cols"]]
    return columns_dict

# Function to extract column list from JSON list and convert to lowercase
def get_column_list_from_list(json_data):
    columns_dict = {}
    for item in json_data:
        for table_name, table_data in item.items():
            columns_dict[table_name.lower()] = [col["col"].lower() for col in table_data["cols"]]
    return columns_dict

# Load JSON data
columns_dict_json1 = get_column_list_from_dict(data1)
columns_dict_json2 = get_column_list_from_list(data2)

# Table name to compare
all_tables = set(columns_dict_json1.keys()).union(set(columns_dict_json2.keys()))
for table_name in all_tables:
    cols_json1 = columns_dict_json1.get(table_name, [])
    cols_json2 = columns_dict_json2.get(table_name, [])
    if cols_json1 == cols_json2:
        continue
    else:
        print(f"The column lists for table '{table_name}' are different.")
        print(f"JSON1 columns for table '{table_name}':", cols_json1)
        print(f"JSON2 columns for table '{table_name}':", cols_json2)

print("All same")
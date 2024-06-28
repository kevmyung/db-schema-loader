import json

with open('spider_inputs.json', 'r') as infile:
    data = json.load(infile)

def parse_data(data):
    parsed = {}
    
    for db in data:
        db_id = db['db_id']
        
        table_names = db['table_names']
        column_names = db['column_names']
        column_names_original = db['column_names_original']
        column_types = db['column_types']
        primary_keys = db['primary_keys']
        foreign_keys = db['foreign_keys']

        for i, table in enumerate(table_names):
            table_key = f"{db_id}_{table.replace(' ', '_')}" 
            parsed[table_key] = {
                "cols": [],
                "table_desc": table
            }
            
            for j, col in enumerate(column_names):
                if col[0] == i:
                    col_name = column_names_original[j][1]
                    col_desc = col[1]
                    col_format = column_types[j]
                    pk = j in primary_keys

                    parsed[table_key]["cols"].append({
                        "col": col_name,
                        "format": col_format,
                        "col_desc": col_desc,
                        "pk": pk
                    })

    return parsed

parsed_data = parse_data(data)

with open('spider_tables.json', 'w') as outfile:
    json.dump(parsed_data, outfile, indent=4)

print("Data successfully parsed and saved to spider_tables.json")

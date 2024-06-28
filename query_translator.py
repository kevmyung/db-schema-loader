import json
import os
import time
import yaml
from langchain_aws import ChatBedrock
from opensearchpy import OpenSearch, RequestsHttpConnection
from langchain_community.embeddings import BedrockEmbeddings
from langchain_core.prompts.chat import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser


output_language = "Korean"

SYS_PROMPT_TEMPLATE1 = """ 
You are an expert in extracting table names and column names from SQL queries. 
From the provided SQL query, extract all table names and column names used for SELECT, WHERE, and JOIN clauses, excluding asterisks ("*"). 
Ensure that the response is in a valid JSON format that can be used directly with json.load(). 
Skip the preamble and only provide the answer in a JSON document:

{
  "table": ["table1", "table2", ...],
  "column": ["col1", "col2", ...]
}

<example>
SQL:
SELECT * from LOGIS_ADMIN.IAWD_TB_DCBSCD_BASISLC_M 
where basis_lclsf_cd_nm like '%예약구분%'
LIMIT 200;

{
  "table": ["IAWD_TB_DCBSCD_BASISLC_M"],
  "column": ["basis_lclsf_cd_nm"]
}
</example>
"""


SYS_PROMPT_TEMPLATE2 = """ 
You are an SQL expert who can understand the intent behind a given SQL query. 
Translate the SQL query into a natural language request in {output_language} that a real user might make. 

- Keep your translation concise and conversational, mimicking how an actual user would ask for the information sought by the query. 
- Do not reference the <description> section directly and do not use a question form. 
- Ensure to include all conditions specified in the SQL query in the request.
- Write possible business and functional purposes of the query.
- Write very detailed purposes and motives of the query in detail.
- Skip the preamble and phrase only the natural language request using a concise and straightforward tone without a verb ending. 

<example>
SQL: SELECT count(*)\nfrom IAWB_TB_DCTRTR_TR_M\nwhere work_dt = '20240522'
Query to retrieve the count of products processed on May 22, 2024.
</example>
""".format(output_language=output_language)

USR_PROMPT_TEMPLATE1="""
SQL: {sql}
"""

USR_PROMPT_TEMPLATE2="""
<description>
{description}
</description>

SQL: {sql}
"""


INDEX_NAME = "example_queries"
REGION_NAME = "us-east-1"

SCHEMA_FILE = "./metadata/spider_schemas.json"
SQL_FILE = "./metadata/spider.sql"
FILE_PATH_1 = "./metadata/spider_example_queries_temp.json"
FILE_PATH_2 = "./metadata/spider_example_queries.json"

model_kwargs =  { 
    "max_tokens": 100000,
    "temperature": 0.0,
    "top_k": 250,
    "top_p": 1
}

model_kwargs["system"] = SYS_PROMPT_TEMPLATE1
model1 = ChatBedrock(model_id="anthropic.claude-3-sonnet-20240229-v1:0", region_name=REGION_NAME, model_kwargs=model_kwargs)

model_kwargs["system"] = SYS_PROMPT_TEMPLATE2
model2 = ChatBedrock(model_id="anthropic.claude-3-sonnet-20240229-v1:0", region_name=REGION_NAME, model_kwargs=model_kwargs)

emb_model = BedrockEmbeddings(model_id="amazon.titan-embed-text-v2:0", region_name=REGION_NAME, model_kwargs={"dimensions":1024}) 

def load_opensearch_config():
    with open("./metadata/opensearch.yml", 'r', encoding='utf-8') as file:
        return yaml.safe_load(file)

def create_os_index(os_client, mapping):
    exists = os_client.indices.exists(INDEX_NAME)

    if exists:
        os_client.indices.delete(index=INDEX_NAME)
        print("Existing index has been deleted. Create new one.")
    else:
        print("Index does not exist, Create one.")

    os_client.indices.create(INDEX_NAME, body=mapping)

def init_opensearch(config):
    mapping = {"settings": config['settings'], "mappings": config['mappings-schema']}
    endpoint = config['opensearch-auth']['domain_endpoint']
    http_auth = (config['opensearch-auth']['user_id'], config['opensearch-auth']['user_password'])

    os_client = OpenSearch(
            hosts=[{'host': endpoint.replace("https://", ""),'port': 443}],
            http_auth=http_auth, 
            use_ssl=True,
            verify_certs=True,
            timeout=300,
            connection_class=RequestsHttpConnection
    )

    create_os_index(os_client, mapping)
    return os_client

def extract_descriptions(table_info, tables, columns):
    tables_lower = {table.lower() for table in tables}
    columns_lower = {column.lower() for column in columns}
    
    description = {
        "table": {},
        "column": {}
    }
    
    for table_schema in table_info:
        for table_name, table_info in table_schema.items():
            if table_name.lower() in tables_lower:
                description["table"][table_name] = table_info["table_desc"]
                for col in table_info["cols"]:
                    col_name = col["col"]
                    if col_name.lower() in columns_lower:
                        description["column"][col_name] = col["col_desc"]
    return description

def query_translation(table_info, queries, chain1, chain2):
    if os.path.exists(FILE_PATH_1):
        os.remove(FILE_PATH_1)

    with open(FILE_PATH_1, 'a') as output_file:
        for query in queries:
            sql = query.strip()
            
            try:
                response = chain1.invoke({"sql": sql})
                schema = json.loads(response)
            except json.JSONDecodeError:
                print(response)
                time.sleep(1)  

            description = extract_descriptions(table_info, schema["table"], schema["column"])
            
            input = chain2.invoke({"sql": sql, "description": description})
            # Write input and query to the file in JSON format
            data = {"input": input, "query": sql}
            output_file.write(json.dumps(data, ensure_ascii=False) + "\n")

def input_embedding(emb_model):
    num = 0
    if os.path.exists(FILE_PATH_2):
        os.remove(FILE_PATH_2)

    with open(FILE_PATH_1, 'r') as input_file, open(FILE_PATH_2, 'a') as output_file:
        for line in input_file:
            data = json.loads(line)
            input = data['input']
            query = data['query']
            
            # Data part
            body = { "input": input, "query": query, "input_v": emb_model.embed_query(input) }

            # Action part
            action = { "index": { "_index": INDEX_NAME, "_id": str(num) } }

            # Write action and body to the file in correct bulk format
            output_file.write(json.dumps(action, ensure_ascii=False) + "\n")
            output_file.write(json.dumps(body, ensure_ascii=False) + "\n")

            num += 1    

def main():   
    # load the schema description
    with open(SCHEMA_FILE, 'r') as file:
        table_info = json.load(file)

    # load the example SQLs
    with open(SQL_FILE, 'r') as file:
        data = file.read()
    queries = [query.strip() for query in data.split(';') if query.strip()]

    prompt1 = ChatPromptTemplate.from_template(USR_PROMPT_TEMPLATE1)
    chain1 = prompt1 | model1 | StrOutputParser()

    prompt2 = ChatPromptTemplate.from_template(USR_PROMPT_TEMPLATE2)
    chain2 = prompt2 | model2 | StrOutputParser()

    query_translation(table_info, queries, chain1, chain2)
    input_embedding(emb_model)

    # initialize opensearch index (cluster should be pre-created)
    config = load_opensearch_config()
    os_client = init_opensearch(config)

    with open(FILE_PATH_2, 'r') as file:
        bulk_data = file.read()

    response = os_client.bulk(body=bulk_data)

    if response["errors"]:
        print("There were errors during bulk indexing:")
        for item in response["items"]:
            if 'index' in item and item['index']['status'] >= 400:
                print(f"Error: {item['index']['error']['reason']}")
    else:
        print("Bulk-inserted all items successfully.")
    
if __name__ == "__main__":
    main()




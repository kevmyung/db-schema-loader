import os
import json
import yaml
from langchain_aws import ChatBedrock
from opensearchpy import OpenSearch, RequestsHttpConnection
from langchain_community.embeddings import BedrockEmbeddings
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts.chat import ChatPromptTemplate


REGION_NAME = "us-east-1"
INDEX_NAME = "schema_descriptions"

SCHEMA_FILE_PATH = "./metadata/default_schema.json"
SAMPLE_QUERY_FILE_PATH = "./metadata/example_queries_temp.json"

OUTPUT_FILE_PATH1 = "./metadata/detailed_schema_temp.json"
OUTPUT_FILE_PATH2 = "./metadata/detailed_schema.json"

SYS_PROMPT = """
You are a data analyst that can help summarize SQL tables.
Summarize the provided table by the given context.

<instruction>
- You shall write the summary based only on the provided information, and make it as detailed as possible.
- Note that above sampled queries are only small sample of queries and thus not all possible use of tables are represented, and only some columns in the table are used.
- Do not use any adjective to describe the table. For example, the importance of the table, its comprehensiveness or if it is crucial, or who may be using it. For example, you can say that a table contains certain types of data, but you cannot say that the table contains a 'wealth' of data, or that it is 'comprehensive'.
- Do not mention about the sampled query. Only talk objectively about the type of data the table contains and its possible utilities.
- Please also include some potential usecases of the table, e.g. what kind of questions can be answered by the table, what kind of anlaysis can be done by the table, etc.
- Please provide the output in Korean.
</instruction>
"""

PROMPT_TEMPLATE = """
<table schema>
{table_schema}
</table schema>

<sample queries>
{sample_queries}
</sample queries>
"""

def load_schema(file_path):
    with open(file_path, 'r', encoding='utf-8') as file:
        schema = json.load(file)
    return schema

def load_queries(file_path):
    with open(file_path, 'r', encoding='utf-8') as file:
        queries = file.readlines()
    return queries

def load_opensearch_config():
    with open("./metadata/opensearch.yml", 'r', encoding='utf-8') as file:
        return yaml.safe_load(file)

def init_model():
    model_kwargs =  { 
        "max_tokens": 100000,
        "temperature": 0.0,
        "top_k": 250,
        "top_p": 1,
        "system": SYS_PROMPT
    }

    chat_model = ChatBedrock(
        model_id="anthropic.claude-3-sonnet-20240229-v1:0",
        region_name=REGION_NAME,
        model_kwargs=model_kwargs
    )

    emb_model = BedrockEmbeddings(model_id="amazon.titan-embed-text-v2:0", region_name=REGION_NAME, model_kwargs={"dimensions":1024}) 
    return chat_model, emb_model

def create_os_index(os_client, mapping):
    exists = os_client.indices.exists(INDEX_NAME)

    if exists:
        os_client.indices.delete(index=INDEX_NAME)
        print("Existing index has been deleted. Create new one.")
    else:
        print("Index does not exist, Create one.")

    os_client.indices.create(INDEX_NAME, body=mapping)

def init_opensearch(config):
    mapping = {"settings": config['settings'], "mappings": config['mappings-detailed-schema']}
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

def search_table_queries(queries, table_name):
    table_name_lower = table_name.lower()
    matched_queries = []

    for line in queries:
        try:
            query_data = json.loads(line)
            if table_name_lower in query_data['query'].lower():
                matched_queries.append(query_data)
        except json.JSONDecodeError:
            print(f"Invalid JSON line: {line}")
    
    return matched_queries

def summarize_table(table_name, table_data, queries, chain):
    with open(OUTPUT_FILE_PATH1, 'a', encoding='utf-8') as output_file:            
        table_summary = chain.invoke({"table_schema": table_data, "sample_queries": queries})
        table_data['table_summary'] = table_summary 
        summary_output = {table_name: table_data}
        output_file.write(json.dumps(summary_output, ensure_ascii=False) + "\n")


def embedding_summary(emb_model):
    num = 0
    with open(OUTPUT_FILE_PATH1, 'r') as input_file, open(OUTPUT_FILE_PATH2, 'a') as output_file:
        for line in input_file:
            data = json.loads(line)
            table_name = list(data.keys())[0]
            table_summary = data[table_name]["table_summary"]
            data[table_name]["table_summary_v"] = emb_model.embed_query(table_summary)
            
            # Action part
            action = { "index": { "_index": INDEX_NAME, "_id": str(num) } }

            # Write action and body to the file in correct bulk format
            output_file.write(json.dumps(action, ensure_ascii=False) + "\n")
            output_file.write(json.dumps(data, ensure_ascii=False) + "\n")

            num += 1    


def main():
    schema = load_schema(SCHEMA_FILE_PATH)
    queries = load_queries(SAMPLE_QUERY_FILE_PATH)
    chat_model, emb_model = init_model()

    if os.path.exists(OUTPUT_FILE_PATH1):
        os.remove(OUTPUT_FILE_PATH1)

    for table_info in schema:
        for table_name, table_data in table_info.items():
            globals()[table_name] = table_data
            matched_queries = search_table_queries(queries, table_name)
            prompt = ChatPromptTemplate.from_template(PROMPT_TEMPLATE)
            chain = prompt | chat_model | StrOutputParser()

            summarize_table(table_name, table_data, matched_queries, chain)

    if os.path.exists(OUTPUT_FILE_PATH2):
        os.remove(OUTPUT_FILE_PATH2)

    embedding_summary(emb_model)

    # initialize opensearch index (cluster should be pre-created)
    config = load_opensearch_config()
    os_client = init_opensearch(config)

    with open(OUTPUT_FILE_PATH2, 'r') as file:
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
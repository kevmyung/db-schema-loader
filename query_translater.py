import json
import os
from langchain_aws import ChatBedrock
from opensearchpy import OpenSearch, RequestsHttpConnection
from langchain_community.embeddings import BedrockEmbeddings
from langchain_core.prompts.chat import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

PROMPT_TEMPLATE = """ 
<table_info>
{table_info}
</table_info>

SQL: {sql}
"""

INDEX_NAME = "example_queries"
REGION_NAME = "us-east-1"
SCHEMA_FILE = "./metadata/default_schema.json"
SQL_FILE = "./metadata/test.txt"
FILE_PATH_1 = "./metadata/example_queries_temp.json"
FILE_PATH_2 = "./metadata/example_queries.json"


def init_model():
    model_kwargs =  { 
        "max_tokens": 100000,
        "temperature": 0.0,
        "top_k": 250,
        "top_p": 1,
        "system":"""
        You are an SQL expert who can understand the intent behind a given SQL query. 
        Translate the SQL query into a natural language request, phrased as a conversational question that a real user might ask. 
        Use the provided table information between <table_info> and </table_info> to comprehend the schema defined in the SQL. 
        Keep your translation concise and conversational, mimicking how an actual user would inquire about the information sought by the query.
        Skip the preamble and only provide the generated user's inquery.
        """
    }

    chat_model = ChatBedrock(
        model_id="anthropic.claude-3-sonnet-20240229-v1:0",
        region_name=REGION_NAME,
        model_kwargs=model_kwargs
    )

    emb_model = BedrockEmbeddings(model_id="amazon.titan-embed-text-v2:0", region_name=REGION_NAME, model_kwargs={"dimensions":1024}) 
    return chat_model, emb_model


def create_os_index(os_client):
    with open('./metadata/index_template.json', 'r') as f:
        index_body = json.load(f)

    exists = os_client.indices.exists(INDEX_NAME)

    if exists:
        os_client.indices.delete(index=INDEX_NAME)
        print("Existing index has been deleted. Create new one.")
    else:
        print("Index does not exist, Create one.")

    os_client.indices.create(INDEX_NAME, body=index_body)

def init_opensearch():
    user = ""
    password = ""
    endpoint = ""
    http_auth = (user, password)

    os_client = OpenSearch(
            hosts=[{'host': endpoint.replace("https://", ""),'port': 443}],
            http_auth=http_auth, 
            use_ssl=True,
            verify_certs=True,
            timeout=300,
            connection_class=RequestsHttpConnection
    )

    # create_os_index(os_client)

    return os_client

def search_with_question(os_client, emb_model):
    # transform the question to vector embeddings
    search_vector = emb_model.embed_query("블루스 장르의 인기 트렌드를 알려줘")
    search_body = {
        "size": 5,
        "query": {
            "knn": {
                "input_v": {
                    "vector": search_vector,
                    "k": 10
                }
            }
        }
    }

    # vector search
    response = os_client.search(
        index=INDEX_NAME,
        body=search_body
    )
    
    if response['hits']['hits']:
        for hit in response['hits']['hits']:
            print(f"Input: {hit['_source']['input']}")
            print(f"Query: {hit['_source']['query']}\n")
    else:
        print(f"Failed to perform knn search: {response}")

    return response['hits']['hits']

def query_translation(table_info, queries, chain):
    if os.path.exists(FILE_PATH_1):
        os.remove(FILE_PATH_1)

    with open(FILE_PATH_1, 'a') as output_file:
        for query in queries:
            sql = query.strip()
            
            # Query translation
            input = chain.invoke({"table_info": table_info, "sql": sql})

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
    # initialize the model
    chat_model, emb_model = init_model()

    # load the schema description
    with open(SCHEMA_FILE, 'r') as file:
        table_info = json.load(file)

    # load the example SQLs
    with open(SQL_FILE, 'r') as file:
        data = file.read()
    queries = data.split(';')

    # create LLM chain
    prompt = ChatPromptTemplate.from_template(PROMPT_TEMPLATE)
    chain = prompt | chat_model | StrOutputParser()

    query_translation(table_info, queries, chain)
    input_embedding(emb_model)

    # initialize opensearch index (cluster should be pre-created)
    os_client = init_opensearch()

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
    
    # hit = search_with_question(os_client, emb_model)
    # print(f"Input: {hit['_source']['input']}")
    # print(f"Query: {hit['_source']['query']}\n")

if __name__ == "__main__":
    main()
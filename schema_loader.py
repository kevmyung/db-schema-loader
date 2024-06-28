import json
import os
from langchain_aws import ChatBedrock
from langchain_core.prompts.chat import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

_SYS_PROMPT_TEMPLATE_1 = """
You are a helpful assistant tasked with writing table creation (DDL) statements to create the tables for the provided schema. 
Skip the preambles and only provide the output in the desired format.
Finish a statement with ";\n".
"""

_SYS_PROMPT_TEMPLATE_2 = """
You are a helpful assistant that reformats the given table info into JSON following the 'output_format'.

Instructions:
- Write detailed descriptions about each table and column by using the given information.
- Don't change the Table Name and Column Names.
- Adhere to the following JSON format for each table and column without any additions or omissions or incorrect values.
{"table_details": {"table_name": "", "table_desc":"", "cols":[{"col":"", "col_desc":""}]}}
- Include the PK info within the column descriptions.
- Skip the preambles and only provide the output in the desired format.

Output Format:
{
    "table_name": {
        "table_desc": "Description of the table",
        "cols": [
            {
                "col": "Column Name 1",
                "col_desc": "Description of the column including PK info"
            },
            {
                "col": "Column Name 2",
                "col_desc": "Description of the column"
            }
        ]
    }
}
"""

_USER_PROMPT_TEMPLATE = """
<table_info>
Table Name: {table}
Column Names: {columns}
</table_info>

DB Dialect: {dialect}
"""

model_kwargs =  { 
    "max_tokens": 200000,
    "temperature": 0.0,
    "top_k": 250,
    "top_p": 1
}

with open('spider_tables.json', 'r', encoding='utf-8') as file:
    table_info = json.load(file)

if not os.path.exists('metadata'):
    os.makedirs('metadata')

# User Prompt Template
usr_prompt = ChatPromptTemplate.from_template(_USER_PROMPT_TEMPLATE)

model_kwargs["system"] = _SYS_PROMPT_TEMPLATE_1
model1 = ChatBedrock(model_id="anthropic.claude-3-sonnet-20240229-v1:0", region_name='us-east-1', model_kwargs=model_kwargs)
chain1 = usr_prompt | model1 | StrOutputParser()

model_kwargs["system"] = _SYS_PROMPT_TEMPLATE_2
model = ChatBedrock(model_id="anthropic.claude-3-sonnet-20240229-v1:0", region_name='us-east-1', model_kwargs=model_kwargs)
chain2 = usr_prompt | model | StrOutputParser()

for table_name, columns in table_info.items():
    all_columns = ""
    for col in columns['cols']:
        all_columns += col['col'] + ", "
    response2 = chain2.invoke({"table":table_name.lower(), "columns":all_columns.lower(), "dialect": "SQLite"})    
    with open('./metadata/spider_schemas.json', 'a') as output_file:
        output_file.write(response2)

file_path = './metadata/spider_schemas.json'
with open(file_path, 'r') as file:
    content = file.read()

content = content.replace('}{', '},{')
content = '[' + content + ']'

with open(file_path, 'w') as file:
    file.write(content)
import json
import os
from langchain_aws import ChatBedrock
from langchain_core.prompts.chat import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

model_kwargs =  { 
    "max_tokens": 200000,
    "temperature": 0.0,
    "top_k": 250,
    "top_p": 1,
    "stop_sequences": ["Human"],
}

model = ChatBedrock(
    model_id="anthropic.claude-3-sonnet-20240229-v1:0",
    region_name='us-east-1',
    model_kwargs=model_kwargs,
)

table_meta_fields = "정보분석 테이블명,정보분석 테이블한글명_3차,정보분석 컬럼명,정보분석 컬럼한글명,정보분석 컬럼타입"

with open('table_info.json', 'r', encoding='utf-8') as file:
    table_info = json.load(file)

prompt_template = """ 
You are a helpful assistant that structures tables according to given schemas and organizes detailed information about the schemas.

<table_info>
{table_meta_fields}
{table}
</table_info>

<instruction>
{input}
</instruction>

Skip the preambles and only provide the output in a desired format.
Begin!
""".format(table_meta_fields=table_meta_fields)

if not os.path.exists('metadata'):
    os.makedirs('metadata')

for table in table_info:
    prompt = ChatPromptTemplate.from_template(prompt_template)

    chain = prompt | model | StrOutputParser()

    question = "Give me a table creation (DDL) statements to create the tables for the provided schema."
    response = chain.invoke({"table":table, "input": question})

    with open('./metadata/table_DDLs.sql', 'a') as output_file:
        output_file.write(response)

    question = """Format the given CSV in JSON like the example below:

                <example>
                <table_info>
                {table_meta_fields} 
                LOGIS_ADMIN.IAWD_TB_DCWBWR_WBL_M,OIAWD_ODCWB_운송장_기본,WBL_NO,운송장번호,VARCHAR(60) 
                LOGIS_ADMIN.IAWD_TB_DCWBWR_WBL_M,OIAWD_ODCWB_운송장_기본,COC_DT,집화일자,VARCHAR(8)
                </table_info>

                <output>
                {
                    "table_details": {
                        "table_name": "IAWD_TB_DCWBWR_WBL_M",
                        "table_name_ko": "운송장_기본",
                        "table_desc": "각 운송장에 대한 기본 정보를 포함하며, 운송장 번호, 집화일자, 집화점 소코드 등의 컬럼을 갖습니다.",
                        "cols": [
                            {
                                "col": "WBL_NO",
                                "col_ko": "운송장번호",
                                "coltype": "VARCHAR(60)",
                                "col_desc": "택배의 운송장 고유번호"
                            },
                            {
                                "col": "COC_DT",
                                "col_ko": "집화일자",
                                "coltype": "VARCHAR(8)",
                                "col_desc": "택배가 집화된 날짜"
                            }
                        ]
                    }
                }, 
                </output>
                </example>

                <requirements>
                - It is crucial to adhere to the following JSON format for each table and column:
                {"table_details": {"table_name": "", "table_name_ko":"", "table_desc":"", "cols":[{"col":"", "col_ko":"", "coltype":"", "col_desc":}]}}
                - Pay close attention to include all columns accurately and without any omissions or incorrect values.
                - Finish a JSON output with a comma.
                </requirements>
                """.format(table_meta_fields=table_meta_fields)
    
    response = chain.invoke({"table":table, "input": question})
    with open('./metadata/schemas.json', 'a') as output_file:
        output_file.write(response)


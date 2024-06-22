# Overview

1. [Schema Loader](#schema-loader)
   - 간단한 테이블 설명 파일을 활용해 데이터베이스 스키마 정의 문서를 자동으로 생성합니다.
2. [Init Database](#optional-데이터베이스-초기화)
   - 데이터베이스 스키마 정의를 활용해, 테스트 용 MySQL 데이터베이스 스키마를 초기 구성하고, 샘플 데이터를 적재합니다.
3. [Query Translator](#query-translator)
   - 예제 SQL 쿼리를 자연어로 번역하고, 이를 벡터 임베딩으로 변환하여 OpenSearch에 인덱싱합니다싱


# Schema Loader
`schema_loader.py` 스크립트는 사전에 정의된 JSON 파일(`table_info.json`)로부터 데이터베이스 스키마 정의를 생성합니다. 이 스크립트는 데이터베이스에 테이블을 생성하기 위한 SQL 데이터 정의 언어(DDL) 문장을 출력하며, 자세한 스키마 설명을 JSON 형식으로 출력합니다.

## 입력

- `table_info.json`: 테이블 및 컬럼 정보를 포함하는 JSON 파일.

### `table_info.json`의 예시 형식

`table_info.json`은 다음과 같은 구조로 작성되어야 합니다:

```json
[
    "Table1, Column1, Column1 Description, Column1 Type\nTable1, Column2, Column2 Description, Column2 Type, ...",
    "Table2, Column1, Column1 Description, Column1 Type\nTable2, Column2, Column2 Description, Column2 Type, ..."
]
```

리스트의 각 항목은 테이블 및 컬럼 정보를 쉼표로 구분한 문자열입니다. 각 테이블의 컬럼은 개행 문자(`\n`)로 구분됩니다.

### 예시

```json
[
    "LOGIS_ADMIN.IAWD_TB_DCWBWR_WBL_M,OIAWD_ODCWB_운송장_기본,WBL_NO,운송장번호,VARCHAR(60)\nLOGIS_ADMIN.IAWD_TB_DCWBWR_WBL_M,OIAWD_ODCWB_운송장_기본,COC_DT,집화일자,VARCHAR(8)"
]
```

## 출력

1. `./metadata/table_DDLs.sql`: `table_info.json`에 정의된 테이블을 생성하기 위한 SQL DDL 구문.
2. `./metadata/schemas.json`: 자세한 스키마 설명을 포함하는 JSON 형식의 파일.

### 출력 예시

#### `table_DDLs.sql`

```sql
CREATE TABLE IAWD_TB_DCWBWR_WBL_M (WBL_NO VARCHAR(60),COC_DT VARCHAR(8));
```

#### `schemas.json`

```json
{
    "IAWD_TB_DCWBWR_WBL_M": {
        "table_desc": "각 운송장에 대한 기본 정보를 포함하며, 운송장 번호, 집화일자 등의 컬럼을 갖습니다.",
        "cols": [
            {
                "col": "WBL_NO",
                "col_desc": "택배의 운송장 고유번호"
            },
            {
                "col": "COC_DT",
                "col_desc": "택배가 집화된 날짜"
            }
        ]
    }
}
```

## 사용법

### 스크립트 실행

1. `table_info.json` 파일이 올바른 형식으로 작성되어 적절한 디렉토리에 위치하고 있는지 확인합니다.
2. `schema_loader.py` 스크립트를 실행합니다:

```sh
python schema_loader.py
```

### `table_meta_fields` 수정

사용자의 메타데이터 구조에 맞춰 `table_meta_fields`를 스크립트에서 수정할 수 있습니다.

#### 예시

메타데이터 필드 형식이 `"정보분석 테이블명,정보분석 테이블한글명_3차,정보분석 컬럼명,정보분석 컬럼한글명,정보분석 컬럼타입"`인 경우, `schema_loader.py`의 `table_meta_fields`를 다음과 같이 업데이트합니다.

```python
table_meta_fields = "정보분석 테이블명,정보분석 테이블한글명_3차,정보분석 컬럼명,정보분석 컬럼한글명,정보분석 컬럼타입"
```

---

# Init Database

테스트용 데이터베이스 환경을 구축하는 경우 이 스크립트를 활용합니다. 이 스크립트는 MySQL 데이터베이스를 대상으로 하는 경우에 맞춰 정의되어 있습니다.

## 입력

- `db_cred.json`: 데이터베이스 연결 정보를 포함하는 JSON 파일.

### `db_cred.json`의 형식

```json
{
    "host": "{Database Endpoint}",
    "user": "{DB User name}",
    "password": "{DB Password}"
}
```

## 실행 방법

`init_database.py`를 통해 `Schema Loader`에서 생성한 `table_DDLs.sql`을 실행합니다. 이 스크립트를 실행하면 스키마 설명에 정의된 테이블과 컬럼을 테스트 데이터베이스에 생성합니다.

```sh
python init_database.py
```

## 샘플 데이터 적재

샘플 데이터를 테스트 환경에 함께 적재하고자 한다면, 아래와 같은 형식의 `table_DMLs.sql` 파일을 사전에 생성합니다. 그러면 스크립트에서 DML 구문까지 같이 수행합니다.

### `table_DMLs.sql`의 정의 예시

```sql
INSERT INTO IAWD_TB_DCWBWR_WBL_M (WBL_NO, COC_DT)
VALUES ('571134548144', '20230905');
```

이 스크립트는 `table_DDLs.sql`과 `table_DMLs.sql` 파일을 사용하여 데이터베이스를 초기화하고, 샘플 데이터를 적재합니다.

---

# Query Translator

이 스크립트는 SQL 쿼리를 자연어로 변환하는 스크립트를 포함합니다. 이 스크립트는 SQL 쿼리에서 테이블 및 컬럼 이름을 추출하고, 이를 자연어로 번역하여 사용자 요청 형태로 변환합니다. 또한, 변환된 자연어 요청을 벡터 임베딩으로 변환하여 OpenSearch에 색인합니다.

## 스크립트 설명

### `query_translator.py`

이 스크립트는 다음 주요 기능을 포함합니다:

1. SQL 쿼리에서 테이블 및 컬럼 이름 추출
2. SQL 쿼리를 자연어로 번역
3. 번역된 자연어 요청을 벡터 임베딩으로 변환
4. 변환된 임베딩을 OpenSearch에 색인

## 입력

- `./metadata/default_schema.json`: 테이블 및 컬럼 정보를 포함하는 JSON 파일
- `./metadata/test.txt`: 번역할 SQL 쿼리 목록을 포함하는 파일

### `default_schema.json`의 형식
```json
[
    {
        "Album": {
            "table_desc": "Stores album data with unique ID, title, and links to artist via artist ID.",
            "cols": [
                {
                    "col": "AlbumId",
                    "col_desc": "Primary key, unique identifier for the album."
                },
                {
                    "col": "Title",
                    "col_desc": "Title of the album."
                },
                {
                    "col": "ArtistId",
                    "col_desc": "Foreign key that references the artist of the album."
                }
            ]
        }
    },
    ...
]
```

### `test.txt`의 형식
```
SELECT * FROM Artist;
SELECT * FROM Album WHERE ArtistId = (SELECT ArtistId FROM Artist WHERE Name = 'AC/DC');
SELECT * FROM Track WHERE GenreId = (SELECT GenreId FROM Genre WHERE Name = 'Rock');
SELECT SUM(Milliseconds) FROM Track;
```

## 출력

- `example_queries_temp.json`: 임시 파일로 번역된 쿼리와 SQL 쿼리를 저장
- `example_queries.json`: 최종 파일로 번역된 쿼리와 임베딩을 저장

### `example_queries_temp.json`의 형식
```json
{"input": "모든 아티스트 정보 조회", "query": "SELECT * FROM Artist"}
{"input": "AC/DC 아티스트의 앨범 정보 조회", "query": "SELECT * FROM Album WHERE ArtistId = (SELECT ArtistId FROM Artist WHERE Name = 'AC/DC')"}
{"input": "락 장르의 모든 트랙 정보 조회", "query": "SELECT * FROM Track WHERE GenreId = (SELECT GenreId FROM Genre WHERE Name = 'Rock')"}
```

### `example_queries.json`의 형식
```json
{"index": {"_index": "example_queries", "_id": "0"}}
{"input": "모든 아티스트 정보 조회", "query": "SELECT * FROM Artist", "input_v": [0.1, 0.2, ..., 0.3]}
{"index": {"_index": "example_queries", "_id": "1"}}
{"input": "AC/DC 아티스트의 앨범 정보 조회", "query": "SELECT * FROM Album WHERE ArtistId = (SELECT ArtistId FROM Artist WHERE Name = 'AC/DC')", "input_v": [0.1, 0.2, ..., 0.3]}
{"index": {"_index": "example_queries", "_id": "2"}}
{"input": "락 장르의 모든 트랙 정보 조회", "query": "SELECT * FROM Track WHERE GenreId = (SELECT GenreId FROM Genre WHERE Name = 'Rock')", "input_v": [0.1, 0.2, ..., 0.3]}
```

## 실행 방법

### 스크립트 실행

1. 필요한 입력 파일이 올바른 형식으로 작성되어 적절한 디렉토리에 위치하고 있는지 확인합니다.
2. `query_translator.py` 스크립트를 실행합니다:

```sh
python query_translator.py
```

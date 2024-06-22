import os
import json
import mysql.connector
from mysql.connector import Error

def create_connection(host_name, user_name, user_password, db_name=None):
    connection = None
    try:
        if db_name:
            connection = mysql.connector.connect(
                host=host_name,
                user=user_name,
                passwd=user_password,
                database=db_name
            )
        else:
            connection = mysql.connector.connect(
                host=host_name,
                user=user_name,
                passwd=user_password
            )
        print("Connection to MySQL DB successful")
    except Error as e:
        print(f"The error '{e}' occurred")
        return None
    return connection

def execute_query(connection, query):
    if connection is not None:
        cursor = connection.cursor()
        try:
            cursor.execute(query)
            connection.commit()
            print("Query executed successfully")
        except Error as e:
            print(f"The error '{e}' occurred in {query}")
            cursor.execute('SHOW WARNINGS;')
            warnings = cursor.fetchall()
            if warnings:
                print(warnings)
    else:
        print("No connection to the database.")

def main():
    with open('db_cred.json', 'r') as file:
        db_credentials = json.load(file)

    host = db_credentials['host']
    user = db_credentials['user']
    password = db_credentials['password']
    
    connection = create_connection(host, user, password)
    
    drop_query = "DROP DATABASE IF EXISTS logis_admin;"
    create_query = "CREATE DATABASE logis_admin;"
    execute_query(connection, drop_query)
    execute_query(connection, create_query)

    if connection.is_connected():
        connection.close()

    connection = create_connection(host, user, password, "logis_admin")
    
    with open('metadata/table_DDLs.sql', 'r') as file:
        sql_file = file.read()
        sql_commands = sql_file.split(';') 

    for command in sql_commands:
        if command.strip():
            execute_query(connection, command)

    if os.path.exists('metadata/table_DMLs.sql'):
        with open('metadata/table_DMLs.sql', 'r') as file:
            sql_file = file.read()
            sql_commands = sql_file.split(';') 

        for command in sql_commands:
            if command.strip():
                execute_query(connection, command)
    else:
        print("File 'metadata/table_DMLs.sql' does not exist.")

    if connection and connection.is_connected():
        connection.close()
        print("MySQL connection is closed")

if __name__ == "__main__":
    main()

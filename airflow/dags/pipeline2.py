from airflow import DAG
from airflow.operators.python import PythonOperator, BranchPythonOperator
from airflow.utils.dates import days_ago
from datetime import timedelta
import pandas as pd
import ast
import pinecone
import pymssql
from airflow.models import Variable

def load_variables(ti):
    ti.xcom_push(key='pine_cone_api', value= Variable.get("pinecone_api"))
    ti.xcom_push(key='pine_cone_environment',value = Variable.get("environment"))
    ti.xcom_push(key='server', value= Variable.get("server"))
    ti.xcom_push(key='database', value = Variable.get("database"))
    ti.xcom_push(key='table', value = Variable.get("table"))
    ti.xcom_push(key='username', value = Variable.get("username"))
    ti.xcom_push(key='password', value = Variable.get("password"))
    ti.xcom_push(key='file_path' , value = Variable.get("df_var"))
    ti.xcom_push(key='operation' , value = Variable.get("operation"))

def insert_dataframe_to_sql(ti):
    file_path = ti.xcom_pull(key='file_path', task_ids='load_variables')
    df = pd.read_csv(file_path)
    # df["Embeddings"] = df["Embeddings"].apply(ast.literal_eval)
    df["combined_columns"] = df["File_Name"].astype(str) + df["SEC_Number"].astype(str) + df["Topic"].astype(str) + df ["PDF_Link"].astype(str) + df["Chunk_No"].astype(str)
    server = ti.xcom_pull(key='server', task_ids='load_variables')
    database = ti.xcom_pull(key='database', task_ids='load_variables')
    table = ti.xcom_pull(key='table', task_ids='load_variables')
    username = ti.xcom_pull(key='username', task_ids='load_variables')
    password = ti.xcom_pull(key='password', task_ids='load_variables')
    dataframe = df
    try:
        conn = pymssql.connect(server=server, database=database, user=username, password=password)
        cursor = conn.cursor()
        for index, row in dataframe.iterrows():
            values = {
                "combined_columns": row["combined_columns"],
                "File_Name": row["File_Name"],
                "SEC_Number": row["SEC_Number"],
                "Topic": row["Topic"],
                "PDF_Link": row["PDF_Link"],
                "Chunk_Content": row["Chunk_Content"],
                "Chunk_No": row["Chunk_No"]
            }
            merge_sql = """
                MERGE INTO {} AS target
                USING (
                    VALUES (
                        %(combined_columns)s,
                        %(File_Name)s,
                        %(SEC_Number)s,
                        %(Topic)s,
                        %(PDF_Link)s,
                        %(Chunk_Content)s,
                        %(Chunk_No)s
                    )
                ) AS source (combined_columns, File_Name, SEC_Number, Topic, PDF_Link, Chunk_Content, Chunk_No)
                ON target.combined_columns = source.combined_columns
                WHEN MATCHED THEN
                    UPDATE SET
                        target.File_Name = source.File_Name,
                        target.SEC_Number = source.SEC_Number,
                        target.Topic = source.Topic,
                        target.PDF_Link = source.PDF_Link,
                        target.Chunk_Content = source.Chunk_Content,
                        target.Chunk_No = source.Chunk_No
                WHEN NOT MATCHED THEN
                    INSERT (combined_columns, File_Name, SEC_Number, Topic, PDF_Link, Chunk_Content, Chunk_No)
                    VALUES (source.combined_columns, source.File_Name, source.SEC_Number, source.Topic, source.PDF_Link, source.Chunk_Content, source.Chunk_No);
            """.format(table)
            cursor.execute(merge_sql, values)
        conn.commit()
        print("Data inserted successfully.")
    except Exception as e:
        print("Error:", str(e))
    finally:
        cursor.close()
        conn.close()
        
def upsert_to_pinecone(ti):
    file_path = ti.xcom_pull(key='file_path', task_ids='load_variables')
    df = pd.read_csv(file_path)
    # df["Embeddings"] = df["Embeddings"].apply(ast.literal_eval)
    df["combined_columns"] = df["File_Name"].astype(str) + df["SEC_Number"].astype(str) + df["Topic"].astype(str) + df ["PDF_Link"].astype(str) + df["Chunk_No"].astype(str)    
    combined_columns_to_embeddings = {row["combined_columns"]: row["Embeddings"] for _, row in df.iterrows()}    
    server = ti.xcom_pull(key='server', task_ids='load_variables')
    database = ti.xcom_pull(key='database', task_ids='load_variables')
    table = ti.xcom_pull(key='table', task_ids='load_variables')
    username = ti.xcom_pull(key='username', task_ids='load_variables')
    password = ti.xcom_pull(key='password', task_ids='load_variables')
    pine_cone_api = ti.xcom_pull(key='pine_cone_api', task_ids='load_variables')
    pine_cone_environment = ti.xcom_pull(key='pine_cone_environment', task_ids='load_variables')
    pinecone.init(api_key=pine_cone_api, environment=pine_cone_environment)
    index_name = "test-index"
    existing_indexes = pinecone.list_indexes()
    if index_name not in existing_indexes:
        pinecone.create_index("test-index", dimension=768, metric="cosine")
    index = pinecone.Index("test-index")
    conn = pymssql.connect(server=server, database=database, user=username, password=password)
    cursor = conn.cursor()
    cursor.execute(f"SELECT * FROM {table}")
    upserted_count = 0
    for row in cursor:
        combined_columns = row[6]
        embeddings = combined_columns_to_embeddings.get(combined_columns)
        if embeddings:
            embedding_values = embeddings.strip('[]').split()
            embedding_floats = [float(value) for value in embedding_values]

            metadata = {
                "FileName": row[1],
                "SEC_Number": row[2]
            } 
            index.upsert(vectors=[{"id": str(row[0]), "values": embedding_floats}], metadata=metadata)  # Adjust as per your metadata
            upserted_count += 1
    conn.close()
    print(f"Upserted {upserted_count} records to Pinecone index.")
    
def delete_index_id(ti):
    pine_cone_api = ti.xcom_pull(key='pine_cone_api', task_ids='load_variables')
    pine_cone_environment = ti.xcom_pull(key='pine_cone_environment', task_ids='load_variables')
    pinecone.init(api_key=pine_cone_api, environment=pine_cone_environment)
    existing_indexes = pinecone.list_indexes()
    if 'test_index'  in existing_indexes:
       pinecone.delete_index('test-index')

    server = ti.xcom_pull(key='server', task_ids='load_variables')
    database = ti.xcom_pull(key='database', task_ids='load_variables')
    table = ti.xcom_pull(key='table', task_ids='load_variables')
    username = ti.xcom_pull(key='username', task_ids='load_variables')
    password = ti.xcom_pull(key='password', task_ids='load_variables')
    conn = pymssql.connect(server=server, database=database, user=username, password=password)
    cursor = conn.cursor()

    delete_query = f"TRUNCATE TABLE {table}"
    cursor.execute(delete_query)
    conn.commit()
    conn.close()
    
def select_upsert_or_delete_index(ti):
    if ti.xcom_pull(key='operation', task_ids='load_variables') == "delete":
        return 'delete_index'
    elif ti.xcom_pull(key='operation', task_ids='load_variables') == "upsert":
        return 'insert_dataframe_to_sql'

dag = DAG(
    dag_id="pipeline2",
    schedule="0 0 * * *",   # https://crontab.guru/
    start_date=days_ago(0),
    catchup=False,
    dagrun_timeout=timedelta(minutes=60),
    tags=["assignment3"],
    # params=user_input,
)

with dag:
    s1 = PythonOperator(
        task_id='load_variables',
        python_callable=load_variables,
        dag=dag
    )
    
    insert_in_sql = PythonOperator( 
        task_id='insert_dataframe_to_sql',
        python_callable=insert_dataframe_to_sql,
        dag=dag,
    )
    
    upsert_task = PythonOperator(
        task_id='upsert_to_pinecone',
        python_callable=upsert_to_pinecone,
        dag=dag,
    )
    
    delete_index_task = PythonOperator(
        task_id='delete_index',
        python_callable=delete_index_id,
        dag=dag,
    )
    
    branch = BranchPythonOperator(
        task_id='branch',
        python_callable=select_upsert_or_delete_index,
        dag=dag,
    )
    
    s1 >> branch
    branch >> delete_index_task
    branch >> insert_in_sql >> upsert_task
    
    
    
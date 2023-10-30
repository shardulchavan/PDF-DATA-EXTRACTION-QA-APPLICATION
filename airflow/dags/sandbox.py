import os
from airflow.models import DAG
from airflow.operators.bash_operator import BashOperator
from airflow.operators.python_operator import PythonOperator
from airflow.utils.dates import days_ago
from datetime import timedelta
import requests
from bs4 import BeautifulSoup
from pyngrok import ngrok, conf
from airflow.models import Variable
from PyPDF2 import PdfReader
import io
import subprocess
import pandas as pd


#############################################################################################################

def scrape_pdf_links():
    base_url = "https://www.sec.gov"
    target_url = f"{base_url}/forms"

    response = requests.get(target_url)
    soup = BeautifulSoup(response.content, 'html.parser')

    records = []

    # Iterate through all table rows in the table's body
    for row in soup.select('table tbody tr')[3:8]:
        # Extract link
        link_element = row.find('a', href=True)
        link = link_element['href'] if link_element else None
        link = base_url + link if link and link.startswith('/') else link

        # Extract form name from link
        file_name = os.path.basename(link).replace('.pdf', '') if link else None

        # Extract SEC number
        sec_cell = row.find('td', class_='list-page-detail-content views-field views-field-field-list-page-det-secarticle')
        sec_number = sec_cell.find('p').get_text(strip=True) if sec_cell and sec_cell.find('p') else None

        # Extract topic
        topic_cell = row.find('td', class_='views-field views-field-term-node-tid')
        topic = topic_cell.get_text(strip=True).replace('Topic(s):', '') if topic_cell else None


        records.append({
            'File_Name': file_name,
            'SEC_Number': sec_number,
            'Topic': topic,
            'PDF_Link': link
        })

    df = pd.DataFrame(records)
    return df


def get_pdf_content_from_link(pdf_link):
    response = requests.get(pdf_link)
    return response.content

def extract_pdf_content_using_pypdf(row):
    pdf_link = row['PDF_Link']
    content = get_pdf_content_from_link(pdf_link)
    reader = PdfReader(io.BytesIO(content))
    data = []
    total_tokens = 0
    for page_num in range(len(reader.pages)):
        page_content = reader.pages[page_num].extract_text() if reader.pages[page_num].extract_text() else ""
        page_tokens = len(page_content.split())
        total_tokens += page_tokens
        data.append({
            'File_Name': row['File_Name'],
            'SEC_Number': row['SEC_Number'],
            'Topic': row['Topic'],
            'PDF_Link': pdf_link,
            'Page_No': page_num + 1,
            'Page_Content': page_content,
            'Number_of_Words': len(page_content.split()),
            'Total_Tokens_in_PDF': total_tokens
        })
    return data


def process_task():
    # read the dataframe from the CSV or Parquet file
    df = pd.read_parquet('/tmp/intermediate_df.parquet')
    final_pypdf_df = process_dataframe_Pypdf_links(df)
    print(final_pypdf_df)
    final_pypdf_df.to_csv('final_output.csv', index=False)

# to process pdf using pypdf
def process_dataframe_Pypdf_links(input_df):
    all_data = []
    for _, row in input_df.iterrows():
        all_data.extend(extract_pdf_content_using_pypdf(row))
    return pd.DataFrame(all_data)


# extraction using nougat
def text_extraction_from_link_new(row, output_directory='./extracted_files'):
    os.makedirs(output_directory, exist_ok=True)
    
    # Get the list of links
    pdf_links = scrape_pdf_links()

    # If you want to process only 5 links, take the first 5 links
    # pdf_links = pdf_links[:5]

    all_extracted_data = []

    for _, row in pdf_links_df.iterrows():
        file_link = row['PDF_Link']
        print(f"Processing link: {file_link}")
        
        # Download the PDF and save to the output directory
        file_response = requests.get(file_link)
        file_response.raise_for_status()
        
        file_name = os.path.join(output_directory, file_link.split('/')[-1])
        with open(file_name, 'wb') as f:
            f.write(file_response.content)

        # Execute the nougat command
        command = ["nougat", file_name, "-o", output_directory]
        result = subprocess.run(command, capture_output=True, text=True)

        # Check if the command was successful
        if result.returncode != 0:
            print("Nougat processing failed for link:", file_link)
            print(result.stderr)
            continue  # move to the next link

        # Print Nougat's stdout for debugging
        print("Nougat stdout:", result.stdout)

        # Check the filenames in the output directory to verify Nougat's output
        print("Files in output directory:", os.listdir(output_directory))
        # Load the extracted content from the output directory
        extracted_file_path = os.path.join(output_directory, os.path.basename(file_name).replace('.pdf', '.mmd'))
        
        if not os.path.exists(extracted_file_path):
            print(f"Expected extracted file {extracted_file_path} not found!")
            continue  # move to the next link

        with open(extracted_file_path, 'r') as f:
            extracted_data = f.read()

        all_extracted_data.append(extracted_data)
        print(f"Data extracted for link: {file_link}")

    return all_extracted_data

    # Load the extracted content from the output directory
    extracted_file_path = os.path.join(output_directory, os.path.basename(file_name).replace('.pdf', '.txt'))
    
    if not os.path.exists(extracted_file_path):
        print(f"Expected extracted file {extracted_file_path} not found!")
        return None

    with open(extracted_file_path, 'r') as f:
        extracted_data = f.read()

    print(extracted_data)
    return extracted_data

# to process pdf using nougat
def process_dataframe_Nougat_links(input_df):
    all_data = []
    for _, row in input_df.iterrows():
        all_data.extend(extract_pdf_content_using_pypdf(row))
    return pd.DataFrame(all_data)


# Define tasks
def scrape_task():
    df = scrape_pdf_links()
    # save the dataframe to a CSV or Parquet file
    df.to_parquet('/tmp/intermediate_df.parquet', index=False)

    

def process_nougat_task():
    # read the dataframe from the CSV or Parquet file
    df = pd.read_parquet('/tmp/intermediate_df.parquet')
    final_nougat_df = process_dataframe_Nougat_links(df)
    print(final_nougat_df)
    final_nougat_df.to_csv('final_output.csv', index=False)
    # Optionally, you can save the final_df to another location or perform other tasks

#############################################################################################################






dag = DAG(
    dag_id="sandbox",
    schedule="0 0 * * *",   # https://crontab.guru/
    start_date=days_ago(0),
    catchup=False,
    dagrun_timeout=timedelta(minutes=60),
    tags=["labs", "damg7245"],
    # params=user_input,
)

with dag:
    t1 = PythonOperator(
        task_id='scrape_pdf_links_task',
        python_callable=scrape_task,
        dag=dag
    )

    t2 = PythonOperator(
        task_id='process_pdf_links_task',
        python_callable=process_task,
        dag=dag
    )


    extarct_pdf_nougat = PythonOperator(
        task_id='extract_pdf_nougat',
        python_callable=text_extraction_from_link_new
    )

    bye_world = BashOperator(
    task_id="bye_world",
    bash_command='echo "bye from airflow"'
    )

    # Flow
    t1 >> t2 >> extarct_pdf_nougat >> bye_world






# def text_extraction_from_link_new(file_link):
#     file_response = requests.get(file_link)
#     file_response.raise_for_status()  # Check for any HTTP errors.
#     file_content = file_response.content
#     reader = PdfReader(io.BytesIO(file_content))
#     metadata = reader.metadata  # Using the new 'metadata' attribute
#     title = metadata.get('/Title', None)  # Extract the title from the metadata dictionary
#     print(title)
#     number_of_pages  = len(reader.pages)
#     extracted_data=""
#     num_words = 0
#     for page_num in range(1, number_of_pages+1):
#         params = {
#             'start': page_num,
#             'stop': page_num
#         }

#         nougat_response = requests.post(nougat_api_url+"/predict", headers=headers, files=files, params=params)
#         if nougat_response.status_code == 200:
#             extracted_data = title + extracted_data + nougat_response.text
#             num_words += len(nougat_response.text.split())
#             break
#         else:
#             print("Request failed with status code:" + str(nougat_response.status_code))
#             print(nougat_response.text)
#             request_counter += 1
#     if request_counter == 3:
#         return "Error in nougat api"
#     print(extracted_data)
#     return extracted_data


# def setup_ngrok_and_variable():
#     conf.get_default().auth_token = "2X2iUKS8w5UoLeLQ4R4Rw1Mm27M_3yi3rkFDWqy1gdtufgLdV"  # Consider securing your auth_token
#     port = 8503
#     public_url = ngrok.connect(port).public_url
#     print(f"Your ngrok link is: '{public_url}'")
#     return public_url
#     # Variable.set("nougat_api_url", public_url)
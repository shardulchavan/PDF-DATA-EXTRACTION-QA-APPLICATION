import os, requests, io, subprocess, pandas as pd, re, torch, yaml, shutil
from airflow.models import DAG
from airflow.operators.bash_operator import BashOperator
from airflow.operators.python_operator import PythonOperator, BranchPythonOperator
from airflow.utils.dates import days_ago
from datetime import timedelta
from bs4 import BeautifulSoup
from pyngrok import ngrok, conf
from airflow.models import Variable
from PyPDF2 import PdfReader
from transformers import LongformerTokenizer, LongformerModel

def load_config(ti):
    with open('./config/pipeline1_config.yaml', 'r') as file:
        config = yaml.safe_load(file)
    ti.xcom_push(key='config', value=config)

def scrape_pdf_links(config):
    base_url = config['base_url']
    target_url = f"{base_url}/forms"
    file_urls = config['file_urls']
    response = requests.get(target_url)
    soup = BeautifulSoup(response.content, 'html.parser')
    records = []
    # Iterate through all table rows in the table's body
    for row in soup.select('table tbody tr'):
        # Extract link
        link_element = row.find('a', href=True)
        link = link_element['href'] if link_element else None
        full_link = base_url + link if link and link.startswith('/') else link

        # Check if the full_link is in the list of file_urls before processing the row
        if full_link in file_urls:
            file_name = os.path.basename(full_link).replace('.pdf', '') if full_link else None

            sec_cell = row.find('td', class_='list-page-detail-content views-field views-field-field-list-page-det-secarticle')
            sec_number = sec_cell.find('p').get_text(strip=True) if sec_cell and sec_cell.find('p') else None

            topic_cell = row.find('td', class_='views-field views-field-term-node-tid')
            topic = topic_cell.get_text(strip=True).replace('Topic(s):', '') if topic_cell else None

            records.append({
                'File_Name': file_name,
                'SEC_Number': sec_number,
                'Topic': topic,
                'PDF_Link': full_link
            })

    df = pd.DataFrame(records)
    return df

def scrape_task(ti):
    os.makedirs("./data/tmp", exist_ok=True)
    config = ti.xcom_pull(key='config', task_ids='load_config')
    df = scrape_pdf_links(config)
    # save the dataframe to a CSV or Parquet file
    df.to_parquet('./data/tmp/scraped_links_data.parquet', index=False)
    
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
            'Chunk_No': page_num + 1,
            'Chunk_Content': page_content,
            'Number_of_Words': len(page_content.split()),
            'Total_Tokens_in_PDF': total_tokens
        })
    return data    

def process_dataframe_Pypdf_links(input_df):
    all_data = []
    for _, row in input_df.iterrows():
        all_data.extend(extract_pdf_content_using_pypdf(row))
    return pd.DataFrame(all_data)    

def extract_sections_new3(wiki_text: str) -> list:
    if not wiki_text:
        return []

    # Find all headings in the format **HEADING**
    headings = re.findall(r"\*\*[^*]+\*\*|### [^#]+ ###|## [^#]+ ##", wiki_text)
    contents = re.split(r"\*\*[^*]+\*\*", wiki_text)[1:]
    contents = [c.replace("{", "").replace("}", "").strip() for c in contents]  # Remove extraneous curly braces
    assert len(headings) == len(contents)

    # Create a list of (title, section_name, content, token_count) for each section
    sections = [( h.replace('**', '').strip(), c, len(c.split())) for h, c in zip(headings, contents)]

    return sections

def text_extraction_from_link_new(row, output_directory='./data/tmp/extracted_files'):
  os.makedirs(output_directory, exist_ok=True)
  all_extracted_data=[]
  file_link = row['PDF_Link']

  file_response = requests.get(file_link)
  file_response.raise_for_status()
  
  file_name = os.path.join(output_directory, file_link.split('/')[-1])
  with open(file_name, 'wb') as f:
      f.write(file_response.content)

  command = ["nougat", file_name, "-o", output_directory]
  result = subprocess.run(command, capture_output=True, text=True)

  if result.returncode != 0:
      print("Nougat processing failed for link:", file_link)
      print(result.stderr)

  extracted_file_path = os.path.join(output_directory, os.path.basename(file_name).replace('.pdf', '.mmd'))

  if not os.path.exists(extracted_file_path):
      print(f"Expected extracted file {extracted_file_path} not found!")
      return []

  with open(extracted_file_path, 'r') as f:
      extracted_data = f.read()

  # Split the extracted data into sections
  sections = extract_sections_new3(extracted_data)

  # Prepare data for each section
  data = []
  total_tokens = 0
  for section_num, (heading, content,tokens) in enumerate(sections, start=1):
      total_tokens += tokens
      data.append({
          'File_Name': row['File_Name'],
          'SEC_Number': row['SEC_Number'],
          'Topic': row['Topic'],
          'PDF_Link': file_link,
          'Chunk_No': section_num,
          'Chunk_Content': heading + "\n" + content,
          'Number_of_Words': tokens,
          'Total_Tokens_in_PDF': total_tokens
      })

  return data

def process_dataframe_Nougat_links(input_df):
    all_data = []
    for _, row in input_df.iterrows():
        all_data.extend(text_extraction_from_link_new(row))
    return pd.DataFrame(all_data)
    
def process_pdf_task(ti):
    config = ti.xcom_pull(key='config', task_ids='load_config')
    df = pd.read_parquet('./data/tmp/scraped_links_data.parquet')
    if config['processing_option'] == "nougat":
        final_df = process_dataframe_Nougat_links(df)
    elif config['processing_option'] == "pypdf":
        final_df = process_dataframe_Pypdf_links(df)
    final_df.to_csv('./data/tmp/processed_data_for_embedding.csv', index=False)
    
def get_embedding(text, model, tokenizer, device):
    tokens = tokenizer.encode(text, return_tensors='pt', truncation=True, max_length=4096).to(device)
    
    if len(tokens[0]) > 4096:
        print("Warning: Text is too long, truncating...")
        
    with torch.no_grad():
        outputs = model(tokens)
        # Return the average of the embeddings and its dimension
        return outputs.last_hidden_state.mean(dim=1).cpu().numpy(), outputs.last_hidden_state.shape[-1]

def generate_embeddings():
    df = pd.read_csv('./data/tmp/processed_data_for_embedding.csv')
    # Initialize model and tokenizer
    model_name = "allenai/longformer-base-4096"
    model = LongformerModel.from_pretrained(model_name)
    tokenizer = LongformerTokenizer.from_pretrained(model_name)

    # Set device
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = model.to(device)
    model.eval()

    # Batch processing
    batch_size = 2
    embeddings = []
    dimensions = []

    for i in range(0, len(df), batch_size):
        batch_texts = df['Chunk_Content'].iloc[i:i+batch_size].tolist()
        batch_data = [get_embedding(text, model, tokenizer, device) for text in batch_texts]

        for emb, dim in batch_data:
            embeddings.append(emb)
            dimensions.append(dim)

    df['Embeddings'] = embeddings
    df['Embedding_Dimension'] = dimensions

    # Save to CSV
    df.to_csv('./data/final_embeddings.csv', index=False)
    
def delete_tmp_directory():
    directory_path = './data/tmp'
    shutil.rmtree(directory_path, ignore_errors=True)


dag = DAG(
    dag_id="pipeline1",
    schedule="0 0 * * *",   # https://crontab.guru/
    start_date=days_ago(0),
    catchup=False,
    dagrun_timeout=timedelta(minutes=60),
    tags=["assignment3"],
    # params=user_input,
)

with dag:
    s1 = PythonOperator(
        task_id='load_config',
        python_callable=load_config,
        dag=dag
    )
    
    s2 = PythonOperator(
        task_id='scrape_pdf_links_task',
        python_callable=scrape_task,
        dag=dag
    )
    
    s3 = PythonOperator(
        task_id='process_pdf',
        python_callable=process_pdf_task,
        dag=dag
    )
    
    s4 = PythonOperator(
        task_id='generate_embeddings',
        python_callable=generate_embeddings,
        dag=dag
    )
    
    s5 = PythonOperator(
        task_id='delete_tmp_directory',
        python_callable=delete_tmp_directory,
        dag=dag,
    )
    
    s1 >> s2 >> s3 >> s4 >> s5
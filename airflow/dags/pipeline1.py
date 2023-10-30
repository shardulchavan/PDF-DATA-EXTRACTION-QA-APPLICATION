import pandas as pd
import io
from PyPDF2 import PdfReader
import requests
import os
from bs4 import BeautifulSoup

def text_extraction_from_link_new(file_link= None, output_directory='./extracted_files'):
    os.makedirs(output_directory, exist_ok=True)
    
    # Get the list of links
    pdf_links = scrape_pdf_links()

    # If you want to process only 5 links, take the first 5 links
    # pdf_links = pdf_links[:5]

    all_extracted_data = []

    for file_link in pdf_links:
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
    
def get_pdf_content_from_link()->str:
    links = scrape_pdf_links()
    for link in links:
        print(f"Processing link: {link}")
        file_response = requests.get(link)
        file_response.raise_for_status()  # Check for any HTTP errors.
    return file_response.content

def extract_pdf_content_using_pypdf():
    content = get_pdf_content_from_link()
    extracted_text=""
    num_words=0
    reader = PdfReader(io.BytesIO(content))
    number_of_pages  = len(reader.pages)
    for page_num in range(number_of_pages):
        page = reader.pages[page_num]
        extracted_text += page.extract_text()
        num_words += len(extracted_text.split())
    print(extracted_text,num_words)
    return extracted_text, num_words

def scrape_pdf_links():
    base_url = "https://www.sec.gov"
    target_url = f"{base_url}/forms"

    response = requests.get(target_url)
    soup = BeautifulSoup(response.content, 'html.parser')

    records = []

    # Iterate through all table rows in the table's body
    for row in soup.select('table tbody tr')[3:15]:
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


# Define DAG
dag = DAG(
    'sec_pdf_scraper',
    default_args=default_args,
    description='Scrapes SEC PDF links and extracts content',
    schedule_interval=None,  # This means the DAG will not run automatically but can be triggered manually
    catchup=False
)

# Set up the task sequence
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

# Set task sequence
t1 >> t2
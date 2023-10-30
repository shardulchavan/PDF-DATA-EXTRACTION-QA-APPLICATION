from dotenv import load_dotenv
import openai, pathlib, os

env_path = pathlib.Path('.') / '.env'
load_dotenv(dotenv_path=env_path)

EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL")
GPT_MODEL = os.getenv("GPT_MODEL")

def embed_user_query(user_query: str):
    embedded_query = openai.Embedding.create(input=user_query,model=EMBEDDING_MODEL)
    query_embedding = embedded_query["data"][0]['embedding']
    print(len(query_embedding))
    return query_embedding

def build_prompt(context: str, user_query: str) -> str:
    return (f"The following is the content for your reference:\n"
                   f"{context}\n\n"
                   f"Based on the above content, please answer the question below concisely and clearly. "
                   f"If the information isn't available in the content, just respond with 'Context not Enough' and do not specify anything else"
                   f"If found, Ensure the answer in not more than 50 tokens.\n\n"
                   f"Question:\n{user_query}")
    
def ask_openai_model(prompt: str)-> str:
    response = openai.ChatCompletion.create(
        model=GPT_MODEL,
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": prompt}
        ],
        max_tokens=100
    )
    return response['choices'][0]['message']["content"]
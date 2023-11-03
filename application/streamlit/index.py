import streamlit as st
import requests, pathlib, os
from dotenv import load_dotenv
from request_utils import get_request, post_request

env_path = pathlib.Path('.') / '.env'
load_dotenv(dotenv_path=env_path)

FASTAPI_HOST = os.getenv('FASTAPI_HOST')

def login_page():
    st.title('LOGIN')
    username = st.text_input('Username')
    password = st.text_input('Password', type='password')
    
    if st.button('Login'):
        data = {'username': username, 'password': password}
        response = post_request(url=FASTAPI_HOST+'/login', data=data, headers=None)
        if response is None:
            st.error("Invalid credentials")
            
        elif response.status_code == 200:
            token = response.json()['token']
            st.session_state['token'] = token
            st.session_state['page'] = 'landing' 
            st.rerun()
        else:
            st.error("Something went wrong!!!")
        
    if st.button('New here? Sign up!!'):
        st.session_state['page'] = 'register'
        st.rerun()
       
            
def register_page():
    st.title('Sign Up')
    full_name = st.text_input('Full Name')
    email = st.text_input('Email')
    username = st.text_input('Username')
    password = st.text_input('Password', type='password')
    
    if st.button('REGISTER'):
        request_body = {
            "fullname": full_name,
            "email": email,
            "username": username,
            "password": password,
            "is_active": True
        }
        response = post_request(url=FASTAPI_HOST+'/register', data=request_body)
        if response.status_code == 201:
            st.session_state['page'] = 'login'
            st.rerun()
        elif response.status_code == 400:
            st.error("Username already exists")
        else:
            st.error("Something went wrong!!!")
          

def landing_page():
    if 'token' not in st.session_state:
        st.session_state['page'] = 'login' 
        st.rerun()
    if 'messages' in st.session_state:
        del st.session_state['messages']
    st.title('Welcome to Sec-GPT')
    auth_token =  "Bearer "+ st.session_state['token']
    headers = {
        "accept": "application/json",
        "Authorization": auth_token,
        "Content-Type": "application/json" 
    }
    filters=get_request(FASTAPI_HOST+'/get_all_filter',headers=headers,params=None)
    if filters is None:
        del st.session_state['token']
        st.session_state['page'] = 'login' 
        st.rerun() 
    file_filter_option = [item for sublist in filters.json()['file_names'] for item in sublist]
    st.session_state['file_filter'] = st.multiselect("Please select a pdf from the below option",options=file_filter_option)
    sec_no_filter_option = [item for sublist in filters.json()['sec_no'] for item in sublist]
    st.session_state['sec_no_filter'] = st.multiselect("Apply sec no filter",options=sec_no_filter_option)
    if st.button('Submit'):
        st.session_state['page'] = 'chat' 
        st.rerun()    
    if st.button('LogOut'):
        del st.session_state['token']
        st.session_state['page'] = 'login' 
        st.rerun()  


def chat_page():
    if 'messages' not in st.session_state:
        st.session_state['messages'] = []
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])    
    
    if user_query:= st.chat_input("Ask a question!!"):
        st.session_state.messages.append({"role": "user", "content": user_query})
        with st.chat_message("user"):
            st.markdown(user_query)
        request_body = {
            "query": user_query,
            "file_name": st.session_state['file_filter'],
            "sec_no": st.session_state['sec_no_filter'],
        }
        auth_token =  "Bearer "+ st.session_state['token']
        headers = {
            "accept": "application/json",
            "Authorization": auth_token,
            "Content-Type": "application/json" \
        }
        openai_response = post_request(url=FASTAPI_HOST+'/chat', data=request_body, headers=headers)
        if openai_response is None:
            del st.session_state['token']
            del st.session_state['file_filter']
            del st.session_state['sec_no_filter']
            st.session_state['page'] = 'login' 
            st.rerun() 
        st.session_state.messages.append({"role": "assistant", "content": openai_response.json()['response']})
        with st.chat_message("assistant"):
            st.markdown(openai_response.json()['response'])
    if st.button("Return"):
        del st.session_state['file_filter']
        del st.session_state['sec_no_filter']
        st.session_state['page'] = 'landing' 
        st.rerun()
    if st.button('LogOut'):
        del st.session_state['token']
        st.session_state['page'] = 'login' 
        st.rerun() 
          

def main():
    # st.session_state['page'] = 'landing'    
    if 'page' not in st.session_state:
        st.session_state['page'] = 'landing'    
    if st.session_state['page'] == 'login':
        login_page()
    elif st.session_state['page'] == 'register':
        register_page()
    elif st.session_state['page'] == 'landing':
        landing_page()
    elif st.session_state['page'] == 'chat':
        chat_page()
    else:
        st.error('Unknown page: %s' % st.session_state['page'])

if __name__ == '__main__':
    main()

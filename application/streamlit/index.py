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
        if response.status_code == 200:
            token = response.json()['token']
            st.session_state['token'] = token  # Store token in session state
            st.session_state['page'] = 'page1' # Set current page to page1
            st.rerun()
        elif response.status_code == 401:
            st.error("Invalid credentials")
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
          
    

def qna_page():
    st.title('Welcome to Sec-GPT')
    option = ["PDF 1", "PDF 2", "PDF 3", "PDF 4"]
    selected_options = st.multiselect("Please select a pdf from the below option",options=option)
    user_query = st.text_input('Ask your question!!')
    if st.button('Submit'):
        st.write("Wait")






def main():
    st.session_state['page'] = 'page1'    
    if 'page' not in st.session_state:
        st.session_state['page'] = 'login'    
    if st.session_state['page'] == 'login':
        login_page()
    elif st.session_state['page'] == 'register':
        register_page()
    elif st.session_state['page'] == 'page1':
        qna_page()
    else:
        st.error('Unknown page: %s' % st.session_state['page'])

if __name__ == '__main__':
    main()

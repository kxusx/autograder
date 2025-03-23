import streamlit as st
from pdf2image import convert_from_bytes
import PyPDF2
import io
from PIL import Image
import numpy as np
import google.generativeai as genai
import os
from dotenv import load_dotenv
import json
from authlib.integrations.requests_client import OAuth2Session
import requests
from urllib.parse import urlencode


# Load environment variables
load_dotenv()
GEMINI_API_KEY = os.getenv('gemini-key')
AUTH0_CLIENT_ID = os.getenv('AUTH0_CLIENT_ID')
AUTH0_CLIENT_SECRET = os.getenv('AUTH0_CLIENT_SECRET')
AUTH0_DOMAIN = os.getenv('AUTH0_DOMAIN')
AUTH0_CALLBACK_URL = os.getenv('AUTH0_CALLBACK_URL')
AUTH0_LOGOUT_URL = os.getenv('AUTH0_LOGOUT_URL')

oauth = OAuth2Session(
        client_id=AUTH0_CLIENT_ID, 
        client_secret=AUTH0_CLIENT_SECRET,
        client_kwargs={
            "scope": "openid profile email",
        },
        server_metadata_url=f'https://{AUTH0_DOMAIN}/.well-known/openid-configuration',
        redirect_uri=AUTH0_CALLBACK_URL)


# Configure Gemini
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-2.0-flash-exp-image-generation')

# Initialize session state for auth
if 'user' not in st.session_state:
    st.session_state.user = None

def extract_text_from_handwritten_pdf(pdf_file):
    # Convert PDF to images
    images = convert_from_bytes(pdf_file.read())
    text = ""
    
    # Process each page
    for i, image in enumerate(images):
        st.write(f"Processing page {i+1}...")
        
        # Convert to RGB (Gemini requires RGB images)
        rgb_image = image.convert('RGB')
        
        # Create prompt for Gemini
        prompt = """
        Please extract all the text from this handwritten answer sheet image.
        Return only the extracted text, without any additional commentary.
        Be as accurate as possible in reading the handwriting.
        """
        
        # Get response from Gemini
        try:
            response = model.generate_content([prompt, rgb_image])
            page_text = response.text
            text += page_text + "\n\n--- Page Break ---\n\n"
        except Exception as e:
            st.error(f"Error processing page {i+1}: {str(e)}")
            continue
    
    return text

def extract_text_from_digital_pdf(pdf_file):
    try:
        # Reset file pointer to beginning
        pdf_file.seek(0)
        pdf_reader = PyPDF2.PdfReader(pdf_file)
        
        if len(pdf_reader.pages) == 0:
            raise ValueError("PDF file contains no pages")
            
        text = ""
        for page in pdf_reader.pages:
            try:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
            except Exception as e:
                st.warning(f"Warning: Could not extract text from a page: {str(e)}")
                continue
                
        if not text:
            raise ValueError("No text could be extracted from the PDF")
            
        return text
    except Exception as e:
        raise Exception(f"Error reading PDF file: {str(e)}")

def login():
    # Generate a secure random state parameter and store it in session state
    if 'auth_state' not in st.session_state:
        import secrets
        st.session_state.auth_state = secrets.token_urlsafe(16)
    
    auth_url = f"https://{AUTH0_DOMAIN}/authorize?" + urlencode({
        "response_type": "code",
        "client_id": AUTH0_CLIENT_ID,
        "redirect_uri": AUTH0_CALLBACK_URL,
        "scope": "openid profile email",
        "state": st.session_state.auth_state
    })
    
    st.link_button("Login with Auth0", auth_url)

def handle_auth_callback():
    # Get query parameters
    query_params = st.experimental_get_query_params()
    code = query_params.get("code", [None])[0]
    state = query_params.get("state", [None])[0]
    
    # # Verify state to prevent CSRF attacks
    # if state != st.session_state.get("auth_state"):
    #     st.error("Invalid state parameter. Possible CSRF attack.")
    #     return
    
    if code:
        try:
            # Form data must be properly URL-encoded
            token_url = f"https://{AUTH0_DOMAIN}/oauth/token"
            payload = {
                "grant_type": "authorization_code",
                "client_id": AUTH0_CLIENT_ID,
                "client_secret": AUTH0_CLIENT_SECRET,
                "code": code,
                "redirect_uri": AUTH0_CALLBACK_URL
            }
            
            # Make sure to set the correct content type
            headers = {"Content-Type": "application/x-www-form-urlencoded"}
            
            # Log the request for debugging (remove in production)
            st.write(f"Sending token request to: {token_url}")
            st.write(f"Redirect URI: {AUTH0_CALLBACK_URL}")
            
            # Send the request
            response = requests.post(
                token_url, 
                data=payload,
                headers=headers
            )
            
            # Check response status
            if response.status_code != 200:
                st.error(f"Token request failed with status code: {response.status_code}")
                st.write(f"Response: {response.text}")
                return
                
            tokens = response.json()
            
            if 'error' in tokens:
                st.error(f"Authentication error: {tokens.get('error_description', tokens['error'])}")
                return
                
            # Get user info
            user_url = f"https://{AUTH0_DOMAIN}/userinfo"
            headers = {"Authorization": f"Bearer {tokens['access_token']}"}
            user_info = requests.get(user_url, headers=headers).json()
            
            # Store in session state
            st.session_state.user = user_info
            st.session_state.access_token = tokens['access_token']
            
            # Clear query parameters by using rerun
            st.experimental_set_query_params()
            st.rerun()
        except Exception as e:
            st.error(f"Authentication error: {str(e)}")
            import traceback
            st.write(traceback.format_exc())
    else:
        st.error("No authorization code received from Auth0")

def logout():
    logout_url = f"https://{AUTH0_DOMAIN}/v2/logout?" + urlencode({
        "client_id": AUTH0_CLIENT_ID,
        "returnTo": AUTH0_LOGOUT_URL
    })
    st.session_state.user = None
    st.session_state.access_token = None
    st.link_button("Logout", logout_url)

def show_user_info():
    if st.session_state.user:
        st.sidebar.write(f"Welcome, {st.session_state.user.get('name', 'User')}")
        st.sidebar.image(st.session_state.user.get('picture', ''), width=50)
        st.sidebar.button("Logout", on_click=logout)
    else:
        login()


def main():
    st.title("TAMU AutoGrader")
    
    # Handle Auth0 callback if code parameter is present
    query_params = st.experimental_get_query_params()
    if "code" in query_params:
        handle_auth_callback()
    else:
        # Display login/user info in sidebar
        show_user_info()
        
        # Only show app content if user is authenticated
        if st.session_state.user:
            # First get the number of students
            num_students = st.number_input("How many student answer sheets would you like to upload?", 
                                        min_value=1, 
                                        max_value=50,  # You can adjust this limit
                                        value=1)
            
            # Upload answer key first
            key_pdf = st.file_uploader("Upload Answer Key (Digital PDF)", type=['pdf'])
            
            # Create a dictionary to store all student data
            students_data = {}
            
            # Create file uploaders for each student
            for i in range(int(num_students)):
                student_name = st.text_input(f"Enter Student {i+1}'s Name", key=f"student_name_{i}")
                student_pdf = st.file_uploader(f"Upload Student {i+1}'s Answer Sheet", 
                                            type=['pdf'],
                                            key=f"student_pdf_{i}")
                
                if student_name and student_pdf:
                    students_data[student_name] = {"pdf": student_pdf}

            if key_pdf is not None and len(students_data) > 0:
                st.write("Files uploaded successfully!")
                
                try:
                    # Process answer key using PyPDF2
                    with st.spinner("Processing answer key..."):
                        key_pdf.seek(0)
                        key_text = extract_text_from_digital_pdf(key_pdf)
                    
                    # Process each student's submission
                    for student_name, data in students_data.items():
                        with st.spinner(f"Processing {student_name}'s answers..."):
                            data['pdf'].seek(0)
                            student_text = extract_text_from_handwritten_pdf(data['pdf'])
                            students_data[student_name]['text'] = student_text
                            
                            # Generate comparison right away
                            comparison_prompt = f"""
                            Compare the following student answers with the answer key.
                            Provide a short analysis of matching and non-matching answers.
                            Calculate an approximate score and provide it as "Score: score/100". 

                            Student Answers:
                            {student_text}

                            Answer Key:
                            {key_text}
                            """
                            
                            comparison_response = model.generate_content(comparison_prompt)
                            students_data[student_name]['analysis'] = comparison_response.text

                    # Display results in expandable sections
                    st.subheader("Answer Key")
                    with st.expander("View Answer Key"):
                        st.text_area("Content", key_text, height=200)
                        key_pdf.seek(0)
                        images = convert_from_bytes(key_pdf.read())
                        for i, image in enumerate(images):
                            st.image(image, caption=f"Page {i+1}", use_column_width=True)

                    st.subheader("Student Submissions")
                    
                    # Display student submissions
                    for student_name, data in students_data.items():
                        with st.expander(f"📝 {student_name}"):
                            # Create tabs for different views
                            tabs = st.tabs(["AI Analysis", "Transcribed Answer", "Original PDF"])
                            
                            with tabs[0]:
                                st.write("AI Analysis:")
                                st.write(data['analysis'])
                            
                            with tabs[1]:
                                st.text_area("Transcribed Content", data['text'], height=200)
                            
                            with tabs[2]:
                                data['pdf'].seek(0)
                                images = convert_from_bytes(data['pdf'].read())
                                for i, image in enumerate(images):
                                    st.image(image, caption=f"Page {i+1}", use_column_width=True)

                    # Add download button for results
                    if st.button("Download All Results"):
                        results_text = "Answer Sheet Analysis Results\n\n"
                        results_text += f"Answer Key:\n{key_text}\n\n"
                        for student_name, data in students_data.items():
                            results_text += f"\n{'='*50}\n"
                            results_text += f"Student: {student_name}\n"
                            results_text += f"Analysis:\n{data['analysis']}\n"
                            results_text += f"Transcribed Answer:\n{data['text']}\n"
                        
                        st.download_button(
                            label="Download Results as Text",
                            data=results_text,
                            file_name="grading_results.txt",
                            mime="text/plain"
                        )

                except Exception as e:
                    st.error(f"An error occurred during processing: {str(e)}")
                    st.write("Please make sure all PDF files are valid and not corrupted.")
        else:
            st.warning("Please log in to use the PDF Answer Sheet Comparison tool.")

if __name__ == "__main__":
    main()

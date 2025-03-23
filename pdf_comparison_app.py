import streamlit as st
from pdf2image import convert_from_bytes
import PyPDF2
import google.generativeai as genai
import os
from dotenv import load_dotenv
from authlib.integrations.requests_client import OAuth2Session
import requests
from urllib.parse import urlencode
import pandas as pd

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
model = genai.GenerativeModel('gemini-2.0-flash-exp-image-generation', generation_config={
    'temperature': 1.0
})

# Initialize session state for auth
if 'user' not in st.session_state:
    st.session_state.user = None

def extract_text_from_pdf(pdf_file, is_handwritten=True):
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
        Please extract all the text from this image.
        Return only the extracted text, without any additional commentary.
        Be as accurate as possible in reading the text.
        """
        if is_handwritten:
            prompt = """
            Please extract all the text from this handwritten answer sheet image.
            Return only the extracted text, without any additional commentary.
            Be as accurate as possible in reading the handwriting.
            """
        
        # Get response from Gemini
        try:
            response = model.generate_content([prompt, rgb_image], generation_config={
                'temperature': 1.0
            })
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

def get_student_name(filename):
    # Remove .pdf extension and return the filename as student name
    return filename.replace('.pdf', '')

def extract_score(analysis_text):
    try:
        # Find the last occurrence of "Total Score:" and extract just the score portion
        score = "N/A"
        if "Total Score:" in analysis_text:
            score = analysis_text.split("Total Score:")[-1].strip().split('\n')[0]
        elif "Total score:" in analysis_text:
            score = analysis_text.split("Total score:")[-1].strip().split('\n')[0]
        elif "Total Score : " in analysis_text:
            score = analysis_text.split("Total Score : ")[-1].strip().split('\n')[0]
        elif "Total Score :" in analysis_text:
            score = analysis_text.split("Total Score :")[-1].strip().split('\n')[0]
        
        # Clean up the score by removing any non-numeric characters except '/'
        cleaned_score = ''.join(char for char in score if char.isdigit() or char == '/')
        
        # If we found a score, return it, otherwise return "N/A"
        return cleaned_score if cleaned_score else "N/A"
    except:
        return "N/A"

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
    state = query_params.get("auth_state", [None])[0]
    
    # Verify state to prevent CSRF attacks
    if state != st.session_state.get("auth_state"):
        st.error("Invalid state parameter. Possible CSRF attack.")
        return
    
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
    st.title("Texas A&M AutoGrader")
    
    # Handle Auth0 callback if code parameter is present
    query_params = st.experimental_get_query_params()
    if "code" in query_params:
        handle_auth_callback()
    else:
        # Display login/user info in sidebar
        show_user_info()
        
        # Only show app content if user is authenticated
        if st.session_state.user:
            # Upload answer key first
            key_pdf = st.file_uploader("Upload Answer Key (Digital PDF)", type=['pdf'])
            
            # Single uploader for multiple student PDFs
            student_pdfs = st.file_uploader("Upload Student Answer Sheets", 
                                        type=['pdf'],
                                        accept_multiple_files=True)
            
            # Create a dictionary to store all student data
            students_data = {}
            
            # Process uploaded student PDFs
            for student_pdf in student_pdfs:
                student_name = get_student_name(student_pdf.name)
                students_data[student_name] = {"pdf": student_pdf}

            if "students_data" not in st.session_state:
                st.session_state.students_data = {}

            # Process student PDFs only if not already done
            if key_pdf is not None and len(students_data) > 0 and not st.session_state.students_data:
                st.write(f"Files uploaded successfully! Processing {len(students_data)} student submissions...")

                try:
                    with st.spinner("Processing answer key..."):
                        key_pdf.seek(0)
                        # Process answer key through Gemini with is_handwritten=False
                        key_text = extract_text_from_pdf(key_pdf, is_handwritten=False)
                        st.session_state.key_text = key_text

                    for student_name, data in students_data.items():
                        with st.spinner(f"Processing {student_name}'s answers..."):
                            data['pdf'].seek(0)
                            # Process student submissions with is_handwritten=True
                            student_text = extract_text_from_pdf(data['pdf'], is_handwritten=True)
                            students_data[student_name]['text'] = student_text
                            
                            comparison_prompt = f"""
                            Compare the following student answers with the answer key.
                            Provide a short analysis of matching and non-matching answers.

                            I want the output to be structured in the following way:
                            Question wise Matching Aspects and non-matching aspects and score for that question
                            and in the end there will be only 1 "Total Score : 'score'/100"
                            Student Answers:
                            {student_text}

                            Answer Key:
                            {key_text}
                            """
                            
                            comparison_response = model.generate_content(comparison_prompt, generation_config={
                                'temperature': 1.0
                            })
                            students_data[student_name]['analysis'] = comparison_response.text

                    # Store processed data in session state
                    st.session_state.students_data = students_data

                except Exception as e:
                    st.error(f"An error occurred during processing: {str(e)}")
                    st.write("Please make sure all PDF files are valid and not corrupted.")

            # Store the key_pdf in session state when first uploaded
            if key_pdf is not None and 'key_pdf' not in st.session_state:
                st.session_state.key_pdf = key_pdf

            # Display results (moved outside the processing block)
            if st.session_state.students_data:
                st.subheader("Answer Key")
                # Only show the expander if we have the key_pdf in session state
                if 'key_pdf' in st.session_state:
                    with st.expander("View Answer Key", expanded=False):
                        st.text_area("Content", st.session_state.key_text, height=200)
                        st.session_state.key_pdf.seek(0)
                        images = convert_from_bytes(st.session_state.key_pdf.read())
                        for i, image in enumerate(images):
                            st.image(image, caption=f"Page {i+1}", use_column_width=True)

                st.subheader("Student Submissions")
                
                # Display student submissions
                for student_name, data in st.session_state.students_data.items():
                    score = extract_score(data['analysis'])
                    with st.expander(f"📝 {student_name} - {score}", expanded=False):
                        tabs = st.tabs(["AI Analysis", "Transcribed Answer", "Original PDF"])
                        
                        with tabs[0]:
                            st.write("AI Analysis:")
                            st.write(data['analysis'])
                        
                        with tabs[1]:
                            st.text_area("Transcribed Content", data['text'], height=200)
                        
                        with tabs[2]:
                            if 'pdf' in data:
                                data['pdf'].seek(0)
                                images = convert_from_bytes(data['pdf'].read())
                                for i, image in enumerate(images):
                                    st.image(image, caption=f"Page {i+1}", use_column_width=True)
                                
                # Add buttons for both text and Excel downloads
                col1, col2 = st.columns(2)

                with col1:
                    results_text = "Answer Sheet Analysis Results\n\n"
                    results_text += f"Answer Key:\n{st.session_state.key_text}\n\n"
                    for student_name, data in st.session_state.students_data.items():
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

                with col2:
                    df = pd.DataFrame({
                        'Student Name': list(st.session_state.students_data.keys()),
                        'Score': [extract_score(data['analysis']) 
                                 for data in st.session_state.students_data.values()]
                    })
                
                    st.download_button(
                        label="Download Results as Excel",
                        data=df.to_csv(index=False).encode('utf-8'),
                        file_name="student_scores.csv",
                        mime="text/csv"
                    )
        else:
            st.warning("")

if __name__ == "__main__":
    main()

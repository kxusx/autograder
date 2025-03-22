import streamlit as st
from pdf2image import convert_from_bytes
import PyPDF2
import io
from PIL import Image
import numpy as np
import google.generativeai as genai
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
GEMINI_API_KEY = os.getenv('gemini-key')

# Configure Gemini
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-2.0-flash-exp-image-generation')

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

def get_student_name(filename):
    # Remove .pdf extension and return the filename as student name
    return filename.replace('.pdf', '')

def extract_score(analysis_text):
    try:
        # Find the last occurrence of "Total Score:" and extract the score
        if "Total Score:" in analysis_text:
            score = analysis_text.split("Total Score:")[-1].strip()
            return score
        if "Total score:" in analysis_text:
            score = analysis_text.split("Total Score:")[-1].strip()
            return score
        if "Total Score : " in analysis_text:
            score = analysis_text.split("Total Score:")[-1].strip()
            return score
        if "Total Score :" in analysis_text:
            score = analysis_text.split("Total Score:")[-1].strip()
            return score
        return "N/A"
    except:
        return "N/A"

def main():
    st.title("PDF Answer Sheet Comparison")
    
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

    if key_pdf is not None and len(students_data) > 0:
        st.write(f"Files uploaded successfully! Processing {len(students_data)} student submissions...")
        
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
                  
                    I want the output to be structured in the following way:
                    Question wise Matching Aspects and non-matching aspects and score for that question
                    and in the end there will be "Total Score : 'score'/100"
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
                # Extract score from analysis
                score = extract_score(data['analysis'])
                # Display name and score in the expander header
                with st.expander(f"📝 {student_name} - {score}"):
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

if __name__ == "__main__":
    main()

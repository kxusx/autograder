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

def main():
    st.title("Texas A&M AutoGrader")
    st.write("Upload a student's handwritten answer sheet and the digital answer key")

    # File uploaders
    student_pdf = st.file_uploader("Upload Student's Handwritten Answer Sheet", type=['pdf'])
    key_pdf = st.file_uploader("Upload Answer Key", type=['pdf'])

    if student_pdf is not None and key_pdf is not None:
        st.write("Files uploaded successfully!")
        
        try:
            with st.spinner("Processing handwritten answers using Gemini AI (this may take a while)..."):
                student_text = extract_text_from_handwritten_pdf(student_pdf)
            
            with st.spinner("Processing answer key..."):
                key_text = extract_text_from_digital_pdf(key_pdf)

            # Display the extracted text
            col1, col2 = st.columns(2)
            
            with col1:
                st.subheader("Student's Answers (Gemini AI Result)")
                st.text_area("Content", student_text, height=400)
                
                # Display the original image for verification
                st.subheader("Original Answer Sheet")
                try:
                    # Reset file pointer to beginning
                    student_pdf.seek(0)
                    images = convert_from_bytes(student_pdf.read())
                    for i, image in enumerate(images):
                        st.image(image, caption=f"Page {i+1}", use_column_width=True)
                except Exception as e:
                    st.error(f"Error displaying student PDF: {str(e)}")

            with col2:
                st.subheader("Answer Key")
                try:
                    # Reset file pointer to beginning
                    key_pdf.seek(0)
                    # Validate PDF before processing
                    if key_pdf.size > 0:  # Check if file is not empty
                        key_text = extract_text_from_digital_pdf(key_pdf)
                        st.text_area("Content", key_text, height=400)
                    else:
                        st.error("The answer key PDF file appears to be empty")
                        key_text = ""
                except Exception as e:
                    st.error(f"Error processing answer key PDF: {str(e)}")
                    key_text = ""

            # Add a button to compare
            if st.button("Compare Answers"):
                st.subheader("Comparison Results")
                st.info("Using Gemini AI for handwriting recognition")
                
                # Ask Gemini to compare the answers
                comparison_prompt = f"""
                Compare the following student answers with the answer key.
                Provide a short analysis of matching and non-matching answers.
                Calculate an approximate score and privde it as "Score: score/100". 

                Student Answers:
                {student_text}

                Answer Key:
                {key_text}
                """
                
                try:
                    comparison_response = model.generate_content(comparison_prompt)
                    st.write("AI Analysis:")
                    st.write(comparison_response.text)
                except Exception as e:
                    st.error(f"Error during comparison: {str(e)}")
                    
                # Also show basic similarity score
                from difflib import SequenceMatcher
                similarity = SequenceMatcher(None, student_text, key_text).ratio()
                st.write(f"Text Similarity Score: {similarity:.2%}")

        except Exception as e:
            st.error(f"An error occurred during processing: {str(e)}")
            st.write("Please make sure the PDF files are valid and not corrupted.")

if __name__ == "__main__":
    main()

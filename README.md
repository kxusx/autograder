# Texas A&M AutoGrader

## Description
Texas A&M AutoGrader is an AI-powered application designed to streamline the grading process for educators. It automatically compares handwritten student answers against a digital answer key using Google's Gemini AI model. The application provides detailed analysis, scoring, and the ability to process multiple student submissions simultaneously.

### Key Features
- Secure authentication using Auth0
- Digital answer key upload and processing
- Multiple handwritten student submission processing
- AI-powered text extraction from handwritten documents
- Detailed comparison and scoring analysis
- Export results in both text and Excel formats
- User-friendly interface with expandable sections for each submission

## Installation

### Prerequisites
- Python 3.8 or higher
- pip (Python package installer)

1. Clone the repository:
```bash
git clone https://github.com/kxusx/autograder.git
cd autograder
```

2. Create and activate a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install required packages:
```bash
pip install -r requirements.txt
```

4. Create a `.env` file in the root directory with the following variables:
```
GEMINI_API_KEY=your_gemini_api_key
AUTH0_CLIENT_ID=your_auth0_client_id
AUTH0_CLIENT_SECRET=your_auth0_client_secret
AUTH0_DOMAIN=your_auth0_domain
AUTH0_CALLBACK_URL=your_callback_url
AUTH0_LOGOUT_URL=your_logout_url
```

## Usage

1. Start the application:
```bash
streamlit run pdf_comparison_app.py
```

2. Access the application through your web browser at `http://localhost:8501`

3. Log in using Auth0 authentication

4. Upload the digital answer key PDF

5. Upload student submission PDFs (handwritten)

6. Wait for the AI to process and analyze the submissions

7. View results and download reports in either text or Excel format

## Security Features
- Secure authentication using Auth0
- State parameter verification to prevent CSRF attacks
- Secure session management
- Environment variable protection for sensitive keys

## Technical Requirements
See `requirements.txt` for a complete list of Python dependencies.

## License
[Your License Type]

## Contributors
Khush Patel @kxusx
Rahul Baid @rahulb99
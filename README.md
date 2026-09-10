# AI-Engineer-Document-Intelligence-Platform
An AI-powered Document Intelligence Platform for extracting, validating, and visualizing structured information from financial documents such as Balance Sheets, Profit & Loss Statements, Cash Flow Statements, and Invoices.

The platform combines OCR, PDF text extraction, LLM-based extraction, validation, and a dashboard into a single workflow.

🚀 Features
📄 Process PDF, JPG, JPEG, and PNG documents
🔍 Native PDF text extraction using PyMuPDF
🧠 OCR fallback using Tesseract
🤖 AI-powered information extraction using Anthropic Claude
💰 Financial document extraction and validation
📊 Dashboard for viewing processed documents and extracted information
✅ Numerical consistency and validation checks
📑 Page-level extraction with source tracking
🔎 Evidence/grounding support for extracted information
⚙️ Configurable file size and page limits
🗂️ Local document storage
🧾 SQLite database support
🏗️ Architecture
                    ┌─────────────────────┐
                    │     User Upload     │
                    │   PDF / JPG / PNG    │
                    └──────────┬──────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │   Document Parser   │
                    └──────────┬──────────┘
                               │
                ┌──────────────┴──────────────┐
                │                             │
                ▼                             ▼
        ┌───────────────┐             ┌───────────────┐
        │ Native PDF    │             │     OCR       │
        │ Text Extract  │             │  Tesseract    │
        │   PyMuPDF     │             │               │
        └───────┬───────┘             └───────┬───────┘
                │                             │
                └──────────────┬──────────────┘
                               ▼
                    ┌─────────────────────┐
                    │   Extracted Text    │
                    │   Page-level data   │
                    └──────────┬──────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │    LLM Extraction   │
                    │   Claude / Anthropic │
                    └──────────┬──────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │ Validation Engine   │
                    │                     │
                    │ • Financial checks  │
                    │ • Numeric tolerance │
                    │ • Evidence mapping  │
                    └──────────┬──────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │      Dashboard      │
                    │                     │
                    │ Extracted Results   │
                    │ Validation Results  │
                    │ Document History    │
                    └─────────────────────┘
🔄 Document Processing Flow
User uploads a document.
The system identifies the document type.
For PDFs, the system first attempts native text extraction.
If insufficient text is found, the page is rasterized and sent to Tesseract OCR.
Images are processed directly using OCR.
Extracted text is associated with its page number and extraction source.
The LLM converts the unstructured text into structured information.
The validation layer checks extracted financial values.
Results and evidence are presented through the dashboard.
🧠 OCR Strategy

The platform uses a hybrid extraction strategy.

PDF Documents
PDF
 │
 ├── Native text available?
 │        │
 │        ├── YES → PyMuPDF extraction
 │        │
 │        └── NO / insufficient text
 │                    ↓
 │                 Tesseract OCR
 │
 ▼
Page-level extracted text

A PDF page is considered to have usable native text when it contains at least 20 non-whitespace characters.

This allows the system to avoid unnecessary OCR when a PDF already contains a reliable text layer.

Images

For:

JPG
JPEG
PNG

the system directly uses Tesseract OCR.

🛠️ Tech Stack
Backend
Python
FastAPI
PyMuPDF
Pytesseract
Pillow
SQLite
AI / LLM
Anthropic Claude
Structured information extraction
Evidence-based document processing
OCR
Tesseract OCR
Frontend / Dashboard
Web-based dashboard
Document processing interface
Extracted data visualization
📁 Project Structure
AI-Engineer-Document-Intelligence-Platform/
│
├── app/
│   ├── ...
│   ├── config.py
│   ├── logging_config.py
│   └── ...
│
├── storage/
│   └── uploads/
│
├── tests/
│   └── ...
│
├── .env.example
├── .gitignore
├── requirements.txt
├── README.md
└── ...

The exact structure may vary depending on the current implementation.

⚙️ Installation
1. Clone the repository
git clone https://github.com/Anshul271/AI-Engineer-Document-Intelligence-Platform.git
cd AI-Engineer-Document-Intelligence-Platform
2. Create a virtual environment

Windows:

python -m venv .venv

Activate it:

.venv\Scripts\activate

Linux/macOS:

python3 -m venv .venv
source .venv/bin/activate
3. Install dependencies
pip install -r requirements.txt
🔐 Environment Configuration

Create a .env file from .env.example:

copy .env.example .env

Then configure your environment variables:

ENV=development

DATABASE_URL=sqlite:///./docintel.db

MAX_PAGES=3
MAX_FILE_SIZE_MB=15

ANTHROPIC_API_KEY=your_anthropic_api_key_here
ANTHROPIC_MODEL=claude-sonnet-4-6

TESSERACT_CMD=C:\Program Files\Tesseract-OCR\tesseract.exe
OCR_DPI=200

UPLOAD_DIR=./storage/uploads

NUMERIC_TOLERANCE=0.01
⚠️ Security

Never commit .env or real API keys to GitHub.

The repository uses:

.env
.env.*
!.env.example

The .env.example file should contain placeholders only, never real credentials.

🔍 Tesseract Setup

Install Tesseract OCR on your system.

If Tesseract is not available in your system PATH, specify its executable location using:

TESSERACT_CMD=C:\Program Files\Tesseract-OCR\tesseract.exe

The application uses the configured path when available.

▶️ Running the Application

After installing dependencies and configuring .env, start the application using the project's configured entry point.

For a typical FastAPI application:

uvicorn app.main:app --reload

The application will normally be available at:

http://127.0.0.1:8000
📄 Supported Documents
Document Type	Supported
Invoice	✅
Balance Sheet	✅
Profit & Loss	✅
Cash Flow Statement	✅
PDF	✅
JPG / JPEG	✅
PNG	✅
📊 Financial Validation

The validation layer helps identify inconsistencies in extracted financial data.

For example:

Assets = Liabilities + Equity

The system can compare extracted values and determine whether they fall within the configured numerical tolerance.

The default tolerance is:

NUMERIC_TOLERANCE=0.01

which represents 1%.

🧾 Page-Level Evidence

Each extracted page is represented using a structure similar to:

PageText(
    page_number=1,
    text="...",
    source="native"
)

The source identifies whether the text came from:

native → PDF text layer
ocr    → Tesseract OCR

This makes it possible for downstream extraction and validation components to associate information with its original document page.

🧪 Example Workflow
Upload Balance Sheet
        ↓
Extract PDF text
        ↓
Check text quality
        ↓
OCR if required
        ↓
Send extracted text to LLM
        ↓
Generate structured financial data
        ↓
Validate extracted values
        ↓
Display results
🎯 Use Cases

This platform can be used for:

Financial document analysis
Automated invoice processing
Accounting document extraction
Financial data digitization
Document verification
Automated reporting
AI-powered document workflows
Building RAG/agentic document-processing systems
🔮 Future Improvements

Multi-document batch processing

Advanced table extraction

Human-in-the-loop verification

Confidence scoring

Vector database integration

Agentic document reasoning

Advanced RAG pipeline

Cloud storage integration

Authentication and user management

Export results to Excel/CSV

Improved OCR preprocessing

Production deployment with Docker

👨‍💻 Author

Anshul

AI Engineer — Document Intelligence Platform

📜 License

This project is intended for educational and development purposes.

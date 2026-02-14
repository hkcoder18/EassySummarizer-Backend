# Universal Summarizer Backend

FastAPI backend for processing YouTube videos, PDFs, and Web links into summaries using Google Gemini AI.

## Setup

1. Create a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # or venv\Scripts\activate on Windows
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Configure environment variables:
   Create a `.env` file in the `backend` directory:
   ```env
   GOOGLE_API_KEY=your_gemini_api_key
   GEMINI_MODEL=gemini-flash-latest
   ```

4. Run the server:
   ```bash
   python main.py
   ```

## Detailed Working

The backend acts as a multi-stage pipeline that transforms unstructured media into structured insights.

### 1. Data Extraction Layer
- **YouTube Processing**: 
  - Extracts Video IDs using regex patterns.
  - Fetches video metadata (Title, Author, Thumbnail) via `yt-dlp`.
  - Retrieves full transcripts using `youtube-transcript-api` with language fallback logic (tries English first, then falls back to any available language).
- **Web Scraping**:
  - Fetches HTML content with optimized headers to bypass bot detection.
  - Uses `BeautifulSoup4` to surgically remove scripts, styles, and navigational elements, leaving only the core article text.
- **PDF Analysis**:
  - Uses `PyMuPDF` (fitz) to scrape text from uploaded document files.

### 2. AI Summarization Engine
- **Model Orchestration**: Powered by the `google-genai` SDK. It uses a configurable model (defaults to `gemini-flash-latest` for high speed and generous free-tier quotas).
- **Prompt Engineering**: The content is sent with a specific system-style prompt that instructs the AI to return four distinct segments:
  1. **TL;DR**: An executive summary.
  2. **Key Pillars**: The main arguments or components.
  3. **Action Items**: Key takeaways or next steps.
  4. **Glossary**: Definitions of complex terms.

### 3. Concurrency Model
- The API is built with **FastAPI**. While the endpoints are defined as standard `def` (synchronous) functions, FastAPI automatically runs them in an external thread pool. This is critical because AI generation is a blocking operation; this approach prevents the server from hanging and allows it to handle multiple users simultaneously.

## Endpoints

- `POST /summarize`: Summarize YouTube or Web links.
  - Body: `{"url": "...", "content_type": "youtube" | "web"}`
- `POST /summarize/file`: Upload and summarize a PDF.
  - Form-data: `file: [PDF File]`

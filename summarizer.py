import os
import re
from typing import Optional
from youtube_transcript_api import YouTubeTranscriptApi
from google import genai
from dotenv import load_dotenv

load_dotenv()

# Configure Gemini
client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))

def extract_video_id(url: str) -> Optional[str]:
    """Extract the video ID from a YouTube URL."""
    patterns = [
        r'(?:v=|\/)([0-9A-Za-z_-]{11}).*',
        r'(?:be\/)([0-9A-Za-z_-]{11}).*',
        r'(?:embed\/)([0-9A-Za-z_-]{11}).*',
        r'(?:shorts\/)([0-9A-Za-z_-]{11}).*'
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None

def get_transcript(video_id: str) -> str:
    """Fetch the transcript for a YouTube video with language fallbacks."""
    try:
        print(f"DEBUG: Fetching transcript for {video_id}...")
        api = YouTubeTranscriptApi()
        transcript_list = api.list(video_id)
        
        try:
            transcript_obj = transcript_list.find_transcript(['en'])
        except Exception:
            print("DEBUG: English transcript not found, taking first available.")
            transcript_obj = next(iter(transcript_list))
            
        transcript_data = transcript_obj.fetch()
        print(f"DEBUG: Found {len(transcript_data)} transcript segments.")
        transcript_text = " ".join([item.text for item in transcript_data])
        print(f"DEBUG: Transcript length: {len(transcript_text)} characters.")
        return transcript_text
    except Exception as e:
        print(f"DEBUG: Error in get_transcript: {str(e)}")
        return f"Error fetching transcript: {str(e)}"

import yt_dlp

def extract_metadata(url: str) -> dict:
    """Extract metadata for a YouTube video using yt-dlp."""
    ydl_opts = {
        'skip_download': True,
        'quiet': True,
        'no_warnings': True,
    }
    try:
        print(f"DEBUG: Extracting metadata for {url}...")
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            return {
                "title": info.get('title'),
                "author": info.get('uploader'),
                "thumbnail": info.get('thumbnail'),
                "duration": info.get('duration'),
                "view_count": info.get('view_count'),
                "published_at": info.get('upload_date')
            }
    except Exception as e:
        print(f"DEBUG: Error in extract_metadata: {str(e)}")
        return {"error": str(e)}

import fitz  # PyMuPDF

def extract_pdf_text(file_path: str) -> str:
    """Extract text from a PDF file."""
    text = ""
    try:
        doc = fitz.open(file_path)
        for page in doc:
            text += page.get_text()
        doc.close()
        return text
    except Exception as e:
        return f"Error extracting PDF: {str(e)}"

import requests
from bs4 import BeautifulSoup

def extract_web_text(url: str) -> dict:
    """Extract text and metadata from a web page."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9"
    }
    try:
        print(f"DEBUG: Extracting web text from {url}...")
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        for script in soup(["script", "style"]):
            script.extract()
            
        text = soup.get_text()
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        text = '\n'.join(chunk for chunk in chunks if chunk)
        
        title = soup.title.string if soup.title else url
        return {"text": text, "title": title}
    except Exception as e:
        print(f"DEBUG: Error in extract_web_text: {str(e)}")
        return {"error": str(e)}

def chat_with_content(context: str, question: str, history: list = None) -> str:
    """Answer a question based on the provided context using Gemini."""
    model_name = os.getenv("GEMINI_MODEL", "gemini-flash-latest")
    
    # Format history if provided
    history_str = ""
    if history:
        for msg in history:
            role = "User" if msg["role"] == "user" else "Assistant"
            history_str += f"{role}: {msg['content']}\n"

    prompt = f"""
    Act as an expert assistant. Answer the user's question based ONLY on the provided context. 
    If the answer is not in the context, say "I'm sorry, but that information is not available in the provided content."
    
    Context:
    {context}
    
    Chat History:
    {history_str}
    
    Question: {question}
    
    Answer:
    """
    
    try:
        print(f"DEBUG: Starting Gemini chat with model {model_name}...")
        response = client.models.generate_content(
            model=model_name,
            contents=prompt
        )
        print("DEBUG: Gemini chat response received successfully.")
        return response.text
    except Exception as e:
        print(f"DEBUG: Error in chat_with_content: {str(e)}")
        return f"Error with AI generation: {str(e)}"

def summarize_content(text: str, metadata: Optional[dict] = None) -> str:
    """Summarize the provided text using Gemini."""
    
    title_str = f"Title: {metadata.get('title')}\n" if metadata and metadata.get('title') else ""
    
    prompt = f"""
    Act as an expert researcher. Analyze the provided content and return the response in English.
    {title_str}
    1. A TL;DR (Executive Summary).
    2. Key Pillars (The main arguments/components).
    3. Action Items/Takeaways.
    4. Glossary (Define any complex terms used).

    Content to summarize:
    {text}
    """
    
    try:
        model_name = os.getenv("GEMINI_MODEL", "gemini-flash-latest")
        print(f"DEBUG: Starting Gemini summarization with model {model_name}...")
        response = client.models.generate_content(
            model=model_name,
            contents=prompt
        )
        print("DEBUG: Gemini response received successfully.")
        return response.text
    except Exception as e:
        print(f"DEBUG: Error in summarize_content: {str(e)}")
        return f"Error with AI generation: {str(e)}"

if __name__ == "__main__":
    test_url = input("Enter YouTube URL: ")
    v_id = extract_video_id(test_url)
    if v_id:
        print(f"Extracting metadata for video ID: {v_id}...")
        metadata = extract_metadata(test_url)
        print(f"Title: {metadata.get('title')}")
        
        print(f"Extracting transcript...")
        transcript = get_transcript(v_id)
        if not transcript.startswith("Error"):
            print("Summarizing...")
            summary = summarize_content(transcript, metadata)
            print("\n--- SUMMARY ---\n")
            print(summary)
        else:
            print(transcript)
    else:
        print("Invalid YouTube URL.")

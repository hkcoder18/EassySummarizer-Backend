import os
from dotenv import load_dotenv
import fastapi

load_dotenv()
from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Depends
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from summarizer import extract_video_id, get_transcript, summarize_content, chat_with_content
from pydantic import BaseModel, EmailStr
from typing import Optional, List
from sqlalchemy.orm import Session
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
import models
from database import engine, get_db
from auth_utils import get_password_hash, verify_password, create_access_token, decode_access_token

# Create database tables
models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="Universal Summarizer API")

# Configure CORS
allowed_origins = os.getenv("FRONTEND_URL", "http://localhost:3000").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins if allowed_origins != ["*"] else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class SummarizeRequest(BaseModel):
    url: Optional[str] = None
    content_type: str  # "youtube", "web", "pdf"

class ChatRequest(BaseModel):
    context: str
    question: str
    history: Optional[list] = []

class UserCreate(BaseModel):
    email: EmailStr
    password: str

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

def get_current_user(token: str = fastapi.Depends(oauth2_scheme), db: Session = fastapi.Depends(get_db)):
    payload = decode_access_token(token)
    if payload is None:
        raise HTTPException(status_code=401, detail="Invalid authentication credentials")
    email: str = payload.get("sub")
    if email is None:
        raise HTTPException(status_code=401, detail="Invalid authentication credentials")
    user = db.query(models.User).filter(models.User.email == email).first()
    if user is None:
        raise HTTPException(status_code=401, detail="User not found")
    return user

@app.post("/signup")
def signup(user_data: UserCreate, db: Session = Depends(get_db)):
    db_user = db.query(models.User).filter(models.User.email == user_data.email).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    hashed_pwd = get_password_hash(user_data.password)
    new_user = models.User(email=user_data.email, hashed_password=hashed_pwd)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    access_token = create_access_token(data={"sub": new_user.email})
    return {"access_token": access_token, "token_type": "bearer", "user": {"email": new_user.email}}

@app.post("/login")
def login(user_data: UserLogin, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == user_data.email).first()
    if not user or not verify_password(user_data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Incorrect email or password")
    
    access_token = create_access_token(data={"sub": user.email})
    return {"access_token": access_token, "token_type": "bearer", "user": {"email": user.email}}

@app.get("/me")
def get_me(current_user: models.User = Depends(get_current_user)):
    return {"email": current_user.email, "id": current_user.id}

@app.get("/")
async def root():
    return {"message": "Universal Summarizer API is running"}

@app.post("/summarize")
def summarize(request: SummarizeRequest, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    if request.content_type == "youtube":
        if not request.url:
            raise HTTPException(status_code=400, detail="URL is required for YouTube summary")
        
        video_id = extract_video_id(request.url)
        if not video_id:
            raise HTTPException(status_code=400, detail="Invalid YouTube URL")
        
        from summarizer import extract_metadata
        metadata = extract_metadata(request.url)
        
        transcript = get_transcript(video_id)
        if transcript.startswith("Error"):
            raise HTTPException(status_code=500, detail=transcript)
        
        summary = summarize_content(transcript, metadata)
        
        # Save to history
        db_history = models.SummaryHistory(
            title=metadata.get("title", request.url),
            url=request.url,
            summary=summary,
            content=transcript,
            video_id=video_id,
            content_type="youtube",
            user_id=current_user.id
        )
        db.add(db_history)
        db.commit()

        return {
            "summary": summary, 
            "content": transcript,
            "type": "youtube", 
            "video_id": video_id,
            "metadata": metadata
        }
    
    elif request.content_type == "web":
        if not request.url:
            raise HTTPException(status_code=400, detail="URL is required for web summary")
        
        from summarizer import extract_web_text
        result = extract_web_text(request.url)
        
        if "error" in result:
            raise HTTPException(status_code=500, detail=result["error"])
        
        metadata = {"title": result["title"]}
        summary = summarize_content(result["text"], metadata)
        
        # Save to history
        db_history = models.SummaryHistory(
            title=result["title"],
            url=request.url,
            summary=summary,
            content=result["text"],
            content_type="web",
            user_id=current_user.id
        )
        db.add(db_history)
        db.commit()

        return {
            "summary": summary, 
            "content": result["text"],
            "type": "web", 
            "title": result["title"],
            "url": request.url
        }
    
    return {"message": f"{request.content_type} summarization is coming soon!"}

@app.post("/chat")
def chat(request: ChatRequest, current_user: models.User = Depends(get_current_user)):
    print(f"DEBUG: Handling chat request. Question: {request.question[:50]}...")
    answer = chat_with_content(request.context, request.question, request.history)
    return {"answer": answer}

@app.post("/summarize/file")
def summarize_file(file: UploadFile = File(...), current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported currently")
    
    # Save the file temporarily
    temp_path = f"temp_{file.filename}"
    with open(temp_path, "wb") as buffer:
        buffer.write(file.file.read())
    
    from summarizer import extract_pdf_text
    text = extract_pdf_text(temp_path)
    
    # Remove temp file
    import os
    if os.path.exists(temp_path):
        os.remove(temp_path)
        
    if text.startswith("Error"):
        raise HTTPException(status_code=500, detail=text)
    
    metadata = {"title": file.filename}
    summary = summarize_content(text, metadata)
    
    # Save to history
    db_history = models.SummaryHistory(
        title=file.filename,
        url=None,
        summary=summary,
        content=text,
        content_type="pdf",
        user_id=current_user.id
    )
    db.add(db_history)
    db.commit()

    return {
        "summary": summary, 
        "content": text,
        "type": "pdf", 
        "filename": file.filename
    }

@app.get("/history")
def get_history(current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    history = db.query(models.SummaryHistory).filter(models.SummaryHistory.user_id == current_user.id).order_by(models.SummaryHistory.created_at.desc()).all()
    return history

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)

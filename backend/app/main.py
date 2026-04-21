from fastapi import FastAPI, Depends, HTTPException, status, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
import os
import shutil

from app.database import engine, Base, get_db
from app import models, schemas, auth, knowledge_base

UPLOAD_DIR = os.getenv("UPLOAD_DIR", "/app/uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

app = FastAPI(
    title="Falcon University Admission Bot API",
    description="Backend for the Falcon University admission pre-assessment tool.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    Base.metadata.create_all(bind=engine)


@app.get("/health", tags=["Health"])
def health_check():
    """Health check endpoint for Docker/Podman orchestrators."""
    return {"status": "ok", "service": "falcon-university-api"}


@app.get("/", tags=["Root"])
def root():
    return {"message": "Falcon University Admission Bot API is running."}


# -----------------------
# Auth endpoints
# -----------------------

@app.post("/auth/register", response_model=schemas.UserOut, tags=["Auth"])
def register(payload: schemas.UserCreate, db: Session = Depends(get_db)):
    """Register a new admin user."""
    existing = db.query(models.User).filter(models.User.username == payload.username).first()
    if existing:
        raise HTTPException(status_code=400, detail="Username already taken")
    user = models.User(
        username=payload.username,
        hashed_password=auth.get_password_hash(payload.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@app.post("/auth/login", response_model=schemas.Token, tags=["Auth"])
def login(payload: schemas.UserCreate, db: Session = Depends(get_db)):
    """Log in and receive a JWT access token."""
    user = db.query(models.User).filter(models.User.username == payload.username).first()
    if not user or not auth.verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Invalid username or password")
    access_token = auth.create_access_token(data={"sub": user.username})
    return {"access_token": access_token, "token_type": "bearer"}


@app.get("/auth/me", response_model=schemas.UserOut, tags=["Auth"])
def me(current_user: models.User = Depends(auth.get_current_user)):
    """Get current authenticated user."""
    return current_user


# -----------------------
# Document / Knowledge Base endpoints
# -----------------------

@app.post("/documents/upload", response_model=schemas.DocumentOut, tags=["Documents"])
def upload_document(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    """Upload a PDF and ingest it into the knowledge base."""
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted")

    # Save file to disk
    file_path = os.path.join(UPLOAD_DIR, file.filename)
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # Extract text using pdfplumber
    try:
        import pdfplumber
        text_parts = []
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(page_text)
        extracted_text = "\n".join(text_parts)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to extract PDF text: {e}")

    # Persist to DB
    doc = models.Document(filename=file.filename, content=extracted_text)
    db.add(doc)
    db.commit()
    db.refresh(doc)

    # Ingest into Chroma
    knowledge_base.ingest_document(doc.id, extracted_text)

    return doc


@app.get("/documents", response_model=list[schemas.DocumentList], tags=["Documents"])
def list_documents(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    """List all uploaded documents."""
    return db.query(models.Document).all()


@app.get("/documents/{doc_id}", response_model=schemas.DocumentOut, tags=["Documents"])
def get_document(
    doc_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    """Get a single document by ID."""
    doc = db.query(models.Document).filter(models.Document.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc


@app.delete("/documents/{doc_id}", tags=["Documents"])
def delete_document(
    doc_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    """Delete a document and remove it from the knowledge base."""
    doc = db.query(models.Document).filter(models.Document.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    # Remove from Chroma
    knowledge_base.delete_document(doc_id)

    # Remove file from disk
    file_path = os.path.join(UPLOAD_DIR, doc.filename)
    if os.path.exists(file_path):
        os.remove(file_path)

    db.delete(doc)
    db.commit()
    return {"detail": "Document deleted"}

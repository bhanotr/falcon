from fastapi import FastAPI, Depends, HTTPException, status, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import inspect, text
import os
import shutil
import json
import re

from openai import OpenAI

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
    # Inline migration: add new columns to existing tables if missing
    inspector = inspect(engine)
    applicant_cols = [c["name"] for c in inspector.get_columns("applicants")]
    with engine.begin() as conn:
        if "details" not in applicant_cols:
            conn.execute(text("ALTER TABLE applicants ADD COLUMN details JSONB DEFAULT '{}'"))
        if "is_complete" not in applicant_cols:
            conn.execute(text("ALTER TABLE applicants ADD COLUMN is_complete BOOLEAN DEFAULT FALSE"))


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


# -----------------------
# Chat endpoint
# -----------------------

_llm_client = None


def get_llm_client():
    global _llm_client
    if _llm_client is None:
        _llm_client = OpenAI(
            api_key=os.getenv("OPENAI_API_KEY", ""),
            base_url="http://localhost:11434/v1",
        )
    return _llm_client


@app.post("/chat", response_model=schemas.ChatResponse, tags=["Chat"])
def chat(payload: schemas.ChatRequest):
    """Handle a student chat message. Queries the knowledge base and returns an LLM response."""
    # 1. Retrieve relevant context from knowledge base
    try:
        docs = knowledge_base.query_kb(payload.message, k=4)
        context = "\n\n".join([d.page_content for d in docs]) if docs else ""
    except Exception:
        context = ""

    # 2. Build system prompt
    system_prompt = (
        "You are the Falcon University admission assistant. "
        "Help prospective students with questions about admission requirements, programs, deadlines, and eligibility. "
        "Be concise, friendly, and factual."
    )
    if context:
        system_prompt += (
            "\n\nUse the following retrieved university documents to answer the student's question:\n"
            + context
        )

    # 3. Call LLM gateway
    try:
        client = get_llm_client()
        response = client.chat.completions.create(
            model="gpt-5.4-nano",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": payload.message},
            ],
            temperature=0.7,
            max_tokens=512,
        )
        answer = response.choices[0].message.content or "..."
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"LLM inference failed: {e}")

    return {"response": answer}


# -----------------------
# Interview endpoints
# -----------------------

INTERVIEW_GREETING = (
    "Hello! Welcome to Falcon University Admission Pre-Assessment. "
    "My name is FalconBot, and I'll be guiding you through a quick interview to evaluate your eligibility. "
    "Let's get started — what is your full name?"
)


def _build_interview_system_prompt(applicant: models.Applicant, context: str) -> str:
    details = json.dumps(applicant.details or {}, indent=2)
    return (
        "You are the Falcon University admission assistant conducting a structured pre-assessment interview.\n\n"
        f"Current applicant info:\n"
        f"- Name: {applicant.name}\n"
        f"- Program: {applicant.program}\n"
        f"- Known details: {details}\n\n"
        "Interview rules:\n"
        "1. Ask ONE question at a time. Be friendly and concise.\n"
        '2. If the name is "Anonymous", ask for the student\'s full name first.\n'
        '3. If the program is "Unknown", ask which program they are interested in (Business or Computer Science).\n'
        "4. Once the program is known, use the retrieved program requirements below to ask for each missing requirement ONE BY ONE.\n"
        "5. Do NOT list all requirements at once. Ask about them individually.\n"
        '6. If the student says they do not have something or do not know, note it and move on.\n'
        "7. Only give your final verdict when you have enough information to determine eligibility.\n"
        "8. End your final message with exactly [INTERVIEW_COMPLETE].\n\n"
        "Program requirements from university documents:\n"
        f"{context}"
    )


def _extract_json(text: str) -> dict:
    """Extract JSON object from text, handling markdown code blocks."""
    # Try ```json ... ``` or ``` ... ```
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if match:
        return json.loads(match.group(1))
    # Try raw JSON object
    match = re.search(r"(\{.*\})", text, re.DOTALL)
    if match:
        return json.loads(match.group(1))
    raise ValueError("No JSON found in LLM response")


def _evaluate_applicant(applicant_id: int, db: Session) -> dict:
    """Run evaluation via LLM and update DB. Returns evaluation dict."""
    applicant = db.query(models.Applicant).filter(models.Applicant.id == applicant_id).first()
    if not applicant:
        raise HTTPException(status_code=404, detail="Applicant not found")

    messages = (
        db.query(models.ChatMessage)
        .filter(models.ChatMessage.applicant_id == applicant_id)
        .order_by(models.ChatMessage.created_at)
        .all()
    )
    transcript = "\n".join([f"{m.role}: {m.content}" for m in messages])

    # Query KB for program requirements
    docs = knowledge_base.query_kb(f"{applicant.program} admission requirements eligibility", k=4)
    context = "\n\n".join([d.page_content for d in docs]) if docs else ""

    eval_prompt = (
        "You are the Falcon University admission evaluation officer.\n"
        "Review the following interview transcript and program requirements.\n"
        "Extract all applicant details and determine eligibility.\n\n"
        "Respond ONLY with valid JSON in this exact format:\n"
        '{\n'
        '  "name": "...",\n'
        '  "program": "...",\n'
        '  "details": { "age": null, "gpa": null, "sat_score": null, "act_score": null, "english_test": null, "has_recommendation": null, "has_personal_statement": null, "high_school_completed": null, "math_courses": null },\n'
        '  "eligible": true,\n'
        '  "reasoning": "...",\n'
        '  "next_steps": "..."\n'
        "}\n\n"
        f"Program Requirements:\n{context}\n\n"
        f"Interview Transcript:\n{transcript}"
    )

    client = get_llm_client()
    response = client.chat.completions.create(
        model="gpt-5.4-nano",
        messages=[{"role": "system", "content": eval_prompt}],
        temperature=0.2,
        max_tokens=1024,
    )

    content = response.choices[0].message.content or "{}"
    try:
        result = _extract_json(content)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to parse evaluation JSON: {e}")

    # Update applicant record
    applicant.name = result.get("name", applicant.name)
    applicant.program = result.get("program", applicant.program)
    applicant.details = result.get("details", {})
    applicant.is_complete = True
    db.commit()

    # Create assessment record
    assessment = models.Assessment(
        applicant_id=applicant.id,
        outcome="eligible" if result.get("eligible") else "not eligible",
        rule_summary=result.get("reasoning", ""),
        transcript=transcript,
    )
    db.add(assessment)
    db.commit()

    return result


@app.post("/interview/start", response_model=schemas.InterviewStartResponse, tags=["Interview"])
def interview_start(db: Session = Depends(get_db)):
    """Start a new admission interview. Creates an applicant and returns the opening greeting."""
    applicant = models.Applicant(name="Anonymous", program="Unknown")
    db.add(applicant)
    db.commit()
    db.refresh(applicant)

    # Persist greeting as first bot message
    greeting_msg = models.ChatMessage(
        applicant_id=applicant.id,
        role="bot",
        content=INTERVIEW_GREETING,
    )
    db.add(greeting_msg)
    db.commit()

    return {"applicant_id": applicant.id, "greeting": INTERVIEW_GREETING}


@app.get("/interview/{applicant_id}/status", response_model=schemas.InterviewStatus, tags=["Interview"])
def interview_status(applicant_id: int, db: Session = Depends(get_db)):
    """Get the current status of an interview (name, program, completion)."""
    applicant = db.query(models.Applicant).filter(models.Applicant.id == applicant_id).first()
    if not applicant:
        raise HTTPException(status_code=404, detail="Applicant not found")
    return applicant


@app.get("/interview/{applicant_id}/messages", response_model=list[schemas.ChatMessageOut], tags=["Interview"])
def interview_messages(applicant_id: int, db: Session = Depends(get_db)):
    """Get all chat messages for an interview, ordered by time."""
    applicant = db.query(models.Applicant).filter(models.Applicant.id == applicant_id).first()
    if not applicant:
        raise HTTPException(status_code=404, detail="Applicant not found")
    messages = (
        db.query(models.ChatMessage)
        .filter(models.ChatMessage.applicant_id == applicant_id)
        .order_by(models.ChatMessage.created_at)
        .all()
    )
    return messages


@app.post("/interview/{applicant_id}/chat", response_model=schemas.InterviewChatResponse, tags=["Interview"])
def interview_chat(applicant_id: int, payload: schemas.InterviewChatRequest, db: Session = Depends(get_db)):
    """Handle one turn of the guided interview. Loads history, queries KB, calls LLM, checks for completion."""
    applicant = db.query(models.Applicant).filter(models.Applicant.id == applicant_id).first()
    if not applicant:
        raise HTTPException(status_code=404, detail="Applicant not found")
    if applicant.is_complete:
        return {"response": "This interview has already been completed. Thank you!", "interview_complete": True}

    # Persist user message
    user_msg = models.ChatMessage(
        applicant_id=applicant.id,
        role="user",
        content=payload.message,
    )
    db.add(user_msg)
    db.commit()

    # Load full transcript
    messages = (
        db.query(models.ChatMessage)
        .filter(models.ChatMessage.applicant_id == applicant_id)
        .order_by(models.ChatMessage.created_at)
        .all()
    )

    # Build LLM message list
    llm_messages = []

    # Query KB if program is known
    context = ""
    if applicant.program and applicant.program != "Unknown":
        try:
            docs = knowledge_base.query_kb(f"{applicant.program} admission requirements eligibility", k=4)
            context = "\n\n".join([d.page_content for d in docs]) if docs else ""
        except Exception:
            context = ""

    system_prompt = _build_interview_system_prompt(applicant, context)
    llm_messages.append({"role": "system", "content": system_prompt})

    for m in messages:
        llm_messages.append({"role": "user" if m.role == "user" else "assistant", "content": m.content})

    # Call LLM
    try:
        client = get_llm_client()
        response = client.chat.completions.create(
            model="gpt-5.4-nano",
            messages=llm_messages,
            temperature=0.7,
            max_tokens=512,
        )
        answer = response.choices[0].message.content or "..."
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"LLM inference failed: {e}")

    # Check for interview completion
    interview_complete = "[INTERVIEW_COMPLETE]" in answer
    if interview_complete:
        answer = answer.replace("[INTERVIEW_COMPLETE]", "").strip()

    # Persist bot response
    bot_msg = models.ChatMessage(
        applicant_id=applicant.id,
        role="bot",
        content=answer,
    )
    db.add(bot_msg)
    db.commit()

    if interview_complete:
        try:
            result = _evaluate_applicant(applicant.id, db)
            verdict = result.get("reasoning", "Evaluation complete.")
            next_steps = result.get("next_steps", "")
            if next_steps:
                verdict += f"\n\nNext steps: {next_steps}"
            answer = verdict
        except Exception as e:
            answer = f"Interview complete, but evaluation failed: {e}"

    return {"response": answer, "interview_complete": interview_complete}

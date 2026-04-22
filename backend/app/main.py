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
    user_cols = [c["name"] for c in inspector.get_columns("users")]
    document_cols = [c["name"] for c in inspector.get_columns("documents")]
    with engine.begin() as conn:
        if "details" not in applicant_cols:
            conn.execute(text("ALTER TABLE applicants ADD COLUMN details JSONB DEFAULT '{}'"))
        if "is_complete" not in applicant_cols:
            conn.execute(text("ALTER TABLE applicants ADD COLUMN is_complete BOOLEAN DEFAULT FALSE"))
        if "is_admin" not in user_cols:
            conn.execute(text("ALTER TABLE users ADD COLUMN is_admin BOOLEAN DEFAULT FALSE"))
        if "is_active" not in document_cols:
            conn.execute(text("ALTER TABLE documents ADD COLUMN is_active BOOLEAN DEFAULT TRUE"))

    # Seed admin user if env vars are set
    admin_username = os.getenv("ADMIN_USERNAME")
    admin_password = os.getenv("ADMIN_PASSWORD")
    if admin_username and admin_password:
        db = next(get_db())
        try:
            existing = db.query(models.User).filter(models.User.username == admin_username).first()
            if not existing:
                user = models.User(
                    username=admin_username,
                    hashed_password=auth.get_password_hash(admin_password),
                    is_admin=True,
                )
                db.add(user)
                db.commit()
            elif not existing.is_admin:
                existing.is_admin = True
                db.commit()
        finally:
            db.close()


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
            base_url=os.getenv("LLM_GATEWAY_URL", "http://localhost:11434/v1"),
        )
    return _llm_client


def _get_active_doc_ids(db: Session) -> set:
    return {d.id for d in db.query(models.Document).filter(models.Document.is_active == True).all()}


@app.post("/chat", response_model=schemas.ChatResponse, tags=["Chat"])
def chat(payload: schemas.ChatRequest, db: Session = Depends(get_db)):
    """Handle a student chat message. Queries the knowledge base and returns an LLM response."""
    # 1. Retrieve relevant context from knowledge base (active docs only)
    try:
        active_ids = _get_active_doc_ids(db)
        docs = knowledge_base.query_kb(payload.message, k=4, active_doc_ids=active_ids)
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

    # Build full transcript (bot + user) for context window
    transcript_lines = []
    for m in messages:
        transcript_lines.append(f"{m.role}: {m.content}")
    full_transcript = "\n".join(transcript_lines)

    # Soft cap: keep last ~30 turns to stay within context window (~8k chars).
    # A guided interview rarely exceeds 30 turns, so this is a safety guard.
    if len(full_transcript) > 12000:
        full_transcript = "... [truncated] ...\n" + full_transcript[-12000:]

    # Query KB for program requirements (active docs only)
    active_ids = _get_active_doc_ids(db)
    docs = knowledge_base.query_kb(f"{applicant.program} admission requirements eligibility", k=6, active_doc_ids=active_ids)
    context = "\n\n".join([d.page_content for d in docs]) if docs else ""

    eval_prompt = (
        "You are the Falcon University admission evaluation officer. "
        "Your job is to review the applicant's stated information against the OFFICIAL program requirements provided below, "
        "and return a definitive JSON verdict.\n\n"
        "CRITICAL INSTRUCTIONS:\n"
        "1. The official program requirements ARE provided below under 'Program Requirements'. Use ONLY those requirements.\n"
        "2. The FULL interview transcript is provided under 'Interview Transcript' — read it carefully. It contains both the bot's questions AND the applicant's answers.\n"
        "3. You must ONLY mark an item as 'missing' if the bot EXPLICITLY asked the applicant for it and the applicant failed to provide it.\n"
        "4. If a requirement was never asked about during the interview, do NOT list it in 'missing_items' and do NOT assume the applicant lacks it.\n"
        "5. Do NOT hallucinate values for fields that were never discussed. Leave them absent or null in 'details'.\n"
        "6. Do NOT say you lack information or cannot confirm. Work with what was provided in the transcript.\n"
        "7. Compare each requirement against the applicant's responses and decide definitively.\n"
        "8. If the applicant meets all stated requirements → status = 'eligible'.\n"
        "9. If the applicant fails one or more hard requirements → status = 'not_eligible'.\n"
        "10. If the applicant is missing required documents or information (that were explicitly asked for) → status = 'needs_more_info'.\n"
        "11. Your reasoning must be brief (1-2 sentences max).\n"
        "12. If status is 'needs_more_info', list the exact missing items in 'missing_items' array.\n\n"
        "Respond ONLY with valid JSON in this exact format:\n"
        '{\n'
        '  "name": "...",\n'
        '  "program": "...",\n'
        '  "details": { /* ONLY include fields that were actually discussed in the interview */ },\n'
        '  "status": "eligible | not_eligible | needs_more_info",\n'
        '  "reasoning": "1-2 sentence explanation",\n'
        '  "missing_items": ["item 1", "item 2"],\n'
        '  "next_steps": "what the applicant should do next"\n'
        "}\n\n"
        f"Program Requirements:\n{context}\n\n"
        f"Interview Transcript:\n{full_transcript}"
    )

    client = get_llm_client()
    response = client.chat.completions.create(
        model="gpt-5.4-nano",
        messages=[{"role": "system", "content": eval_prompt}],
        temperature=0.1,
        max_tokens=1024,
    )

    content = response.choices[0].message.content or "{}"
    try:
        result = _extract_json(content)
    except Exception as e:
        # Fallback: create a basic result so we don't crash
        result = {
            "name": applicant.name,
            "program": applicant.program,
            "details": applicant.details or {},
            "status": "needs_more_info",
            "reasoning": f"Evaluation parsing failed: {e}. Please contact admissions.",
            "missing_items": [],
            "next_steps": "Contact Falcon University admissions office for manual review.",
        }

    # Normalize status field
    status = result.get("status", "needs_more_info").lower().strip()
    if status not in ("eligible", "not_eligible", "needs_more_info"):
        # Try to infer from old 'eligible' boolean field for backward compatibility
        if "eligible" in result:
            status = "eligible" if result["eligible"] else "not_eligible"
        else:
            status = "needs_more_info"
    result["status"] = status

    # Build clean user-facing message
    reasoning = result.get("reasoning", "").strip()
    next_steps = result.get("next_steps", "").strip()
    missing_items = result.get("missing_items", []) or []

    if status == "eligible":
        user_message = f"Congratulations! You are eligible for the {result.get('program', applicant.program)} program.\n\n{reasoning}"
    elif status == "not_eligible":
        user_message = f"Thank you for your interest. Unfortunately, you do not meet the eligibility criteria for the {result.get('program', applicant.program)} program at this time.\n\n{reasoning}"
    else:  # needs_more_info
        user_message = f"Thank you for providing your information. To complete your evaluation for the {result.get('program', applicant.program)} program, we need the following:\n"
        if missing_items:
            user_message += "\n" + "\n".join([f"- {item}" for item in missing_items])
        else:
            user_message += "\n- Additional required documents or information"
        if reasoning:
            user_message += f"\n\n{reasoning}"

    if next_steps:
        user_message += f"\n\nNext steps: {next_steps}"

    # Safe-merge details: update with non-null values from eval, keep existing data
    existing_details = applicant.details or {}
    new_details = result.get("details", {})
    merged_details = {**existing_details, **{k: v for k, v in new_details.items() if v is not None}}

    # Update applicant record
    applicant.name = result.get("name", applicant.name)
    applicant.program = result.get("program", applicant.program)
    applicant.details = merged_details
    applicant.is_complete = True
    db.commit()

    # Create assessment record
    assessment = models.Assessment(
        applicant_id=applicant.id,
        outcome=status,
        rule_summary=reasoning,
        transcript=full_transcript,
    )
    db.add(assessment)
    db.commit()

    return {**result, "user_message": user_message}


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

    # Query KB if program is known (active docs only)
    context = ""
    if applicant.program and applicant.program != "Unknown":
        try:
            active_ids = _get_active_doc_ids(db)
            docs = knowledge_base.query_kb(f"{applicant.program} admission requirements eligibility", k=4, active_doc_ids=active_ids)
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

    # Detect user intent to force evaluation (e.g., "evaluate", "done", "finish")
    force_eval = any(
        kw in payload.message.lower()
        for kw in ["evaluate", "evaluation", "done", "finish", "that's all", "that is all", "enough", "wrap up", "conclude"]
    )

    # Check for interview completion
    interview_complete = "[INTERVIEW_COMPLETE]" in answer or force_eval
    if "[INTERVIEW_COMPLETE]" in answer:
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
            answer = result.get("user_message", "Evaluation complete.")
        except Exception as e:
            answer = f"Interview complete, but evaluation failed: {e}"

    return {"response": answer, "interview_complete": interview_complete}


# -----------------------
# Admin endpoints
# -----------------------

@app.get("/admin/applicants", response_model=list[schemas.AdminApplicantListItem], tags=["Admin"])
def admin_list_applicants(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_admin_user),
):
    """List all applicants with their latest assessment outcome."""
    applicants = db.query(models.Applicant).order_by(models.Applicant.created_at.desc()).all()
    results = []
    for a in applicants:
        latest = db.query(models.Assessment).filter(models.Assessment.applicant_id == a.id).order_by(models.Assessment.created_at.desc()).first()
        results.append({
            "id": a.id,
            "name": a.name,
            "program": a.program,
            "is_complete": a.is_complete,
            "created_at": a.created_at,
            "outcome": latest.outcome if latest else None,
        })
    return results


@app.get("/admin/applicants/{applicant_id}", response_model=schemas.AdminApplicantDetail, tags=["Admin"])
def admin_get_applicant(
    applicant_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_admin_user),
):
    """Get full applicant details including assessment."""
    applicant = db.query(models.Applicant).filter(models.Applicant.id == applicant_id).first()
    if not applicant:
        raise HTTPException(status_code=404, detail="Applicant not found")
    latest = db.query(models.Assessment).filter(models.Assessment.applicant_id == applicant.id).order_by(models.Assessment.created_at.desc()).first()
    return {
        "id": applicant.id,
        "name": applicant.name,
        "program": applicant.program,
        "details": applicant.details,
        "is_complete": applicant.is_complete,
        "created_at": applicant.created_at,
        "assessment": latest,
    }


@app.get("/admin/applicants/{applicant_id}/transcript", response_model=list[schemas.AdminTranscriptMessage], tags=["Admin"])
def admin_get_transcript(
    applicant_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_admin_user),
):
    """Get full chat transcript for an applicant."""
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


@app.get("/admin/documents", response_model=list[schemas.AdminDocumentItem], tags=["Admin"])
def admin_list_documents(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_admin_user),
):
    """List all knowledge base documents with active status."""
    return db.query(models.Document).order_by(models.Document.uploaded_at.desc()).all()


@app.patch("/admin/documents/{doc_id}/toggle", response_model=schemas.AdminDocumentItem, tags=["Admin"])
def admin_toggle_document(
    doc_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_admin_user),
):
    """Toggle a document's active status."""
    doc = db.query(models.Document).filter(models.Document.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    doc.is_active = not doc.is_active
    db.commit()
    db.refresh(doc)
    return doc

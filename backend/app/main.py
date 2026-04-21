from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
import os

from app.database import engine, Base, get_db
from app import models, schemas, auth

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

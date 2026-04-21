from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os

from app.database import engine, Base
from app import models

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

import os
import chromadb
from chromadb.config import Settings
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import Chroma
from langchain.text_splitter import RecursiveCharacterTextSplitter

CHROMA_PERSIST_DIR = os.getenv("CHROMA_PERSIST_DIR", "/app/chroma_db")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

_chroma_client = None
_vectorstore = None


def get_chroma_client():
    global _chroma_client
    if _chroma_client is None:
        os.makedirs(CHROMA_PERSIST_DIR, exist_ok=True)
        _chroma_client = chromadb.PersistentClient(
            path=CHROMA_PERSIST_DIR,
            settings=Settings(anonymized_telemetry=False),
        )
    return _chroma_client


def get_vectorstore():
    global _vectorstore
    if _vectorstore is None:
        if not OPENAI_API_KEY:
            raise RuntimeError("OPENAI_API_KEY not set; cannot initialize embeddings")
        embeddings = OpenAIEmbeddings(openai_api_key=OPENAI_API_KEY)
        _vectorstore = Chroma(
            persist_directory=CHROMA_PERSIST_DIR,
            embedding_function=embeddings,
            client=get_chroma_client(),
            collection_name="falcon_kb",
        )
    return _vectorstore


def ingest_document(doc_id: int, text: str):
    """Chunk and add a document to the Chroma knowledge base."""
    if not OPENAI_API_KEY:
        return
    try:
        vs = get_vectorstore()
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=800,
            chunk_overlap=100,
        )
        chunks = splitter.split_text(text)
        metadatas = [{"doc_id": str(doc_id), "chunk_index": str(i)} for i in range(len(chunks))]
        ids = [f"doc_{doc_id}_chunk_{i}" for i in range(len(chunks))]
        vs.add_texts(texts=chunks, metadatas=metadatas, ids=ids)
    except Exception:
        pass


def delete_document(doc_id: int):
    """Remove all chunks belonging to a document from Chroma."""
    if not OPENAI_API_KEY:
        return
    try:
        vs = get_vectorstore()
        collection = vs._collection
        results = collection.get(where={"doc_id": str(doc_id)})
        if results and results.get("ids"):
            collection.delete(ids=results["ids"])
    except Exception:
        pass


def query_kb(query: str, k: int = 4):
    """Query the knowledge base and return relevant documents."""
    if not OPENAI_API_KEY:
        return []
    try:
        vs = get_vectorstore()
        return vs.similarity_search(query, k=k)
    except Exception:
        return []

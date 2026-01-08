import os
import uuid # Added for unique ID generation if needed
from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from langchain_chroma import Chroma
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_core.documents import Document
from backend.config import settings

# --- 1. Vector Store Configuration (ChromaDB) ---
VECTORSTORE_DIR = "./chroma_db"

def get_embeddings():
    return GoogleGenerativeAIEmbeddings(
        model="models/embedding-001",
        google_api_key=settings.GEMINI_API_KEY
    )

def get_vectorstore():
    return Chroma(
        persist_directory=VECTORSTORE_DIR,
        embedding_function=get_embeddings()
    )

# --- 2. Relational Database Configuration (SQLite for History) ---
# Ensure this matches the database name used in your connection strings
SQLITE_URL = "sqlite:///./chat_history.db" 
engine = create_engine(SQLITE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class ChatMessage(Base):
    """Table to store chat history persistent across restarts"""
    __tablename__ = "messages"
    
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String, index=True)
    role = Column(String)  # 'user' or 'assistant'
    content = Column(Text)
    department = Column(String, index=True, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow)

# Create the SQLite tables
Base.metadata.create_all(bind=engine)

# Ensure backward-compatible migration: add `department` column if it is missing
try:
    with engine.connect() as conn:
        res = conn.execute("PRAGMA table_info(messages);")
        cols = [row[1] for row in res.fetchall()]
        if "department" not in cols:
            conn.execute("ALTER TABLE messages ADD COLUMN department VARCHAR;")
            print("⚙️ Migrated messages table: added 'department' column")
except Exception:
    # If migration fails (older DB without column), remove DB and recreate tables (dev-only fallback)
    try:
        db_path = os.path.join(os.path.dirname(__file__), '..', 'chat_history.db')
        db_path = os.path.normpath(db_path)
        if os.path.exists(db_path):
            os.remove(db_path)
            print(f"⚠️ Removed existing DB at {db_path} to recreate schema (dev fallback)")
            Base.metadata.create_all(bind=engine)
    except Exception:
        pass

# --- 3. Database Seeding Logic ---

def seed_database():
    """Initializes the vector database with sample HR policy data."""
    vectorstore = get_vectorstore()
    
    # Check if collection exists and has data to avoid duplicates
    try:
        count = vectorstore._collection.count()
        if count > 0:
            print(f"ℹ️ Vector database already has {count} documents. Skipping seed.")
            return
    except Exception:
        # If collection doesn't exist yet, we proceed to seed
        pass

    sample_policies = [
        Document(
            page_content="Employees are entitled to 10 days of paid sick leave per year. Application is via the HR Portal.",
            metadata={
                "policy_name": "Sick Leave Policy",
                "source_file": "manual_v1.pdf",
                "department": "HR",
                "visibility": "EMPLOYEE",
                "is_latest": True
            }
        ),
        Document(
            page_content="The IT department provides hardware upgrades every 3 years for all developers.",
            metadata={
                "policy_name": "Hardware Policy",
                "source_file": "it_guidelines.pdf",
                "department": "IT",
                "visibility": "ALL",
                "is_latest": True
            }
        )
    ]
    
    vectorstore.add_documents(sample_policies)
    print(f"✅ Vector Database seeded with {len(sample_policies)} documents.")

if __name__ == "__main__":
    seed_database()
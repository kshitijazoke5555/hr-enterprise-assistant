from langchain_google_genai import GoogleGenerativeAIEmbeddings
from backend.config import settings


def get_embeddings():
    return GoogleGenerativeAIEmbeddings(
        model="models/embedding-001",
        google_api_key=settings.GEMINI_API_KEY
    )

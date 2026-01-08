
from dotenv import load_dotenv
import os

load_dotenv()

from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    # 🔐 API Keys
    GEMINI_API_KEY: str = Field(..., env="GEMINI_API_KEY")

    # 🧠 Vectorstore
    VECTORSTORE_DIR: str = "vectorstore"

    # 🗄 MongoDB
    MONGO_URI: str = Field(..., env="MONGO_URI")
    DB_NAME: str = Field(..., env="DB_NAME")

    class Config:
        env_file = ".env"
        extra = "forbid"   # security best practice


settings = Settings()

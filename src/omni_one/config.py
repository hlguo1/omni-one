"""
Configuration management for Omni-One Enterprise AI Platform
"""

import os
from pathlib import Path
from typing import Dict, Any
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class Config:
    """Application configuration"""

    # Flask configuration
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key-change-in-production")
    DEBUG = os.getenv("DEBUG", "False").lower() == "true"
    HOST = os.getenv("HOST", "0.0.0.0")
    PORT = int(os.getenv("PORT", "5003"))

    # AI Model configuration
    GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

    # Database configuration
    DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:pass@localhost:5432/omni_one")
    REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")

    # Enterprise features
    ENABLE_ETHICAL_AI = os.getenv("ENABLE_ETHICAL_AI", "true").lower() == "true"
    ENABLE_QUANTUM_OPTIMIZATION = os.getenv("ENABLE_QUANTUM_OPTIMIZATION", "true").lower() == "true"
    ENABLE_FEDERATED_LEARNING = os.getenv("ENABLE_FEDERATED_LEARNING", "true").lower() == "true"
    ENABLE_MULTIMODAL_PROCESSING = os.getenv("ENABLE_MULTIMODAL_PROCESSING", "true").lower() == "true"

    # File paths
    BASE_DIR = Path(__file__).parent.parent.parent
    SRC_DIR = BASE_DIR / "src"
    LOGS_DIR = BASE_DIR / "logs"
    DATA_DIR = BASE_DIR / "data"
    MODELS_DIR = BASE_DIR / "models"

    @classmethod
    def to_dict(cls) -> Dict[str, Any]:
        """Convert config to dictionary"""
        return {
            key: getattr(cls, key)
            for key in dir(cls)
            if not key.startswith('_') and not callable(getattr(cls, key))
        }

# Global config instance
config = Config()
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    APP_NAME: str = "渠道线索判重服务"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True
    
    DATABASE_URL: str = "sqlite:///./lead_deduplication.db"
    
    API_PREFIX: str = "/api/v1"
    
    SECRET_KEY: str = "your-secret-key-change-in-production"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440
    
    LEAD_PHONE_HASH_SALT: str = "lead-dedup-salt"
    
    DEFAULT_CHANNEL_PRIORITY: int = 100
    CROSS_STORE_CONFLICT_ENABLED: bool = True
    
    class Config:
        env_file = ".env"


settings = Settings()

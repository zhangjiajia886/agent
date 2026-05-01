from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    APP_NAME: str = "TTS Application"
    APP_ENV: str = "development"
    DEBUG: bool = True
    SECRET_KEY: str
    API_V1_PREFIX: str = "/api/v1"
    
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    
    DATABASE_URL: str
    DATABASE_POOL_SIZE: int = 20
    DATABASE_MAX_OVERFLOW: int = 10
    
    REDIS_URL: str
    REDIS_MAX_CONNECTIONS: int = 50
    
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    
    FISH_API_URL: str = "https://api.fish.audio"
    FISH_API_KEY: str
    FISH_DEFAULT_VOICE: str
    FISH_TTS_MODEL: str = "s2-pro"
    
    UPLOAD_DIR: str = "./uploads"
    MAX_UPLOAD_SIZE: int = 104857600
    ALLOWED_AUDIO_FORMATS: str = "mp3,wav,m4a,flac,ogg"
    
    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:5173"
    CORS_ALLOW_CREDENTIALS: bool = True
    
    LOG_LEVEL: str = "INFO"
    LOG_FILE: str = "./logs/app.log"

    # ---- Soul AI Lab 配置 ----
    SOUL_PODCAST_SPACE: str = "Soul-AILab/SoulX-Podcast-1.7B"
    SOUL_PODCAST_URL: str = ""
    SOUL_SINGER_SPACE: str = "Soul-AILab/SoulX-Singer"
    SOUL_FLASHHEAD_SPACE: str = "Soul-AILab/SoulX-FlashHead"
    SOUL_API_TIMEOUT: int = 300
    SOUL_HF_TOKEN: str = ""
    SOUL_ENABLED: bool = True
    SOUL_MIDI_EDITOR_URL: str = "https://huggingface.co/spaces/Soul-AILab/SoulX-Singer-Midi-Editor"

    # ---- ComfyUI 漫剧生成 ----
    COMFYUI_URL: str = "https://u982127-7772b8fbe6d9.bjb2.seetacloud.com:8443"
    COMFYUI_TIMEOUT: int = 600
    COMFYUI_ENABLED: bool = True

    JIMENG_ENABLED: bool = False
    JIMENG_AK: str = ""
    JIMENG_SK: str = ""
    JIMENG_REGION: str = "cn-north-1"
    JIMENG_HOST: str = "visual.volcengineapi.com"
    JIMENG_TIMEOUT: int = 300
    JIMENG_DEFAULT_WIDTH: int = 768
    JIMENG_DEFAULT_HEIGHT: int = 1024
    JIMENG_LEGACY_REQ_KEY: str = "jimeng_high_aes_general_v21_L"

    # ---- AIPro 聚合平台 (OpenAI 兼容, Claude/GPT/Gemini) ----
    AIPRO_BASE_URL: str = "https://vip.aipro.love/v1"
    AIPRO_API_KEY: str = ""
    AIPRO_DEFAULT_MODEL: str = "claude-sonnet-4-6"

    # ---- 南格 L1 轻量 LLM ----
    L1_LLM_BINDING: str = "southgrid"
    L1_LLM_MODEL: str = "qwen2.5-3b-instruct"
    L1_LLM_BINDING_HOST: str = "http://192.168.0.246:5030/ai-gateway/predict"
    L1_LLM_BINDING_API_KEY: str = ""
    L1_LLM_CUSTCODE: str = ""
    L1_LLM_COMPONENTCODE: str = ""

    # ---- 南格 主 LLM ----
    LLM_MODEL: str = "Qwen3-32B"
    LLM_BASE_URL: str = "http://192.168.0.246:5030/ai-gateway/predict"
    LLM_API_KEY: str = ""
    LLM_CUSTCODE: str = ""
    LLM_COMPONENTCODE: str = ""

    # ---- 南格 多模态 ----
    MMP_MODEL: str = "Qwen3-VL"
    MMP_BASE_URL: str = "http://192.168.0.246:5030/ai-gateway/predict"
    MMP_API_KEY: str = ""
    MMP_CUSTCODE: str = ""
    MMP_COMPONENTCODE: str = ""

    # ---- 南格 Embedding ----
    EMBEDDING_MODEL: str = "bge-m3"
    EMBEDDING_BASE_URL: str = "http://192.168.0.246:5030/ai-gateway/predict"
    EMBEDDING_API_KEY: str = ""
    EMBEDDING_CUSTCODE: str = ""
    EMBEDDING_COMPONENTCODE: str = ""
    EMBEDDING_DIM: int = 1024
    
    @property
    def cors_origins_list(self) -> List[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]
    
    @property
    def allowed_audio_formats_list(self) -> List[str]:
        return [fmt.strip() for fmt in self.ALLOWED_AUDIO_FORMATS.split(",")]
    
    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()

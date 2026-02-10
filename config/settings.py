"""Application settings with Pydantic v2 - Versione Integrata e Completa."""
import json
from functools import lru_cache
from pathlib import Path
from typing import Literal, Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Tutte le configurazioni dell'applicazione."""
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # === Modalità Esecuzione ===
    execution_mode: Literal["LOCAL", "RUNPOD"] = Field(
        default="LOCAL",
        alias="EXECUTION_MODE"
    )

    # === LLM Provider ===
    llm_provider: Literal["gemini", "moonshot"] = Field(
        default="gemini",
        alias="LLM_PROVIDER"
    )

    # === API Keys ===
    gemini_api_key: str = Field(
        default="",
        alias="GEMINI_API_KEY"
    )
    moonshot_api_key: str = Field(
        default="",
        alias="MOONSHOT_API_KEY"
    )

    # === RunPod Configuration ===
    runpod_id: Optional[str] = Field(
        default=None,
        alias="RUNPOD_ID"
    )
    runpod_api_key: Optional[str] = Field(
        default=None,
        alias="RUNPOD_API_KEY"
    )

    # === SD/ComfyUI URLs ===
    local_sd_url: str = Field(default="http://127.0.0.1:7860")
    local_comfy_url: str = Field(default="http://127.0.0.1:8188")

    # === Path Configuration (Per VideoClient su RunPod) ===
    comfy_output_path: str = Field(
        default="/workspace/ComfyUI/output",
        alias="COMFY_OUTPUT_PATH"
    )

    # === Google Credentials ===
    google_credentials_path: Path = Field(
        default=Path("google_credentials.json")
    )

    # === Database ===
    database_url: str = Field(default="sqlite+aiosqlite:///storage/saves/luna_v3.db")

    # === Memory Settings ===
    memory_history_limit: int = 50
    memory_prune_count: int = 20

    # === Image Generation ===
    image_width: int = 896
    image_height: int = 1152
    image_steps: int = 24
    image_sampler: str = "DPM++ 2M Karras"

    # VAE settings
    vae_path: Optional[str] = None
    use_full_precision_vae: bool = True

    # === Video Generation ===
    video_enabled: bool = False
    video_motion_speed: int = 6

    @field_validator("execution_mode", mode="before")
    @classmethod
    def uppercase_mode(cls, v: str) -> str:
        return v.upper() if isinstance(v, str) else v

    @property
    def is_runpod(self) -> bool:
        """True se in modalità cloud RunPod."""
        return self.execution_mode == "RUNPOD"

    @property
    def sd_url(self) -> str:
        """URL endpoint Stable Diffusion."""
        if self.is_runpod and self.runpod_id:
            return f"https://{self.runpod_id}-7860.proxy.runpod.net"
        return self.local_sd_url

    @property
    def comfy_url(self) -> Optional[str]:
        """URL endpoint ComfyUI."""
        if not self.is_runpod:
            return self.local_comfy_url
        if self.runpod_id:
            return f"https://{self.runpod_id}-8188.proxy.runpod.net"
        return self.local_comfy_url

    @property
    def video_available(self) -> bool:
        """True se il video generation è disponibile.
        
        Video è disponibile solo in modalità RUNPOD con ComfyUI.
        In modalità LOCAL la generazione video è disabilitata.
        """
        # Video richiede RunPod (ComfyUI con nodi video)
        if not self.is_runpod:
            return False
        return self.comfy_url is not None and self.runpod_id is not None

    def validate_setup(self) -> list[str]:
        """Valida la configurazione."""
        errors = []
        if not self.gemini_api_key:
            errors.append("GEMINI_API_KEY mancante nel .env")
        if self.is_runpod and not self.runpod_id:
            errors.append("RUNPOD_ID mancante per modalità RUNPOD")
        return errors


@lru_cache()
def get_settings() -> Settings:
    """Singleton settings instance."""
    return Settings()


# === User Preferences (Fix per ImportError) ===
_USER_PREFS_PATH = Path("storage/config/user_prefs.json")

def load_user_prefs() -> dict:
    """Carica preferenze utente salvate."""
    if _USER_PREFS_PATH.exists():
        try:
            return json.loads(_USER_PREFS_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}

def save_user_prefs(prefs: dict):
    """Salva preferenze utente."""
    try:
        _USER_PREFS_PATH.parent.mkdir(parents=True, exist_ok=True)
        _USER_PREFS_PATH.write_text(json.dumps(prefs, indent=2), encoding="utf-8")
    except Exception as e:
        print(f"[!] Could not save user prefs: {e}")
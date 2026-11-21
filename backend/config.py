"""Settings from .env (git-ignored). See .env.example."""
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv

from backend.paths import ROOT

load_dotenv(ROOT / ".env")

Task = Literal["analyse", "bullet", "answer", "tailor", "extras"]
TASKS: tuple[Task, ...] = ("analyse", "bullet", "answer", "tailor", "extras")

# "anthropic": the Claude API. "openai": any OpenAI-compatible chat completions API
# (OpenAI, Gemini, OpenRouter, Groq, or a local model through Ollama or LM Studio).
PROVIDERS = ("anthropic", "openai")

# Claude defaults: cheap Haiku for the short, simple steps; Sonnet where wording quality matters.
# Other providers have no defaults: set CV_TAILOR_MODEL.
DEFAULT_MODELS: dict[str, str] = {
    "analyse": "claude-haiku-5-5",
    "bullet": "claude-haiku-5-5",
    "answer": "claude-haiku-5-5",
    "tailor": "claude-sonnet-5-5",
    "extras": "claude-sonnet-5-5",
}


@dataclass(frozen=True)
class Settings:
    provider: str
    api_key: str | None
    base_url: str | None
    models: dict[str, str | None]
    db_path: Path

    @property
    def configured(self) -> bool:
        """Enough to make a call: a key, or (OpenAI-compatible) a local server that needs none."""
        return bool(self.api_key or (self.provider == "openai" and self.base_url))

    def model_for(self, task: Task) -> str | None:
        return self.models[task]


def _models(provider: str) -> dict[str, str | None]:
    """Per task: CV_TAILOR_MODEL_<TASK>, else CV_TAILOR_MODEL (all tasks), else the Claude default."""
    everything = os.environ.get("CV_TAILOR_MODEL") or None
    defaults = DEFAULT_MODELS if provider == "anthropic" else {}
    return {
        task: os.environ.get(f"CV_TAILOR_MODEL_{task.upper()}") or everything or defaults.get(task)
        for task in TASKS
    }


def get_settings() -> Settings:
    provider = (os.environ.get("CV_TAILOR_PROVIDER") or "anthropic").strip().lower()
    if provider == "anthropic":
        api_key = os.environ.get("ANTHROPIC_API_KEY")
    else:
        api_key = os.environ.get("CV_TAILOR_API_KEY") or os.environ.get("OPENAI_API_KEY")
    return Settings(
        provider=provider,
        api_key=api_key or None,
        base_url=os.environ.get("CV_TAILOR_BASE_URL") or None,
        models=_models(provider),
        db_path=Path(os.environ.get("CV_TAILOR_DB", ROOT / "data" / "cv_tailor.db")),
    )

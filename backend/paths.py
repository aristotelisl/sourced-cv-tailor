import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# CV_TAILOR_PROFILE points the app at another profile file (end-to-end tests use a copy).
PROFILE_PATH = Path(os.environ.get("CV_TAILOR_PROFILE") or ROOT / "data" / "profile.yaml")
TEMPLATES_DIR = ROOT / "templates"
EXAMPLES_DIR = ROOT / "examples"
# Starting point for a new profile (scripts/start.ps1 copies it to data/profile.yaml on first run).
EXAMPLE_PROFILE_PATH = EXAMPLES_DIR / "profile.example.yaml"
# The tailored CV shown to the LLM as a format example: your own (data/example.tailored.json,
# git-ignored) if you have one, otherwise the fictional one in examples/.
_OWN_EXAMPLE = ROOT / "data" / "example.tailored.json"
EXAMPLE_CV_PATH = _OWN_EXAMPLE if _OWN_EXAMPLE.exists() else EXAMPLES_DIR / "example_frontend.tailored.json"

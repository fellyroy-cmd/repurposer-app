"""Repurposer App package.

Loads .env from the project root before any module reads os.environ, so the README's
"copy .env.example to .env" step actually works. Real environment variables (set by a
host like Render) still win, because load_dotenv never overrides what's already set.
"""
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

"""
Centralized LLM Client Factory

All pipeline modules should import their LLM client from here instead of
creating their own. This ensures:
  - Single source of truth for model names and configuration
  - Easy model switching without editing multiple files
  - Consistent retry and timeout settings across the pipeline

Provider priority:
  1. OpenAI (if OPENAI_API_KEY is set) — best quality, most consistent
  2. Groq (if GROQ_API_KEY is set) — fast, cost-effective fallback
"""

import os
from dotenv import load_dotenv
from openai import AsyncOpenAI

load_dotenv()


# ── Configuration ────────────────────────────────────────────────────────────

# Primary models (OpenAI) — highest quality, best JSON adherence
OAI_MODEL_ANALYSIS = "gpt-4o"
OAI_MODEL_VERIFICATION = "gpt-4o"
OAI_MODEL_SYNTHESIS = "gpt-4o"
OAI_MODEL_GENERATION = "gpt-4o-mini"
OAI_MODEL_CHAT = "gpt-4o-mini"

# Groq models — fast inference, current production models
# IMPORTANT: llama3-70b-8192 and mixtral-8x7b-32768 are DECOMMISSIONED.
# Use only models listed at https://console.groq.com/docs/models
GROQ_MODEL_ANALYSIS = "openai/gpt-oss-120b"       # 120B params, strong reasoning
GROQ_MODEL_VERIFICATION = "openai/gpt-oss-120b"   # Same model for consistency
GROQ_MODEL_SYNTHESIS = "openai/gpt-oss-120b"      # Report formatting needs quality
GROQ_MODEL_GENERATION = "openai/gpt-oss-20b"      # 20B params, fast for clause rewrite
GROQ_MODEL_CHAT = "openai/gpt-oss-20b"            # Chat needs speed over depth


def get_provider() -> str:
    """Returns 'openai' or 'groq' based on which API key is available."""
    if os.environ.get("OPENAI_API_KEY"):
        return "openai"
    if os.environ.get("GROQ_API_KEY"):
        return "groq"
    return "none"


def get_openai_client() -> AsyncOpenAI:
    """
    Returns a configured AsyncOpenAI client.
    Uses OPENAI_API_KEY from environment, falls back to GROQ_API_KEY.
    Both providers work via the OpenAI-compatible API.
    """
    api_key = os.environ.get("OPENAI_API_KEY")
    if api_key:
        return AsyncOpenAI(api_key=api_key)
    
    groq_key = os.environ.get("GROQ_API_KEY")
    if groq_key:
        return AsyncOpenAI(
            api_key=groq_key,
            base_url="https://api.groq.com/openai/v1"
        )

    raise RuntimeError(
        "Neither OPENAI_API_KEY nor GROQ_API_KEY found in environment. "
        "Add one to your .env file. See .env.example for format."
    )


def get_model(role: str) -> str:
    """
    Get the model name for a specific pipeline role.
    Roles: analysis, verification, synthesis, generation, chat
    """
    is_groq = not bool(os.environ.get("OPENAI_API_KEY"))

    if is_groq:
        models = {
            "analysis": GROQ_MODEL_ANALYSIS,
            "verification": GROQ_MODEL_VERIFICATION,
            "synthesis": GROQ_MODEL_SYNTHESIS,
            "generation": GROQ_MODEL_GENERATION,
            "chat": GROQ_MODEL_CHAT,
        }
    else:
        models = {
            "analysis": OAI_MODEL_ANALYSIS,
            "verification": OAI_MODEL_VERIFICATION,
            "synthesis": OAI_MODEL_SYNTHESIS,
            "generation": OAI_MODEL_GENERATION,
            "chat": OAI_MODEL_CHAT,
        }
        
    return models.get(role, models["analysis"])


# ── Standalone Test ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    provider = get_provider()
    print(f"Active provider: {provider}")
    for role in ["analysis", "verification", "synthesis", "generation", "chat"]:
        model = get_model(role)
        print(f"  {role}: {model}")
    if provider != "none":
        print(f"\nClient base_url: {get_openai_client().base_url}")


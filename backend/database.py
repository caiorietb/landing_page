"""
Cliente Supabase — um único ponto de configuração.

Falha rápido (crash no import) se as env vars estiverem faltando —
é melhor o container não subir do que subir e aceitar POSTs que
seriam perdidos.
"""

from __future__ import annotations

import os

from dotenv import load_dotenv
from supabase import Client, create_client


load_dotenv()


def _require_env(name: str) -> str:
    valor = os.getenv(name)
    if not valor:
        raise RuntimeError(
            f"Variável de ambiente obrigatória ausente: {name}. "
            f"Veja .env.example."
        )
    return valor


SUPABASE_URL = _require_env("SUPABASE_URL")
SUPABASE_KEY = _require_env("SUPABASE_KEY")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


def health_check() -> dict[str, str]:
    """Ping simples — usado no endpoint GET /health."""
    try:
        # Consulta barata só para confirmar conectividade.
        supabase.table("feiras").select("id").limit(1).execute()
        return {"database": "connected"}
    except Exception as exc:  # noqa: BLE001 — queremos o erro bruto
        return {"database": "error", "detail": str(exc)}

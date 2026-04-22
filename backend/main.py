"""
Entrypoint FastAPI — Blu Engajamento Comercial / Pipe de Conexões.

Camadas:
    main.py          ← aqui: app, CORS, logging, roteamento de alto nível
    schemas.py       ← Pydantic v2 (payload da LP)
    validators.py    ← validadores fiscais puros
    idempotency.py   ← cálculo da chave de dedup
    database.py      ← cliente Supabase + health check
    repositories.py  ← única camada que fala com o banco
    services.py      ← regras de negócio (orquestra os repositórios)
    integrations/    ← plug-and-play para HubSpot, Excel, S3 (stubs)
"""

from __future__ import annotations

import logging
import os
from typing import Any, Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from .database import health_check as db_health
from . import repositories as repo
from .schemas import IndicacaoCreate, IndicacaoCreatedOut
from .services import FornecedorDesconhecido, criar_indicacao


# ─── logging ────────────────────────────────────────────────────────────

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s :: %(message)s",
)
logger = logging.getLogger("blu.engajamento")


# ─── app ────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Blu Engajamento Comercial",
    version="2.0.0",
    description=(
        "Backend da LP de indicações de varejo (substitui o fluxo n8n). "
        "Fonte de verdade = Supabase. HubSpot/Excel são sinks "
        "atualizados de forma assíncrona."
    ),
)

allowed_origins = [
    o.strip()
    for o in os.getenv("ALLOWED_ORIGINS", "http://localhost:3000,http://localhost:5500").split(",")
    if o.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


# ─── rotas ──────────────────────────────────────────────────────────────

@app.get("/", tags=["meta"])
def root() -> dict[str, str]:
    return {"status": "ok", "service": "blu-engajamento-comercial", "version": app.version}


@app.get("/health", tags=["meta"])
def health() -> dict[str, Any]:
    return {"status": "ok", **db_health()}


@app.post("/indicacoes", status_code=201, response_model=IndicacaoCreatedOut, tags=["indicacoes"])
def post_indicacao(payload: IndicacaoCreate) -> IndicacaoCreatedOut:
    try:
        result = criar_indicacao(payload)
    except FornecedorDesconhecido as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:  # noqa: BLE001
        logger.exception("erro ao criar indicação")
        raise HTTPException(status_code=500, detail="Erro interno ao salvar indicação.") from exc

    return IndicacaoCreatedOut(
        id=result["id"],
        status=result["status"],
        idempotency_key=result["idempotency_key"],
        duplicada=result["duplicada"],
        mensagem=(
            "Indicação já registrada anteriormente (dedup idempotente)."
            if result["duplicada"]
            else "Indicação salva com sucesso."
        ),
    )


@app.get("/fornecedores", tags=["master_data"])
def get_fornecedores(ativos: bool = True) -> list[dict[str, Any]]:
    """Lista fornecedores para popular o dropdown do form."""
    try:
        return repo.list_fornecedores(ativos=ativos)
    except Exception as exc:  # noqa: BLE001
        logger.exception("erro ao listar fornecedores")
        raise HTTPException(status_code=500, detail="Erro ao listar fornecedores.") from exc


@app.get("/feiras", tags=["master_data"])
def get_feiras(ativos: bool = True) -> list[dict[str, Any]]:
    """Lista feiras ativas (catálogo fechado da LP)."""
    try:
        return repo.list_feiras(ativos=ativos)
    except Exception as exc:  # noqa: BLE001
        logger.exception("erro ao listar feiras")
        raise HTTPException(status_code=500, detail="Erro ao listar feiras.") from exc


@app.get("/indicacoes", tags=["indicacoes"])
def get_indicacoes(
    executivo: Optional[str] = Query(None, description="Filtro parcial (nome ou email)."),
    cnpj_industria: Optional[str] = Query(None, description="CNPJ do fornecedor (só dígitos)."),
    limit: int = Query(500, ge=1, le=2000),
) -> list[dict[str, Any]]:
    try:
        return repo.listar_indicacoes(
            executivo=executivo, cnpj_industria=cnpj_industria, limit=limit
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("erro ao listar indicações")
        raise HTTPException(status_code=500, detail="Erro ao consultar indicações.") from exc

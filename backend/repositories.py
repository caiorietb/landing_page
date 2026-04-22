"""
Repositórios — única camada que fala com o Supabase para leitura/escrita.

Mantém a lógica de SQL fora do código HTTP (routes.py) e do domínio
(services.py), facilitando teste e troca de backend no futuro.
"""

from __future__ import annotations

from typing import Any, Optional

from .database import supabase


# ─── executivos ─────────────────────────────────────────────────────────

def upsert_executivo(nome: Optional[str], email: Optional[str]) -> Optional[str]:
    """Retorna o UUID do executivo, se der para identificar."""
    if not email:
        return None
    resp = (
        supabase.table("executivos")
        .upsert(
            {"nome": nome or email, "email": email, "ativo": True},
            on_conflict="email",
        )
        .execute()
    )
    data = resp.data or []
    return data[0]["id"] if data else None


# ─── fornecedores ───────────────────────────────────────────────────────

def find_fornecedor(codigo: Optional[str], cnpj: Optional[str]) -> Optional[dict[str, Any]]:
    q = supabase.table("fornecedores").select("*").limit(1)
    if codigo:
        q = q.eq("codigo", codigo)
    elif cnpj:
        q = q.eq("cnpj", cnpj)
    else:
        return None
    resp = q.execute()
    return (resp.data or [None])[0]


# ─── feiras ─────────────────────────────────────────────────────────────

def find_feira_id(nome: str) -> Optional[str]:
    resp = (
        supabase.table("feiras")
        .select("id")
        .eq("nome", nome)
        .limit(1)
        .execute()
    )
    data = resp.data or []
    return data[0]["id"] if data else None


# ─── gestores / representantes / lojistas ──────────────────────────────

def upsert_gestor(payload: dict[str, Any]) -> str:
    resp = (
        supabase.table("gestores")
        .upsert(payload, on_conflict="email")
        .execute()
    )
    return resp.data[0]["id"]


def upsert_representante(payload: dict[str, Any]) -> str:
    resp = (
        supabase.table("representantes")
        .upsert(payload, on_conflict="tipo_documento,documento")
        .execute()
    )
    return resp.data[0]["id"]


def upsert_lojista(payload: dict[str, Any]) -> str:
    resp = (
        supabase.table("lojistas")
        .upsert(payload, on_conflict="cnpj")
        .execute()
    )
    return resp.data[0]["id"]


# ─── indicação ──────────────────────────────────────────────────────────

def find_indicacao_by_idempotency_key(key: str) -> Optional[dict[str, Any]]:
    resp = (
        supabase.table("indicacoes")
        .select("id, status, idempotency_key")
        .eq("idempotency_key", key)
        .is_("deleted_at", "null")
        .limit(1)
        .execute()
    )
    return (resp.data or [None])[0]


def insert_indicacao(payload: dict[str, Any]) -> dict[str, Any]:
    resp = supabase.table("indicacoes").insert(payload).execute()
    if not resp.data:
        raise RuntimeError("Falha ao inserir indicação: resposta vazia.")
    return resp.data[0]


def insert_indicacao_lojistas(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not rows:
        return []
    resp = supabase.table("indicacao_lojistas").insert(rows).execute()
    return resp.data or []


# ─── eventos de integração (fila async) ───────────────────────────────

def enqueue_integration_event(indicacao_id: str, target: str, payload: dict[str, Any]) -> None:
    supabase.table("integration_events").insert(
        {
            "indicacao_id": indicacao_id,
            "target": target,
            "payload": payload,
            "status": "pending",
        }
    ).execute()


# ─── master data (para o form popular dropdowns) ──────────────────────

def list_fornecedores(ativos: bool = True, limit: int = 2000) -> list[dict[str, Any]]:
    q = (
        supabase.table("fornecedores")
        .select("id, codigo, razao_social, cnpj, apelido")
        .order("codigo")
        .limit(limit)
    )
    if ativos:
        q = q.eq("ativo", True).is_("deleted_at", "null")
    resp = q.execute()
    return resp.data or []


def list_feiras(ativos: bool = True) -> list[dict[str, Any]]:
    q = supabase.table("feiras").select("id, nome").order("nome")
    if ativos:
        q = q.eq("ativo", True)
    resp = q.execute()
    return resp.data or []


# ─── listagem / painel ──────────────────────────────────────────────────

def listar_indicacoes(
    *,
    executivo: Optional[str] = None,
    cnpj_industria: Optional[str] = None,
    limit: int = 500,
) -> list[dict[str, Any]]:
    q = (
        supabase.table("v_indicacoes_detalhe")
        .select("*")
        .order("created_at", desc=True)
        .limit(limit)
    )
    if executivo:
        q = q.or_(
            f"executivo_nome.ilike.%{executivo}%,executivo_email.ilike.%{executivo}%"
        )
    if cnpj_industria:
        q = q.eq("fornecedor_cnpj", cnpj_industria)
    resp = q.execute()
    return resp.data or []

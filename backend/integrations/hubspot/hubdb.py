"""
backend.integrations.hubspot.hubdb
──────────────────────────────────
Lookups nas tabelas HubDB da Blu.

Tabelas-alvo (IDs no HubSpot Portal 7012573):
    • 116939574 — "Usuários HubSpot (Inscrito por)"
    • 27538329  — "Fornecedores (Nome do fornecedor)"

Estes lookups alimentam as tabelas `executivos` e `fornecedores` do
Supabase. A ideia é:

    - Ao receber uma indicação, o backend já tem os IDs locais.
    - Se não tem, chama `HubDBLookup.find_executivo_by_email(...)`
      ou `find_fornecedor_by_codigo(...)`, faz upsert no Supabase e
      cacheia.

⚠️  SKELETON: stubs com NotImplementedError.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, TypedDict

from .client import HubSpotClient

HUBDB_TABLE_EXECUTIVOS   = 116_939_574
HUBDB_TABLE_FORNECEDORES = 27_538_329


class ExecutivoHubDBRow(TypedDict):
    """Projeção mínima da linha de HubDB de executivos."""
    hubdb_row_id: int
    nome: str
    email: str


class FornecedorHubDBRow(TypedDict):
    """Projeção mínima da linha de HubDB de fornecedores."""
    hubdb_row_id: int
    codigo: str
    razao_social: str
    cnpj: str
    apelido: Optional[str]


@dataclass(frozen=True)
class HubDBLookup:
    """
    Lookups simples no HubDB. Contrato estável para o resto do sistema
    mesmo que o layout do HubDB mude no futuro.
    """

    client: HubSpotClient

    # ── Executivos ─────────────────────────────────────────────────────
    def find_executivo_by_email(self, email: str) -> Optional[ExecutivoHubDBRow]:
        """
        Busca um executivo pelo email. None se não achar.
        Endpoint: /hubdb/api/v2/tables/{id}/rows?email=...
        """
        raise NotImplementedError("HubDBLookup.find_executivo_by_email")

    def list_executivos(self, limit: int = 500) -> list[ExecutivoHubDBRow]:
        """Dump de todos os executivos — usado no sync completo de master data."""
        raise NotImplementedError("HubDBLookup.list_executivos")

    # ── Fornecedores ───────────────────────────────────────────────────
    def find_fornecedor_by_codigo(self, codigo: str) -> Optional[FornecedorHubDBRow]:
        """Busca por código ("0010", "2106", etc.). None se não achar."""
        raise NotImplementedError("HubDBLookup.find_fornecedor_by_codigo")

    def find_fornecedor_by_cnpj(self, cnpj: str) -> Optional[FornecedorHubDBRow]:
        """Busca pelo CNPJ (só dígitos). None se não achar."""
        raise NotImplementedError("HubDBLookup.find_fornecedor_by_cnpj")

    def list_fornecedores(self, limit: int = 1000) -> list[FornecedorHubDBRow]:
        """Dump completo — usado no sync inicial para popular `fornecedores`."""
        raise NotImplementedError("HubDBLookup.list_fornecedores")

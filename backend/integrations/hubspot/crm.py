"""
backend.integrations.hubspot.crm
────────────────────────────────
Operações em Contacts / Companies / Deals.

Fluxo por indicação (ver `docs/fluxo_atual.md` §3):

    1. Gestor   → Contact  (email é a chave natural)
    2. REP      → Contact  (CPF/CNPJ é a chave natural)
    3. Lojista  → Company  (CNPJ é a chave natural)
    4. Deal     → Pipeline "Conexões" / estágio inicial
                 → associa Deal ↔ Company(lojista) ↔ Contact(gestor, rep)

Todos os métodos aqui devem ser idempotentes: procuram por chave natural
antes de criar. Retornam o `hubspot_id` do objeto (criado ou existente).

⚠️  SKELETON: stubs com NotImplementedError.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, TypedDict

from .client import HubSpotClient


# ─── contratos de entrada ───────────────────────────────────────────────

class ContactPayload(TypedDict, total=False):
    email: str
    nome: str
    telefone: Optional[str]
    cargo: Optional[str]           # apenas para gestores
    documento: Optional[str]        # apenas para reps
    tipo_documento: Optional[str]   # "cpf" | "cnpj"
    tipo_bonificacao: Optional[str]


class CompanyPayload(TypedDict, total=False):
    cnpj: str
    razao_social: str
    nome_fantasia: str
    email: Optional[str]
    whatsapp: Optional[str]


class DealPayload(TypedDict, total=False):
    dealname: str
    pipeline: str                   # ID do pipe "Conexões"
    dealstage: str                  # estágio inicial
    tipo_produto: str               # PagBlu | CredBlu | Split
    condicao_especial: bool
    condicao_especial_descricao: Optional[str]
    observacoes: Optional[str]
    fornecedor_codigo: str
    associated_company_id: Optional[str]
    associated_contact_ids: list[str]


# ─── cliente CRM ────────────────────────────────────────────────────────

@dataclass(frozen=True)
class HubSpotCRM:
    client: HubSpotClient

    # Contacts ──────────────────────────────────────────────────────────
    def upsert_contact(self, payload: ContactPayload) -> str:
        """
        Procura por email; se existir, faz PATCH; senão cria.
        Retorna o `hubspot_contact_id`.
        """
        raise NotImplementedError("HubSpotCRM.upsert_contact")

    def find_contact_by_email(self, email: str) -> Optional[str]:
        """Retorna o contact_id ou None."""
        raise NotImplementedError("HubSpotCRM.find_contact_by_email")

    # Companies ─────────────────────────────────────────────────────────
    def upsert_company(self, payload: CompanyPayload) -> str:
        """
        Procura por `cnpj` (property customizada); se existir, PATCH;
        senão cria. Retorna `hubspot_company_id`.
        """
        raise NotImplementedError("HubSpotCRM.upsert_company")

    def find_company_by_cnpj(self, cnpj: str) -> Optional[str]:
        raise NotImplementedError("HubSpotCRM.find_company_by_cnpj")

    # Deals ─────────────────────────────────────────────────────────────
    def create_deal(self, payload: DealPayload) -> str:
        """
        Cria o deal no pipeline "Conexões" e associa empresas/contatos.
        Retorna `hubspot_deal_id`.
        """
        raise NotImplementedError("HubSpotCRM.create_deal")

    def associate(
        self,
        *,
        from_type: str,   # "deals" | "contacts" | "companies"
        from_id: str,
        to_type: str,
        to_id: str,
        association_type_id: int,
    ) -> None:
        raise NotImplementedError("HubSpotCRM.associate")

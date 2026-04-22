"""
backend.integrations.hubspot.sync
─────────────────────────────────
Orquestração de alto nível: dada uma indicação persistida no Supabase,
replica no HubSpot (Contacts + Companies + Deal + associações).

Esta função é o ÚNICO ponto de entrada que o worker de
`integration_events` precisa conhecer. Toda a complexidade de resolver
gestor/rep/lojista, criar deals e fazer associações fica escondida aqui.

Plug-and-play: quando a integração for ativada, basta preencher os
corpos em client.py / hubdb.py / crm.py. O endpoint HTTP
(`POST /indicacoes`) não precisa saber nada disso.

⚠️  SKELETON: a função devolve um dict vazio e não faz nada.
"""

from __future__ import annotations

from typing import Any, TypedDict

from .client import HubSpotClient
from .crm import HubSpotCRM
from .hubdb import HubDBLookup


class SyncResult(TypedDict, total=False):
    hubspot_deal_ids:    list[str]
    hubspot_contact_ids: list[str]
    hubspot_company_ids: list[str]
    errors:              list[dict[str, Any]]


def sync_indicacao_to_hubspot(indicacao_snapshot: dict[str, Any]) -> SyncResult:
    """
    Sincroniza uma indicação (snapshot completo vindo do Supabase)
    com o HubSpot.

    `indicacao_snapshot` segue o shape de `v_indicacoes_detalhe` +
    lista expandida de lojistas (`indicacao_lojistas` JOIN `lojistas`).

    Regras:
        * idempotente — roda N vezes e produz o mesmo estado no HubSpot;
        * best-effort — se falhar para 1 lojista, continua os outros e
          registra o erro em `errors`;
        * nunca grava no Supabase aqui — quem escreve de volta é o worker
          que invocou esta função (usando o retorno).

    Returns:
        SyncResult com os IDs criados/achados no HubSpot.
    """
    raise NotImplementedError(
        "Integração HubSpot desligada — implementar junto com client/hubdb/crm."
    )

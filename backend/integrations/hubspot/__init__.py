"""
HubSpot integration — stubs plug-and-play.

Estado atual: SKELETON. Todos os métodos fazem raise NotImplementedError.
O objetivo é que, quando for a hora de ligar a integração, seja só
preencher os corpos das funções — assinaturas, tipagem e contratos já
estão definidos.

Pré-requisitos (quando implementar):
    - env var HUBSPOT_PRIVATE_APP_TOKEN com escopos:
        * hubdb
        * crm.objects.contacts.read/write
        * crm.objects.companies.read/write
        * crm.objects.deals.read/write
    - httpx[http2] (já está em requirements.txt)
    - retry com backoff exponencial (tenacity, opcional)

Mapeamento das tabelas HubDB:
    • 116939574 → espelho em Supabase.executivos  (coluna "Inscrito por")
    • 27538329  → espelho em Supabase.fornecedores (nome do fornecedor + CNPJ)
"""

from .client import HubSpotClient, HubSpotAuthError, HubSpotError
from .hubdb import HubDBLookup
from .crm import HubSpotCRM
from .sync import sync_indicacao_to_hubspot

__all__ = [
    "HubSpotClient",
    "HubSpotAuthError",
    "HubSpotError",
    "HubDBLookup",
    "HubSpotCRM",
    "sync_indicacao_to_hubspot",
]

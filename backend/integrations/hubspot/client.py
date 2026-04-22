"""
backend.integrations.hubspot.client
───────────────────────────────────
Cliente HTTP de baixo nível para a API do HubSpot.

Autentica via Private App Token (`Authorization: Bearer …`) lido de
`HUBSPOT_PRIVATE_APP_TOKEN`. Todas as chamadas passam por aqui para
centralizar retries, rate limiting e logging estruturado.

⚠️  SKELETON: nenhum método faz HTTP de verdade ainda. Todos disparam
    NotImplementedError para deixar explícito que a integração não está
    ligada. Veja `sync_indicacao_to_hubspot` para o plug-and-play point.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Optional


HUBSPOT_BASE_URL = "https://api.hubapi.com"
HUBSPOT_ENV_TOKEN = "HUBSPOT_PRIVATE_APP_TOKEN"


class HubSpotError(Exception):
    """Base de todos os erros do módulo."""


class HubSpotAuthError(HubSpotError):
    """Token ausente, inválido ou sem os escopos necessários."""


@dataclass(frozen=True)
class HubSpotClient:
    """
    Cliente minimalista para a API do HubSpot.

    Uso esperado (quando implementado):

        client = HubSpotClient.from_env()
        data   = client.get("/crm/v3/objects/contacts/search", params={...})

    Por enquanto, todas as chamadas levantam NotImplementedError.
    """

    token: str
    base_url: str = HUBSPOT_BASE_URL
    timeout_seconds: float = 15.0

    # ── construtores ───────────────────────────────────────────────────
    @classmethod
    def from_env(cls) -> "HubSpotClient":
        token = os.getenv(HUBSPOT_ENV_TOKEN)
        if not token:
            raise HubSpotAuthError(
                f"Variável de ambiente {HUBSPOT_ENV_TOKEN} não definida."
            )
        return cls(token=token)

    # ── HTTP primitives ────────────────────────────────────────────────
    def get(self, path: str, params: Optional[dict[str, Any]] = None) -> dict:
        """
        GET em `{base_url}{path}`. Devolve JSON decodificado.

        Erros esperados: HubSpotAuthError (401/403), HubSpotError (outros).
        """
        raise NotImplementedError("HubSpotClient.get não implementado.")

    def post(self, path: str, json: dict[str, Any]) -> dict:
        """POST com body JSON. Mesma política de erros do GET."""
        raise NotImplementedError("HubSpotClient.post não implementado.")

    def patch(self, path: str, json: dict[str, Any]) -> dict:
        """PATCH com body JSON. Mesma política de erros do GET."""
        raise NotImplementedError("HubSpotClient.patch não implementado.")

"""
Chave de idempotência determinística.

Mesmo payload (fornecedor + participantes + lojistas + dia) = mesma
`idempotency_key`, garantindo que reenvios não criem duplicatas
(problema P1 do doc de fluxo).
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from zoneinfo import ZoneInfo

from .schemas import IndicacaoCreate


_BRASIL = ZoneInfo("America/Sao_Paulo")


def dia_corrente_brasil() -> str:
    """Retorna 'YYYY-MM-DD' no fuso de São Paulo."""
    return datetime.now(tz=_BRASIL).strftime("%Y-%m-%d")


def calcular_idempotency_key(
    indicacao: IndicacaoCreate,
    dia: str | None = None,
) -> str:
    """
    Hash SHA-256 (hex, 64 chars) de uma projeção canônica da indicação.
    Agrupa por dia para que reenvios no mesmo dia colapsem e
    reenvios em dias diferentes sejam tratados como novas indicações
    (o que é o comportamento desejado na prática).
    """
    fingerprint = {
        "fornecedor_codigo": indicacao.fornecedor.codigo,
        "fornecedor_cnpj":   indicacao.fornecedor.cnpj,
        "tipo":              indicacao.tipo.value,
        "gestor_email":      (indicacao.gestor.email if indicacao.gestor else None),
        "rep_doc":           (indicacao.representante.documento if indicacao.representante else None),
        "lojistas":          sorted(l.cnpj for l in indicacao.lojistas),
        "eh_feira":          indicacao.eh_feira,
        "feira":             indicacao.feira_nome,
        "dia":               dia or dia_corrente_brasil(),
    }
    raw = json.dumps(fingerprint, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()

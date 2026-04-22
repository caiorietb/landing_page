"""
Camada de domínio — orquestra repositórios e regras de negócio.

Responsabilidade: transformar o `IndicacaoCreate` validado em linhas
persistidas (com dedup idempotente) e enfileirar os eventos de
integração para o worker.
"""

from __future__ import annotations

import logging
from typing import Any

from .idempotency import calcular_idempotency_key
from .schemas import IndicacaoCreate
from . import repositories as repo


logger = logging.getLogger(__name__)


class FornecedorDesconhecido(Exception):
    """Fornecedor informado não existe na master data."""


def criar_indicacao(payload: IndicacaoCreate) -> dict[str, Any]:
    """
    Fluxo:
        1. Resolve fornecedor (obrigatório).
        2. Calcula idempotency_key e checa duplicata.
        3. Upserts: executivo, gestor, rep, lojistas.
        4. Insere indicação + linhas de lojista.
        5. Enfileira eventos de integração para HubSpot/Excel/S3.
    Devolve um dict com `id`, `status`, `idempotency_key`, `duplicada`.
    """
    # 1. Fornecedor
    fornecedor = repo.find_fornecedor(
        payload.fornecedor.codigo, payload.fornecedor.cnpj
    )
    if not fornecedor:
        raise FornecedorDesconhecido(
            "Fornecedor não cadastrado. Rode o sync de HubDB antes de indicar."
        )

    # 2. Idempotência
    key = calcular_idempotency_key(payload)
    existente = repo.find_indicacao_by_idempotency_key(key)
    if existente:
        logger.info("idempotency hit: %s", key)
        return {
            "id": existente["id"],
            "status": existente["status"],
            "idempotency_key": key,
            "duplicada": True,
        }

    # 3. Upserts de entidades relacionadas
    executivo_id = repo.upsert_executivo(
        payload.executivo.nome, str(payload.executivo.email) if payload.executivo.email else None
    )

    gestor_id = None
    if payload.gestor:
        gestor_id = repo.upsert_gestor(
            {
                "nome":   payload.gestor.nome,
                "email":  str(payload.gestor.email),
                "celular": payload.gestor.celular,
                "cargo":  payload.gestor.cargo.value if payload.gestor.cargo else None,
                "fornecedor_id": fornecedor["id"],
            }
        )

    representante_id = None
    if payload.representante:
        doc = payload.representante.documento
        representante_id = repo.upsert_representante(
            {
                "nome":     payload.representante.nome,
                "email":    str(payload.representante.email) if payload.representante.email else None,
                "celular":  payload.representante.celular,
                "tipo_documento": "cpf" if len(doc) == 11 else "cnpj",
                "documento":      doc,
                "tipo_bonificacao": payload.representante.tipo_bonificacao.value
                                    if payload.representante.tipo_bonificacao else None,
            }
        )

    feira_id = (
        repo.find_feira_id(payload.feira_nome)
        if (payload.eh_feira and payload.feira_nome)
        else None
    )

    # 4. Insert indicação + lojistas
    indicacao_row = repo.insert_indicacao(
        {
            "executivo_id": executivo_id,
            "executivo_nome_snapshot":  payload.executivo.nome,
            "executivo_email_snapshot": str(payload.executivo.email) if payload.executivo.email else None,
            "fornecedor_id": fornecedor["id"],
            "tipo": payload.tipo.value,
            "eh_feira": payload.eh_feira,
            "feira_id": feira_id,
            "participantes": payload.participantes.value if payload.participantes else None,
            "gestor_id": gestor_id,
            "representante_id": representante_id,
            "prioridade": payload.prioridade.value,
            "data_contato": payload.data_contato.isoformat() if payload.data_contato else None,
            "status": "recebida",
            "idempotency_key": key,
        }
    )

    rows_lojistas = []
    for lojista_in in payload.lojistas:
        lojista_id = repo.upsert_lojista(
            {
                "cnpj":          lojista_in.cnpj,
                "razao_social":  lojista_in.razao_social,
                "nome_fantasia": lojista_in.nome_fantasia,
                "email_principal": str(lojista_in.email),
                "whatsapp":      lojista_in.whatsapp,
            }
        )
        rows_lojistas.append(
            {
                "indicacao_id": indicacao_row["id"],
                "lojista_id":   lojista_id,
                "tipo_produto": lojista_in.tipo_produto.value,
                "condicao_especial": lojista_in.condicao_especial,
                "condicao_especial_descricao": lojista_in.condicao_especial_descricao,
                "observacoes":  lojista_in.observacoes,
            }
        )
    repo.insert_indicacao_lojistas(rows_lojistas)

    # 5. Enfileira integrações (plug-and-play — workers ainda não ligados)
    for target in ("hubspot_deal", "excel_append"):
        repo.enqueue_integration_event(
            indicacao_row["id"], target, {"indicacao_id": indicacao_row["id"]}
        )

    logger.info(
        "indicacao criada id=%s fornecedor=%s lojistas=%d",
        indicacao_row["id"], fornecedor["codigo"], len(rows_lojistas),
    )

    return {
        "id":              indicacao_row["id"],
        "status":          indicacao_row["status"],
        "idempotency_key": key,
        "duplicada":       False,
    }

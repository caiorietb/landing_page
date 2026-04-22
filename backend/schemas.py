"""
Schemas Pydantic v2 para o endpoint de indicação.

Alinhados ao form em produção (ver `docs/fluxo_atual.md` §2), não ao
MVP reduzido da v1. Campos de data de cadastro **não estão** aqui:
o backend preenche `created_at` automaticamente (correção P4).
"""

from __future__ import annotations

from datetime import date
from enum import Enum
from typing import Optional

from pydantic import BaseModel, EmailStr, Field, model_validator

from .validators import somente_digitos, validar_cnpj, validar_cpf


# ─── enums (espelham os do Postgres) ────────────────────────────────────

class TipoIndicacao(str, Enum):
    varejo = "varejo"
    representante = "representante"


class TipoProduto(str, Enum):
    PagBlu = "PagBlu"
    CredBlu = "CredBlu"
    Split = "Split"


class Prioridade(str, Enum):
    imediato = "imediato"
    programado = "programado"


class Participantes(str, Enum):
    apenas_gestor = "apenas_gestor"
    gestor_e_representante = "gestor_e_representante"
    gestor_e_vendas_interno = "gestor_e_vendas_interno"
    apenas_representante = "apenas_representante"
    direta = "direta"


class CargoGestor(str, Enum):
    CEO_Dono = "CEO_Dono"
    Diretor_Financeiro = "Diretor_Financeiro"
    Gerente_Financeiro = "Gerente_Financeiro"
    Supervisor_Financeiro = "Supervisor_Financeiro"
    Analista_Financeiro = "Analista_Financeiro"
    Diretor_Comercial = "Diretor_Comercial"
    Gerente_Comercial = "Gerente_Comercial"
    Supervisor_Comercial = "Supervisor_Comercial"
    Analista_Comercial = "Analista_Comercial"
    Outros = "Outros"


class TipoBonificacao(str, Enum):
    RPA = "RPA"
    NotaFiscal = "NotaFiscal"


# ─── sub-entidades do payload ───────────────────────────────────────────

class ExecutivoIn(BaseModel):
    nome: Optional[str] = None
    email: Optional[EmailStr] = None

    @model_validator(mode="after")
    def _ao_menos_um(self) -> "ExecutivoIn":
        if not (self.nome or self.email):
            raise ValueError("Informe nome OU email do executivo.")
        return self


class FornecedorRef(BaseModel):
    """Identificador do fornecedor (indústria parceira)."""
    codigo: Optional[str] = None    # "0010", "2106"...
    cnpj: Optional[str] = None

    @model_validator(mode="after")
    def _ao_menos_um(self) -> "FornecedorRef":
        if not (self.codigo or self.cnpj):
            raise ValueError("Informe código ou CNPJ do fornecedor.")
        if self.cnpj:
            d = somente_digitos(self.cnpj)
            if len(d) != 14 or not validar_cnpj(d):
                raise ValueError("CNPJ do fornecedor inválido.")
            object.__setattr__(self, "cnpj", d)
        return self


class GestorIn(BaseModel):
    nome: str = Field(min_length=1)
    email: EmailStr
    celular: Optional[str] = None
    cargo: Optional[CargoGestor] = None


class RepresentanteIn(BaseModel):
    nome: str = Field(min_length=1)
    documento: str
    email: Optional[EmailStr] = None
    celular: Optional[str] = None
    tipo_bonificacao: Optional[TipoBonificacao] = None
    fornecedor_principal: Optional[FornecedorRef] = None

    @model_validator(mode="after")
    def _valida_doc(self) -> "RepresentanteIn":
        d = somente_digitos(self.documento)
        if len(d) == 11:
            if not validar_cpf(d):
                raise ValueError("CPF do representante inválido.")
        elif len(d) == 14:
            if not validar_cnpj(d):
                raise ValueError("CNPJ do representante inválido.")
        else:
            raise ValueError(
                f"Documento do representante deve ter 11 (CPF) ou 14 (CNPJ) dígitos — recebido: {len(d)}."
            )
        object.__setattr__(self, "documento", d)
        return self


class LojistaIn(BaseModel):
    cnpj: str
    razao_social: str = Field(min_length=1)
    nome_fantasia: str = Field(min_length=1)
    email: EmailStr
    whatsapp: str = Field(min_length=8)
    tipo_produto: TipoProduto
    condicao_especial: bool = False
    condicao_especial_descricao: Optional[str] = Field(default=None, max_length=1000)
    observacoes: Optional[str] = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def _valida(self) -> "LojistaIn":
        d = somente_digitos(self.cnpj)
        if len(d) != 14 or not validar_cnpj(d):
            raise ValueError("CNPJ do lojista inválido.")
        object.__setattr__(self, "cnpj", d)

        if self.condicao_especial and not self.condicao_especial_descricao:
            raise ValueError(
                "Descreva a condição especial (ou marque 'Não')."
            )
        if not self.condicao_especial:
            object.__setattr__(self, "condicao_especial_descricao", None)
        return self


# ─── payload de criação ─────────────────────────────────────────────────

class IndicacaoCreate(BaseModel):
    """
    Payload enviado pela LP ao endpoint POST /indicacoes.

    IMPORTANTE: não há campo de data. `created_at` é set pelo banco.
    """
    executivo: ExecutivoIn
    fornecedor: FornecedorRef
    tipo: TipoIndicacao
    eh_feira: bool = False
    feira_nome: Optional[str] = None

    participantes: Optional[Participantes] = None
    gestor: Optional[GestorIn] = None
    representante: Optional[RepresentanteIn] = None

    prioridade: Prioridade = Prioridade.imediato
    data_contato: Optional[date] = None

    lojistas: list[LojistaIn] = Field(min_length=1, max_length=50)

    @model_validator(mode="after")
    def _valida_condicionais(self) -> "IndicacaoCreate":
        if self.eh_feira and not self.feira_nome:
            raise ValueError("Informe o nome da feira.")
        if not self.eh_feira and self.feira_nome:
            object.__setattr__(self, "feira_nome", None)

        if self.prioridade is Prioridade.programado and not self.data_contato:
            raise ValueError("Informe a data para contato (prioridade programado).")
        if self.prioridade is Prioridade.imediato:
            object.__setattr__(self, "data_contato", None)

        if self.tipo is TipoIndicacao.varejo and not self.participantes:
            raise ValueError("Informe quem participou da indicação.")

        cnpjs_lojistas = [l.cnpj for l in self.lojistas]
        if len(cnpjs_lojistas) != len(set(cnpjs_lojistas)):
            raise ValueError("Há CNPJs de lojista duplicados na mesma indicação.")
        return self


# ─── respostas ──────────────────────────────────────────────────────────

class IndicacaoCreatedOut(BaseModel):
    id: str
    status: str
    idempotency_key: str
    duplicada: bool
    mensagem: str

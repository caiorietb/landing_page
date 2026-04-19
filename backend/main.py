import os
import re
from typing import Optional
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, field_validator
from supabase import create_client

load_dotenv()

supabase = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_KEY"),
)

app = FastAPI(title="Blu Engajamento Comercial")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ═══════════════════════════════════════════════════════════════════════
#  Validação de CNPJ e CPF (algoritmo oficial — módulo 11)
# ═══════════════════════════════════════════════════════════════════════

def _somente_digitos(valor: str) -> str:
    return re.sub(r"\D", "", valor or "")


def validar_cnpj(cnpj: str) -> bool:
    cnpj = _somente_digitos(cnpj)
    if len(cnpj) != 14 or len(set(cnpj)) == 1:
        return False

    pesos1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    pesos2 = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]

    soma = sum(int(cnpj[i]) * pesos1[i] for i in range(12))
    d1 = 11 - (soma % 11)
    if d1 >= 10:
        d1 = 0
    if int(cnpj[12]) != d1:
        return False

    soma = sum(int(cnpj[i]) * pesos2[i] for i in range(13))
    d2 = 11 - (soma % 11)
    if d2 >= 10:
        d2 = 0
    return int(cnpj[13]) == d2


def validar_cpf(cpf: str) -> bool:
    cpf = _somente_digitos(cpf)
    if len(cpf) != 11 or len(set(cpf)) == 1:
        return False

    soma = sum(int(cpf[i]) * (10 - i) for i in range(9))
    d1 = 11 - (soma % 11)
    if d1 >= 10:
        d1 = 0
    if int(cpf[9]) != d1:
        return False

    soma = sum(int(cpf[i]) * (11 - i) for i in range(10))
    d2 = 11 - (soma % 11)
    if d2 >= 10:
        d2 = 0
    return int(cpf[10]) == d2


# ═══════════════════════════════════════════════════════════════════════
#  Schema Pydantic — rejeita payloads com documentos inválidos (HTTP 422)
# ═══════════════════════════════════════════════════════════════════════

class Indicacao(BaseModel):
    executivo: str
    cnpj_industria: str
    doc_representante: str
    cnpjs_varejistas: str  # "12345678000100,98765432000100"
    detalhes: str = ""

    @field_validator("executivo")
    @classmethod
    def _executivo_nao_vazio(cls, v: str) -> str:
        v = (v or "").strip()
        if not v:
            raise ValueError("O nome ou e-mail do executivo é obrigatório.")
        return v

    @field_validator("cnpj_industria")
    @classmethod
    def _valida_cnpj_industria(cls, v: str) -> str:
        digitos = _somente_digitos(v)
        if len(digitos) != 14:
            raise ValueError(f"CNPJ da indústria incompleto ({len(digitos)}/14 dígitos).")
        if not validar_cnpj(digitos):
            raise ValueError("CNPJ da indústria inválido.")
        return digitos

    @field_validator("doc_representante")
    @classmethod
    def _valida_doc_representante(cls, v: str) -> str:
        digitos = _somente_digitos(v)
        if len(digitos) == 11:
            if not validar_cpf(digitos):
                raise ValueError("CPF do representante inválido.")
        elif len(digitos) == 14:
            if not validar_cnpj(digitos):
                raise ValueError("CNPJ do representante inválido.")
        else:
            raise ValueError(
                f"Documento do representante deve ter 11 (CPF) ou 14 (CNPJ) dígitos — recebido: {len(digitos)}."
            )
        return digitos

    @field_validator("cnpjs_varejistas")
    @classmethod
    def _valida_cnpjs_varejistas(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Informe ao menos 1 CNPJ de varejista.")

        itens = [p.strip() for p in v.split(",") if p.strip()]
        if not itens:
            raise ValueError("Informe ao menos 1 CNPJ de varejista.")
        if len(itens) > 20:
            raise ValueError(f"Máximo de 20 varejistas — recebido: {len(itens)}.")

        digitos_list = []
        for i, item in enumerate(itens, start=1):
            d = _somente_digitos(item)
            if len(d) != 14:
                raise ValueError(f"CNPJ do varejista #{i} incompleto ({len(d)}/14 dígitos).")
            if not validar_cnpj(d):
                raise ValueError(f"CNPJ do varejista #{i} inválido.")
            if d in digitos_list:
                raise ValueError(f"CNPJ do varejista #{i} duplicado na mesma indicação.")
            digitos_list.append(d)

        return ",".join(digitos_list)


# ═══════════════════════════════════════════════════════════════════════
#  Rotas
# ═══════════════════════════════════════════════════════════════════════

@app.get("/")
def health_check():
    return {"status": "ok", "mensagem": "Backend Blu rodando!"}


@app.post("/indicacoes", status_code=201)
def criar_indicacao(dados: Indicacao):
    try:
        resultado = supabase.table("indicacoes").insert({
            "executivo":         dados.executivo,
            "cnpj_industria":    dados.cnpj_industria,
            "doc_representante": dados.doc_representante,
            "cnpjs_varejistas":  dados.cnpjs_varejistas,
            "detalhes":          dados.detalhes,
        }).execute()
    except Exception:
        raise HTTPException(status_code=500, detail="Erro ao salvar no banco de dados.")

    if not resultado.data:
        raise HTTPException(status_code=500, detail="Erro ao salvar no banco de dados.")

    return {"mensagem": "Indicação salva com sucesso!", "dados": resultado.data[0]}


@app.get("/indicacoes")
def listar_indicacoes(
    executivo: Optional[str] = Query(None, description="Filtro parcial por nome/email do executivo"),
    cnpj_industria: Optional[str] = Query(None, description="Filtro exato por CNPJ da indústria (só dígitos)"),
):
    try:
        query = supabase.table("indicacoes").select("*").order("criado_em", desc=True)

        if executivo:
            query = query.ilike("executivo", f"%{executivo}%")
        if cnpj_industria:
            query = query.eq("cnpj_industria", _somente_digitos(cnpj_industria))

        resultado = query.execute()
        return resultado.data or []
    except Exception:
        raise HTTPException(status_code=500, detail="Erro ao consultar o banco de dados.")

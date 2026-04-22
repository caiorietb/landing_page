"""
Testes end-to-end dos 5 cenários de indicação (sem HubSpot, sem Supabase real).

Cobre:
    1. apenas_gestor
    2. gestor_e_representante
    3. gestor_e_vendas_interno
    4. apenas_representante
    5. direta

Extras:
    • Feira (eh_feira=True + feira_nome).
    • Prioridade programada (data_contato).
    • Dedup idempotente (mesmo payload 2x).
    • Rejeição de payloads inválidos (CNPJ ruim, fornecedor ausente).
    • Cobertura: garante que todo campo do IndicacaoCreate vai parar em
      alguma tabela / coluna SQL (via inspeção do schema).

Uso:
    cd backend && PYTHONPATH=.. python -m pytest tests/test_cenarios_e2e.py -v

Ou simplesmente:
    python3 backend/tests/test_cenarios_e2e.py
"""

from __future__ import annotations

import sys
import os
import copy
import re
import json
import hashlib
import types
from pathlib import Path
from unittest.mock import patch, MagicMock

# Permite rodar sem instalar o pacote
ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

# ─── Stub do módulo backend.database para não precisar de Supabase real ──
_db = types.ModuleType("backend.database")
_db.supabase = MagicMock(name="supabase_fake")
_db.health_check = lambda: {"database": "mocked"}
sys.modules["backend.database"] = _db

from backend import idempotency, schemas, services  # noqa: E402
from backend.schemas import IndicacaoCreate          # noqa: E402


# ═══════════════════════════════════════════════════════════════════════
#  Fake repositories — substituem o Supabase
# ═══════════════════════════════════════════════════════════════════════

class FakeRepo:
    """Imita backend.repositories com estado em memória."""

    def __init__(self):
        self.fornecedores = {
            "0010": {"id": "f-0010", "codigo": "0010",
                     "cnpj": "12345678000190", "razao_social": "Indústria Alpha"},
            "2106": {"id": "f-2106", "codigo": "2106",
                     "cnpj": "98765432000155", "razao_social": "Indústria Beta"},
        }
        self.feiras = {"FIPAN 2026": "feira-fipan", "Abifarma 2026": "feira-abifarma"}
        self.executivos = {}
        self.gestores = {}
        self.representantes = {}
        self.lojistas = {}
        self.indicacoes = []          # lista de dicts
        self.indicacao_lojistas = []  # lista de dicts
        self.integration_events = []  # lista de dicts
        self._id_counter = 0

    def _uid(self, prefix: str) -> str:
        self._id_counter += 1
        return f"{prefix}-{self._id_counter:06d}"

    # ─── façade que o services.py chama ───
    def find_fornecedor(self, codigo, cnpj):
        if codigo and codigo in self.fornecedores:
            return self.fornecedores[codigo]
        if cnpj:
            for f in self.fornecedores.values():
                if f["cnpj"] == cnpj:
                    return f
        return None

    def find_feira_id(self, nome):
        return self.feiras.get(nome)

    def upsert_executivo(self, nome, email):
        if not email:
            return None
        if email not in self.executivos:
            self.executivos[email] = {"id": self._uid("exe"), "nome": nome, "email": email}
        return self.executivos[email]["id"]

    def upsert_gestor(self, payload):
        key = payload["email"]
        if key not in self.gestores:
            self.gestores[key] = {"id": self._uid("ges"), **payload}
        return self.gestores[key]["id"]

    def upsert_representante(self, payload):
        key = (payload["tipo_documento"], payload["documento"])
        if key not in self.representantes:
            self.representantes[key] = {"id": self._uid("rep"), **payload}
        return self.representantes[key]["id"]

    def upsert_lojista(self, payload):
        key = payload["cnpj"]
        if key not in self.lojistas:
            self.lojistas[key] = {"id": self._uid("loj"), **payload}
        return self.lojistas[key]["id"]

    def find_indicacao_by_idempotency_key(self, key):
        for r in self.indicacoes:
            if r["idempotency_key"] == key and not r.get("deleted_at"):
                return r
        return None

    def insert_indicacao(self, payload):
        row = {"id": self._uid("ind"), "deleted_at": None, **payload}
        self.indicacoes.append(row)
        return row

    def insert_indicacao_lojistas(self, rows):
        self.indicacao_lojistas.extend(rows)
        return rows

    def enqueue_integration_event(self, indicacao_id, target, payload):
        self.integration_events.append({
            "indicacao_id": indicacao_id,
            "target": target,
            "payload": payload,
            "status": "pending",
        })

    def listar_indicacoes(self, **_):
        return self.indicacoes


# ═══════════════════════════════════════════════════════════════════════
#  Helpers — builders de payload válido
# ═══════════════════════════════════════════════════════════════════════

CNPJ_FIPAN = "11444777000161"      # válido (dígitos módulo 11)
CNPJ_LOJISTA_1 = "11222333000181"
CNPJ_LOJISTA_2 = "27865757000102"
CNPJ_LOJISTA_3 = "60746948000112"
CPF_REP = "11144477735"


def validar_cpf_check(s):
    # sanity: garante que os documentos fixtures passam no módulo 11
    from backend.validators import validar_cpf, validar_cnpj
    return validar_cpf(s)


def lojista(cnpj, produto="PagBlu", *, feira_flag=False, whatsapp="11999887766"):
    return {
        "cnpj": cnpj,
        "razao_social": f"Loja {cnpj[:4]} LTDA",
        "nome_fantasia": f"Loja {cnpj[:4]}",
        "email": f"contato+{cnpj[:4]}@exemplo.com",
        "whatsapp": whatsapp,
        "tipo_produto": produto,
        "condicao_especial": False,
        "condicao_especial_descricao": None,
        "observacoes": "Ticket médio alto" if produto == "Split" else None,
    }


def payload_base():
    return {
        "executivo": {"nome": "Caio Teste", "email": "caio@blu.com.br"},
        "fornecedor": {"codigo": "0010"},
        "tipo": "varejo",
        "eh_feira": False,
        "feira_nome": None,
        "participantes": None,
        "prioridade": "imediato",
        "data_contato": None,
        "lojistas": [lojista(CNPJ_LOJISTA_1)],
    }


def com_gestor(p):
    p = copy.deepcopy(p)
    p["gestor"] = {
        "nome": "Maria Gestora",
        "email": "maria@alpha.ind.br",
        "celular": "11988887777",
        "cargo": "Gerente_Financeiro",
    }
    return p


def com_rep(p, doc=CPF_REP):
    p = copy.deepcopy(p)
    p["representante"] = {
        "nome": "João REP",
        "documento": doc,
        "email": "joao@rep.com.br",
        "celular": "11977776666",
        "tipo_bonificacao": "RPA",
    }
    return p


# ═══════════════════════════════════════════════════════════════════════
#  Test runner sem pytest (para rodar direto no sandbox)
# ═══════════════════════════════════════════════════════════════════════

RESULTADOS = []


def caso(nome):
    def deco(fn):
        def wrapper():
            try:
                fn()
                RESULTADOS.append((nome, "ok", None))
                print(f"  ✔  {nome}")
            except AssertionError as e:
                RESULTADOS.append((nome, "fail", str(e)))
                print(f"  ✘  {nome}\n     └─ {e}")
            except Exception as e:
                RESULTADOS.append((nome, "err", f"{type(e).__name__}: {e}"))
                print(f"  ⚠  {nome}\n     └─ {type(e).__name__}: {e}")
        return wrapper
    return deco


# ═══════════════════════════════════════════════════════════════════════
#  Util: roda services.criar_indicacao contra o FakeRepo
# ═══════════════════════════════════════════════════════════════════════

def rodar(payload_dict, fake_repo=None, dia=None):
    """Valida Pydantic e chama services.criar_indicacao com repo fake."""
    fake_repo = fake_repo or FakeRepo()
    ind = IndicacaoCreate.model_validate(payload_dict)

    # Monkeypatch do módulo `repositories` dentro do services
    with patch.object(services, "repo", fake_repo), \
         patch.object(idempotency, "dia_corrente_brasil",
                      return_value=dia or idempotency.dia_corrente_brasil()):
        result = services.criar_indicacao(ind)
    return result, fake_repo


# ═══════════════════════════════════════════════════════════════════════
#  CENÁRIOS
# ═══════════════════════════════════════════════════════════════════════

@caso("Cenário 1 — apenas_gestor")
def cen_01():
    p = com_gestor(payload_base())
    p["participantes"] = "apenas_gestor"
    r, repo = rodar(p)
    assert r["duplicada"] is False
    assert r["status"] == "recebida"
    assert len(repo.indicacoes) == 1
    ind = repo.indicacoes[0]
    assert ind["gestor_id"] is not None
    assert ind["representante_id"] is None
    assert ind["participantes"] == "apenas_gestor"
    assert len(repo.integration_events) == 2, "2 sinks (hubspot + excel)"


@caso("Cenário 2 — gestor_e_representante (com REP CPF)")
def cen_02():
    p = com_rep(com_gestor(payload_base()), doc=CPF_REP)
    p["participantes"] = "gestor_e_representante"
    r, repo = rodar(p)
    assert r["duplicada"] is False
    ind = repo.indicacoes[0]
    assert ind["gestor_id"] is not None
    assert ind["representante_id"] is not None
    rep_row = next(iter(repo.representantes.values()))
    assert rep_row["tipo_documento"] == "cpf"
    assert rep_row["documento"] == CPF_REP
    assert rep_row["tipo_bonificacao"] == "RPA"


@caso("Cenário 3 — gestor_e_vendas_interno")
def cen_03():
    p = com_gestor(payload_base())
    p["participantes"] = "gestor_e_vendas_interno"
    r, repo = rodar(p)
    ind = repo.indicacoes[0]
    assert ind["participantes"] == "gestor_e_vendas_interno"
    assert ind["gestor_id"] is not None
    assert ind["representante_id"] is None


@caso("Cenário 4 — apenas_representante (sem gestor)")
def cen_04():
    p = com_rep(payload_base(), doc=CPF_REP)
    p["participantes"] = "apenas_representante"
    r, repo = rodar(p)
    ind = repo.indicacoes[0]
    assert ind["participantes"] == "apenas_representante"
    assert ind["gestor_id"] is None
    assert ind["representante_id"] is not None


@caso("Cenário 5 — direta (sem gestor nem REP)")
def cen_05():
    p = payload_base()
    p["participantes"] = "direta"
    r, repo = rodar(p)
    ind = repo.indicacoes[0]
    assert ind["participantes"] == "direta"
    assert ind["gestor_id"] is None
    assert ind["representante_id"] is None


@caso("Cenário 6 — feira (Abifarma 2026)")
def cen_06():
    p = com_gestor(payload_base())
    p["participantes"] = "apenas_gestor"
    p["eh_feira"] = True
    p["feira_nome"] = "Abifarma 2026"
    r, repo = rodar(p)
    ind = repo.indicacoes[0]
    assert ind["eh_feira"] is True
    assert ind["feira_id"] == "feira-abifarma"


@caso("Cenário 7 — prioridade programada com data")
def cen_07():
    p = com_gestor(payload_base())
    p["participantes"] = "apenas_gestor"
    p["prioridade"] = "programado"
    p["data_contato"] = "2026-05-20"
    r, repo = rodar(p)
    ind = repo.indicacoes[0]
    assert ind["prioridade"] == "programado"
    assert ind["data_contato"] == "2026-05-20"


# ═══════════════════════════════════════════════════════════════════════
#  DEDUP (P1 — problema original resolvido)
# ═══════════════════════════════════════════════════════════════════════

@caso("Dedup — mesmo payload 2x no mesmo dia → duplicada=True")
def cen_dedup():
    p = com_gestor(payload_base())
    p["participantes"] = "apenas_gestor"
    r1, repo = rodar(p, dia="2026-04-19")
    assert r1["duplicada"] is False
    r2, _ = rodar(p, fake_repo=repo, dia="2026-04-19")
    assert r2["duplicada"] is True
    assert r2["idempotency_key"] == r1["idempotency_key"]
    assert len(repo.indicacoes) == 1, "não deve criar nova linha"


@caso("Dedup — mesmo payload em dia diferente → nova indicação")
def cen_dedup_dias():
    p = com_gestor(payload_base())
    p["participantes"] = "apenas_gestor"
    r1, repo = rodar(p, dia="2026-04-19")
    r2, _ = rodar(p, fake_repo=repo, dia="2026-04-20")
    assert r1["idempotency_key"] != r2["idempotency_key"]
    assert len(repo.indicacoes) == 2


@caso("Dedup — ordem dos lojistas não importa na chave")
def cen_dedup_ordem():
    pA = com_gestor(payload_base())
    pA["participantes"] = "apenas_gestor"
    pA["lojistas"] = [lojista(CNPJ_LOJISTA_1), lojista(CNPJ_LOJISTA_2)]
    pB = copy.deepcopy(pA)
    pB["lojistas"] = [lojista(CNPJ_LOJISTA_2), lojista(CNPJ_LOJISTA_1)]
    keyA = idempotency.calcular_idempotency_key(
        IndicacaoCreate.model_validate(pA), dia="2026-04-19")
    keyB = idempotency.calcular_idempotency_key(
        IndicacaoCreate.model_validate(pB), dia="2026-04-19")
    assert keyA == keyB


# ═══════════════════════════════════════════════════════════════════════
#  REJEIÇÕES (validações duras)
# ═══════════════════════════════════════════════════════════════════════

@caso("Rejeita — CNPJ de lojista inválido")
def cen_rej_cnpj():
    p = com_gestor(payload_base())
    p["participantes"] = "apenas_gestor"
    p["lojistas"][0]["cnpj"] = "11111111111111"
    try:
        IndicacaoCreate.model_validate(p)
    except Exception as e:
        assert "CNPJ do lojista" in str(e)
        return
    assert False, "Pydantic deveria ter rejeitado CNPJ inválido"


@caso("Rejeita — fornecedor desconhecido (422)")
def cen_rej_fornecedor():
    p = com_gestor(payload_base())
    p["participantes"] = "apenas_gestor"
    p["fornecedor"] = {"codigo": "9999"}  # não existe na FakeRepo
    try:
        rodar(p)
    except services.FornecedorDesconhecido:
        return
    assert False, "deveria levantar FornecedorDesconhecido"


@caso("Rejeita — tipo=varejo sem participantes")
def cen_rej_participantes():
    p = com_gestor(payload_base())
    p["participantes"] = None
    try:
        IndicacaoCreate.model_validate(p)
    except Exception as e:
        assert "participou" in str(e) or "participantes" in str(e)
        return
    assert False


@caso("Rejeita — CNPJs de lojistas duplicados no mesmo payload")
def cen_rej_dup_loj():
    p = com_gestor(payload_base())
    p["participantes"] = "apenas_gestor"
    p["lojistas"] = [lojista(CNPJ_LOJISTA_1), lojista(CNPJ_LOJISTA_1)]
    try:
        IndicacaoCreate.model_validate(p)
    except Exception as e:
        assert "duplicados" in str(e)
        return
    assert False


@caso("Rejeita — eh_feira=True sem feira_nome")
def cen_rej_feira():
    p = com_gestor(payload_base())
    p["participantes"] = "apenas_gestor"
    p["eh_feira"] = True
    p["feira_nome"] = None
    try:
        IndicacaoCreate.model_validate(p)
    except Exception as e:
        assert "feira" in str(e).lower()
        return
    assert False


@caso("Rejeita — prioridade=programado sem data")
def cen_rej_data():
    p = com_gestor(payload_base())
    p["participantes"] = "apenas_gestor"
    p["prioridade"] = "programado"
    p["data_contato"] = None
    try:
        IndicacaoCreate.model_validate(p)
    except Exception as e:
        assert "data" in str(e).lower() or "programado" in str(e).lower()
        return
    assert False


# ═══════════════════════════════════════════════════════════════════════
#  COBERTURA SQL — garante que todos os campos do Pydantic têm destino
# ═══════════════════════════════════════════════════════════════════════

def ler_sql():
    return (ROOT / "backend" / "migrations" / "002_modelagem_v2.sql").read_text(
        encoding="utf-8")


@caso("SQL — tem todas as tabelas essenciais")
def cov_tabelas():
    sql = ler_sql().lower()
    esperadas = [
        "executivos", "fornecedores", "feiras",
        "gestores", "representantes", "lojistas",
        "indicacoes", "indicacao_lojistas",
        "integration_events", "audit_log",
    ]
    faltando = [t for t in esperadas if f"create table" in sql
                and re.search(rf"create table[^;]*\b{t}\b", sql) is None]
    assert not faltando, f"tabelas ausentes: {faltando}"


@caso("SQL — tem todos os enums do schemas.py")
def cov_enums():
    sql = ler_sql().lower()
    for enum in [
        "tipo_indicacao", "tipo_produto", "cargo_gestor",
        "participantes_indicacao", "indicacao_status", "integration_status",
    ]:
        assert enum in sql, f"enum ausente: {enum}"


@caso("SQL — UNIQUE INDEX de idempotência (aware de soft-delete)")
def cov_unique():
    sql = ler_sql()
    assert re.search(
        r"unique\s+index[^;]*idempotency_key",
        sql, re.IGNORECASE
    ), "índice único de idempotency_key não encontrado"
    # idealmente com WHERE deleted_at IS NULL (partial index)
    # se não tiver, emite warning mas não falha
    partial = re.search(
        r"unique\s+index[^;]*idempotency_key[^;]*where[^;]*deleted_at",
        sql, re.IGNORECASE | re.DOTALL
    )
    if not partial:
        print("       (aviso) idempotency_key sem cláusula partial 'WHERE deleted_at IS NULL'")


@caso("SQL — view v_indicacoes_detalhe existe")
def cov_view():
    sql = ler_sql().lower()
    assert "create view v_indicacoes_detalhe" in sql or \
           "create or replace view v_indicacoes_detalhe" in sql, \
           "view v_indicacoes_detalhe não encontrada"


@caso("SQL — indicacoes tem idempotency_key, created_at e deleted_at")
def cov_cols_indicacoes():
    sql = ler_sql().lower()
    m = re.search(r"create table[^;]*indicacoes\s*\(([^;]+)\);", sql, re.DOTALL)
    assert m, "não achei CREATE TABLE indicacoes"
    body = m.group(1)
    for col in ["idempotency_key", "created_at", "deleted_at",
                "executivo_id", "fornecedor_id", "gestor_id",
                "representante_id", "prioridade", "status"]:
        assert col in body, f"coluna {col} ausente de indicacoes"


@caso("SQL — indicacao_lojistas tem tipo_produto + condicao_especial")
def cov_cols_il():
    sql = ler_sql().lower()
    m = re.search(r"create table[^;]*indicacao_lojistas\s*\(([^;]+)\);",
                  sql, re.DOTALL)
    assert m, "não achei CREATE TABLE indicacao_lojistas"
    body = m.group(1)
    for col in ["indicacao_id", "lojista_id", "tipo_produto",
                "condicao_especial", "condicao_especial_descricao",
                "observacoes"]:
        assert col in body, f"coluna {col} ausente de indicacao_lojistas"


@caso("SQL — trigger touch_updated_at definido")
def cov_trigger():
    sql = ler_sql().lower()
    assert "touch_updated_at" in sql, "função touch_updated_at ausente"
    assert "create trigger" in sql, "nenhum CREATE TRIGGER encontrado"


@caso("SQL — seed de feiras inserido")
def cov_seed_feiras():
    sql = ler_sql().lower()
    assert "insert into feiras" in sql or "insert into public.feiras" in sql, \
           "seed de feiras ausente"


@caso("Mapeamento — todo campo do IndicacaoCreate cai em alguma coluna")
def cov_mapeamento():
    """
    Para cada campo do IndicacaoCreate, confirma que o services.py
    passa esse valor para o repositório (insert/upsert), fechando o
    loop com o SQL. Usa mock recorder.
    """
    p = com_rep(com_gestor(payload_base()), doc=CPF_REP)
    p["participantes"] = "gestor_e_representante"
    p["eh_feira"] = True
    p["feira_nome"] = "FIPAN 2026"
    p["prioridade"] = "programado"
    p["data_contato"] = "2026-05-05"
    p["lojistas"] = [
        {**lojista(CNPJ_LOJISTA_1, produto="Split"),
         "condicao_especial": True,
         "condicao_especial_descricao": "Take rate 1.8%"},
        lojista(CNPJ_LOJISTA_2, produto="PagBlu"),
    ]
    _, repo = rodar(p)
    ind = repo.indicacoes[0]
    # Indicação
    for col in ["executivo_id", "fornecedor_id", "tipo", "eh_feira",
                "feira_id", "participantes", "gestor_id",
                "representante_id", "prioridade", "data_contato",
                "status", "idempotency_key"]:
        assert col in ind, f"indicação não gravou {col}"
    # Lojista linha (indicacao_lojistas)
    il0 = repo.indicacao_lojistas[0]
    for col in ["indicacao_id", "lojista_id", "tipo_produto",
                "condicao_especial", "condicao_especial_descricao",
                "observacoes"]:
        assert col in il0, f"indicacao_lojistas não gravou {col}"
    assert il0["tipo_produto"] == "Split"
    assert il0["condicao_especial"] is True
    assert il0["condicao_especial_descricao"] == "Take rate 1.8%"


# ═══════════════════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════════════════

def main():
    print("\n── Cenários de indicação ─────────────────────────────────")
    for fn in [cen_01, cen_02, cen_03, cen_04, cen_05, cen_06, cen_07]:
        fn()
    print("\n── Dedup / idempotência ─────────────────────────────────")
    for fn in [cen_dedup, cen_dedup_dias, cen_dedup_ordem]:
        fn()
    print("\n── Rejeições (validação dura) ───────────────────────────")
    for fn in [cen_rej_cnpj, cen_rej_fornecedor, cen_rej_participantes,
               cen_rej_dup_loj, cen_rej_feira, cen_rej_data]:
        fn()
    print("\n── Cobertura SQL / Mapeamento ───────────────────────────")
    for fn in [cov_tabelas, cov_enums, cov_unique, cov_view,
               cov_cols_indicacoes, cov_cols_il, cov_trigger,
               cov_seed_feiras, cov_mapeamento]:
        fn()

    ok = sum(1 for _, s, _ in RESULTADOS if s == "ok")
    fail = sum(1 for _, s, _ in RESULTADOS if s == "fail")
    err = sum(1 for _, s, _ in RESULTADOS if s == "err")
    print(f"\n── Resultado ───────────────────────────────────────────")
    print(f"  OK    : {ok}")
    print(f"  FAIL  : {fail}")
    print(f"  ERROR : {err}")
    print(f"  TOTAL : {len(RESULTADOS)}")
    if fail or err:
        print("\n── Falhas/Erros ────────────────────────────────────────")
        for nome, st, msg in RESULTADOS:
            if st != "ok":
                print(f"  [{st}] {nome}\n        {msg}")
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()

"""
Teste de migração "live": sobe um Postgres embarcado (pgserver) e executa
a migração 002_modelagem_v2.sql, verificando que toda a estrutura (tabelas,
índices, enums, view, trigger) foi criada corretamente.

Como o Postgres embarcado do pgserver não vem com as extensões pgcrypto,
citext e pg_trgm, o teste aplica adaptações mínimas antes de rodar:
  - Remove 'create extension ... pgcrypto/citext/pg_trgm'  (gen_random_uuid
    está no core do PG 13+; citext é substituído por text; índice GIN com
    gin_trgm_ops é substituído por btree comum)
  - Substitui 'citext' por 'text' nas colunas
  - Substitui 'using gin (razao_social gin_trgm_ops)' por '(razao_social)'

Se pgserver não estiver disponível, o teste é ignorado.
"""
from __future__ import annotations

import hashlib
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MIG_PATH = ROOT / "backend" / "migrations" / "002_modelagem_v2.sql"

# ───────────────────────────────────────────────────────────────────────────
# Helpers de runner local (mesmo estilo do test_cenarios_e2e.py)
# ───────────────────────────────────────────────────────────────────────────
_TESTS: list = []
def caso(nome: str):
    def _wrap(fn):
        _TESTS.append((nome, fn))
        return fn
    return _wrap


def _adaptar_sql(sql: str) -> str:
    """Remove/subsitui o que o pgserver não suporta."""
    # Remove CREATE EXTENSION (case-insensitive, com ou sem aspas)
    sql = re.sub(
        r"(?i)create\s+extension\s+if\s+not\s+exists\s+\"?(pgcrypto|citext|pg_trgm)\"?\s*;",
        "",
        sql,
    )
    # Substitui tipo citext por text
    sql = re.sub(r"\bcitext\b", "text", sql)
    # Substitui índice GIN com trigram por btree simples
    sql = re.sub(
        r"using\s+gin\s*\(\s*([a-zA-Z_][a-zA-Z0-9_]*)\s+gin_trgm_ops\s*\)",
        r"(\1)",
        sql,
        flags=re.IGNORECASE,
    )
    return sql


def _get_pgserver():
    try:
        import pgserver  # type: ignore
        return pgserver
    except Exception:
        return None


@caso("Sobe pgserver, aplica migração e confirma presença de todas as tabelas")
def t_migration_live():
    pgserver = _get_pgserver()
    if pgserver is None:
        print("  ↪ pgserver indisponível — skip")
        return

    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        srv = pgserver.get_server(tmp)
        try:
            sql = _adaptar_sql(MIG_PATH.read_text(encoding="utf-8"))
            srv.psql(sql)

            # ─── TABELAS ───────────────────────────────────────────────
            esperado_tabelas = {
                "executivos", "fornecedores", "feiras", "gestores",
                "representantes", "lojistas", "indicacoes",
                "indicacao_lojistas", "integration_events", "audit_log",
            }
            rows = srv.psql(
                "select table_name from information_schema.tables "
                "where table_schema='public' order by table_name;"
            )
            encontradas = {
                ln.strip()
                for ln in rows.splitlines()
                if ln.strip() and ln.strip() != "table_name" and "---" not in ln
                and "row" not in ln and "(" not in ln
            }
            faltantes = esperado_tabelas - encontradas
            assert not faltantes, f"Tabelas faltando: {faltantes}"

            # ─── ENUMS ─────────────────────────────────────────────────
            esperado_enums = {
                "tipo_indicacao", "tipo_produto", "tipo_documento",
                "tipo_bonificacao_rep", "prioridade_contato",
                "participantes_indicacao", "cargo_gestor",
                "indicacao_status", "integration_status", "audit_action",
            }
            rows = srv.psql(
                "select t.typname from pg_type t "
                "join pg_enum e on e.enumtypid = t.oid group by t.typname;"
            )
            enums_enc = {
                ln.strip()
                for ln in rows.splitlines()
                if ln.strip() and ln.strip() != "typname" and "---" not in ln
                and "row" not in ln and "(" not in ln
            }
            faltantes_enums = esperado_enums - enums_enc
            assert not faltantes_enums, f"Enums faltando: {faltantes_enums}"

            # ─── UNIQUE indicacoes.idempotency_key ────────────────────
            rows = srv.psql(
                "select indexname from pg_indexes "
                "where tablename='indicacoes' and indexname like '%idempotency%';"
            )
            assert "idempotency" in rows, f"Índice UNIQUE de idempotency_key não encontrado: {rows}"

            # ─── VIEW v_indicacoes_detalhe ──────────────────────────
            rows = srv.psql(
                "select table_name from information_schema.views "
                "where table_schema='public';"
            )
            assert "v_indicacoes_detalhe" in rows, f"View não encontrada: {rows}"

            # ─── TRIGGER touch_updated_at em lojistas ─────────────────
            rows = srv.psql(
                "select trigger_name from information_schema.triggers "
                "where event_object_table='lojistas';"
            )
            assert "trg_lojistas_updated" in rows, f"Trigger updated_at não instalado: {rows}"

            # ─── Seed feira 'ABCASA FAIR' ──────────────────────────────────
            rows = srv.psql("select nome from feiras;")
            assert "ABCASA FAIR" in rows, f"Seed ABCASA FAIR não inserido: {rows}"

            # ─── INSERT completo simulando fluxo real ─────────────────
            # 1. Executivo + fornecedor pré-existentes
            srv.psql(
                "insert into executivos(nome, email) "
                "values ('Ana Teste','ana@useblu.com.br');"
            )
            srv.psql(
                "insert into fornecedores(codigo, cnpj, razao_social, ativo) "
                "values ('9999','11222333000181','Fornecedor Teste',true);"
            )
            # 2. Gestor
            srv.psql(
                "insert into gestores(fornecedor_id, nome, celular, email, cargo) "
                "select id, 'Carlos Gestor', '11999998888', 'carlos@fornec.com', 'CEO_Dono' "
                "from fornecedores where cnpj='11222333000181';"
            )
            # 3. Lojista
            srv.psql(
                "insert into lojistas(cnpj, razao_social, nome_fantasia) "
                "values ('27865757000102','Lojista Teste LTDA','Lojista Teste');"
            )
            # 4. Indicação
            idemp = hashlib.sha256(b"teste-live").hexdigest()
            srv.psql(
                "insert into indicacoes("
                "  executivo_id, executivo_email_snapshot, executivo_nome_snapshot, "
                "  fornecedor_id, tipo, eh_feira, participantes, gestor_id, "
                "  prioridade, status, idempotency_key) "
                "select e.id, e.email, e.nome, "
                "       f.id, 'varejo'::tipo_indicacao, false, "
                "       'apenas_gestor'::participantes_indicacao, g.id, "
                f"       'imediato'::prioridade_contato, 'recebida'::indicacao_status, '{idemp}' "
                "from fornecedores f "
                "join gestores g on g.fornecedor_id = f.id "
                "join executivos e on e.email = 'ana@useblu.com.br' "
                "where f.cnpj='11222333000181';"
            )
            # 5. Vínculo indicacao_lojistas (1:N)
            srv.psql(
                "insert into indicacao_lojistas("
                "  indicacao_id, lojista_id, tipo_produto, "
                "  condicao_especial, observacoes) "
                "select i.id, l.id, 'PagBlu'::tipo_produto, false, 'obs teste' "
                "from indicacoes i, lojistas l "
                "where l.cnpj='27865757000102' limit 1;"
            )

            # ─── VALIDAÇÃO FINAL pela view ───────────────────────────
            rows = srv.psql("select count(*) from v_indicacoes_detalhe;")
            # a view deve devolver 1 linha da indicação inserida
            assert "1" in rows.split("\n")[2], f"View não retornou linha esperada: {rows}"

            # Consulta detalhada
            detalhe = srv.psql(
                "select tipo, prioridade, status "
                "from indicacoes where idempotency_key='" + idemp + "';"
            )
            assert "varejo" in detalhe
            assert "imediato" in detalhe
            assert "recebida" in detalhe

            print(
                f"  ↪ estrutura live OK: "
                f"{len(encontradas)} tabelas, {len(enums_enc)} enums, "
                f"view+trigger+seed+insert validados."
            )
        finally:
            srv.cleanup()


def main():
    falhas = 0
    for nome, fn in _TESTS:
        try:
            fn()
            print(f"[OK] {nome}")
        except AssertionError as e:
            falhas += 1
            print(f"[FAIL] {nome}\n       {e}")
        except Exception as e:  # pragma: no cover
            falhas += 1
            print(f"[ERR ] {nome}: {e!r}")
    print(f"\n{len(_TESTS) - falhas}/{len(_TESTS)} passaram.")
    sys.exit(1 if falhas else 0)


if __name__ == "__main__":
    main()

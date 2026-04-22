# Blu Engajamento Comercial — Pipe de Conexões (v2, Python)

Backend + frontend para substituir os fluxos n8n que alimentam a
LP de indicações de varejo da Blu. Source-of-truth em **Supabase**;
HubSpot e Excel viram *sinks* assíncronos.

## Documentação

- [`docs/fluxo_atual.md`](docs/fluxo_atual.md) — ponta-a-ponta do fluxo em produção + problemas identificados.
- [`docs/modelagem_supabase_v2.md`](docs/modelagem_supabase_v2.md) — racional da modelagem de dados.
- [`backend/migrations/002_modelagem_v2.sql`](backend/migrations/002_modelagem_v2.sql) — DDL do schema novo.

## Estrutura

```
backend/
  main.py                 ← FastAPI app + rotas
  schemas.py              ← Pydantic v2 (payload da LP, alinhado à prod)
  validators.py           ← CNPJ/CPF (módulo 11)
  idempotency.py          ← chave determinística p/ dedup
  database.py             ← cliente Supabase
  repositories.py         ← única camada que fala com Postgres
  services.py             ← regras de negócio (orquestra repositórios)
  integrations/
    hubspot/              ← client / hubdb / crm / sync  (STUBS)
    sinks/                ← excel / s3_parquet           (STUBS)
  migrations/
    001_criar_tabela.sql  ← legado v1 (CSV em célula)
    002_modelagem_v2.sql  ← modelagem 3NF + auditoria + idempotência
frontend/
  index.html, painel.html, js/  ← LP original do MVP (ainda v1; próximo passo)
docs/
  fluxo_atual.md
  modelagem_supabase_v2.md
```

## Setup

```bash
cp .env.example .env            # preencha SUPABASE_URL / SUPABASE_KEY
cd backend
pip install -r requirements.txt
# Aplicar a migration v2 no Supabase:
# Dashboard → SQL Editor → colar backend/migrations/002_modelagem_v2.sql
uvicorn backend.main:app --reload
```

Endpoints:

- `GET  /health` — ping banco.
- `POST /indicacoes` — recebe payload da LP; dedup idempotente; enfileira integrações.
- `GET  /indicacoes` — lista do painel (view `v_indicacoes_detalhe`).

## Problemas resolvidos (vs. fluxo n8n atual)

| Problema original | Solução na v2 |
|---|---|
| **Duplicidade** | `idempotency_key` (SHA-256 de fornecedor+participantes+lojistas+dia) com `UNIQUE INDEX`. |
| **Datas em formatos errados** | Tudo `timestamptz` em UTC + serialização ISO-8601. |
| **Sem chave única** | UUIDs + `external_refs` JSONB com `hubspot_*_id`, `n8n_execution_id`, `excel_row_id`. |
| **Data perguntada ao usuário** | Removida do payload. `created_at default now()`. |
| **Só grava em Excel + HubSpot** | Supabase virou source-of-truth. Excel/HubSpot/S3 viram sinks alimentados por `integration_events`. |

## Integração HubSpot — plug-and-play

A integração **não está ligada** (premissa do ciclo atual). O esqueleto em `backend/integrations/hubspot/` define contratos claros (`HubSpotClient`, `HubDBLookup`, `HubSpotCRM`, `sync_indicacao_to_hubspot`) com `NotImplementedError`. Para ativar:

1. Gerar Private App token com escopos `hubdb`, `crm.objects.contacts/companies/deals` (read+write).
2. Setar `HUBSPOT_PRIVATE_APP_TOKEN` no `.env`.
3. Preencher os métodos dos stubs (httpx já está nas deps).
4. Ligar um worker que consome `integration_events` e chama `sync_indicacao_to_hubspot`.

Nenhuma alteração é necessária no endpoint `POST /indicacoes`.

## Pendências do usuário (para evoluir)

- [ ] Exportar JSON dos dois workflows n8n para `docs/n8n/`:
  - `8BTetzXoOZ15feAk` — indicação varejo.
  - `ln9tTinqjLLjkLJB` — criação de negócio no pipe Conexões.
- [ ] Dump das colunas dos HubDBs `116939574` e `27538329` para `docs/hubspot/`.
- [ ] Decidir se o `frontend/` atual (MVP simples) será substituído pela LP real em produção ou se vamos manter a LP em HubSpot CMS e só trocar o webhook do n8n pela nossa API.

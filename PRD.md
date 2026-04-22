# Product Requirements Document — Blu Engajamento Comercial (Conexões v2)

> Documento ampliado após a leitura da documentação oficial do wiki
> (ver `.claude/wiki_oficial.md`). Substitui a versão MVP de 3 sprints.

## Overview

Plataforma interna para captura e roteamento de **indicações de varejo**
recebidas de indústrias parceiras da Blu. Substitui os 4 workflows n8n
atuais por uma stack Python (FastAPI) com **Supabase como source-of-truth**,
mantendo HubSpot CRM, HubDBs e planilha Excel como **sinks** assíncronos.

O produto é o Pipe de Conexões: converter pagamentos via boleto para
PagBlu, usando recebíveis futuros de cartão de crédito na POS da Blu.

## Problem Statement

Os 4 workflows n8n hoje em produção sofrem com:

1. **Duplicidade** de indicações (sem chave idempotente).
2. **Datas em formatos inconsistentes** (fuso não normalizado).
3. **Ausência de chave única estável** entre Excel, HubSpot e backend.
4. **Data de contato pedida ao usuário**, em vez de `now()`.
5. **Sem banco relacional** — só Excel + HubSpot, sem rastreabilidade.
6. **Resolução de UF frágil** (quando BrasilAPI falha, roteamento fica ao léu).
7. **Owner atribuído manualmente**, inconsistente entre executivos.
8. **"Alto Potencial" subjetivo**, sem regra formal.

## Goals & Success Metrics

- **Zero duplicatas** em produção (idempotency_key único).
- **100% das indicações** com timestamp ISO-8601 UTC.
- **Latência p95 do webhook < 800 ms**, mesmo com sinks assíncronos.
- **Roteamento automático** de owner em ≥ 95% dos casos (regionalização).
- **Rastreabilidade completa**: toda linha do Excel e todo Deal do HubSpot
  apontam de volta para um `indicacoes.id` do Supabase.
- **Auditoria**: 100% das mutações registradas em `audit_log`.

## Target Users

- **Executivos Comerciais da Blu** — preenchem a LP no mobile/notebook.
- **RevOps / Admin** — usam WF2 (Cadastro REP/Gestor) e painel de listagem.
- **Pipeline Managers** — consomem o pipeline "Conexões" no HubSpot.

## Scope

### In Scope (produto completo)

1. **Formulário público** em `https://blu.com.br/conexoes-indicacao-varejo`
   com os 5 tipos de indicação, lojistas dinâmicos, feira, prioridade.
2. **Endpoint `POST /indicacoes`** com idempotência SHA-256, validação
   fiscal (CNPJ/CPF módulo 11), enfileiramento de sinks.
3. **Persistência em Supabase** no modelo 3NF (10 tabelas) com
   soft-delete, triggers `touch_updated_at`, RLS, view agregada.
4. **Resolução automática de UF** (BrasilAPI → DDD → `INDEFINIDO`).
5. **Regionalização** (UF → owner via tabela de configuração).
6. **Classificação Alto Potencial** (VIP + produto + faturamento).
7. **Integração HubSpot plug-and-play** (4 workflows como serviços Python).
8. **Notificação Teams** em falhas críticas.
9. **Sink Excel** append-only para backup offline.
10. **Painel interno** (HTML) com filtros, busca e export CSV.
11. **Observabilidade** (logs JSON estruturados + métricas).
12. **Segurança** (CORS allowlist, rate limit, headers bloqueados, RLS).

### Out of Scope (por enquanto)

- App mobile nativo.
- Dashboard BI (Metabase/Looker ficam em projeto separado).
- Aprovação multi-nível de indicação.
- Integração com ERP das indústrias.

## Arquitetura

```
┌────────────────┐   POST /indicacoes   ┌─────────────────────────┐
│   LP Conexões  │ ────────────────────▶│  FastAPI (backend)      │
│ (Tailwind +    │                      │  ├─ schemas Pydantic    │
│  Alpine.js)    │                      │  ├─ idempotency_key      │
└────────────────┘                      │  ├─ services (regras)    │
                                        │  └─ repositories (SB)    │
                                        └────────────┬────────────┘
                                                     │
                                                     ▼
                                        ┌─────────────────────────┐
                                        │   Supabase (Postgres)   │
                                        │   source-of-truth        │
                                        │   + integration_events   │
                                        └────────────┬────────────┘
                                                     │ workers async
                                 ┌───────────────────┼───────────────────┐
                                 ▼                   ▼                   ▼
                        ┌───────────────┐  ┌───────────────┐  ┌───────────────┐
                        │ WF1/WF2/WF3   │  │ Excel (sink)  │  │ S3 / BrasilAPI│
                        │ HubSpot CRM   │  │ append-only   │  │ enriquecimento│
                        └───────────────┘  └───────────────┘  └───────────────┘
```

## Os 4 Workflows (espelho dos workflows n8n)

| # | Workflow | Trigger | Descrição |
|---|---|---|---|
| **WF1** | Indicação Varejo | `POST /indicacoes` | Valida fornecedor + executivo, cria/atualiza GES/REP/Lojista, enfileira WF3. |
| **WF2** | Cadastro REP/Gestor | `POST /admin/rep` e `POST /admin/ges` | Uso administrativo; cria custom objects sem criar Deal. |
| **WF3** | Criação de Negócios | Event bus interno | Para cada lojista: resolve UF → cenário 1..6 → regionaliza → Alto Potencial → cria Deal + associações. |
| **WF4** | Consulta REP/Gestor | `GET /admin/rep?q=` | Read-only para autocompletar formulários internos. |

## Tipos de Indicação (5 cenários)

| Cenário | `participantes` | Gestor? | REP? | Executivo Blu? |
|---|---|---|---|---|
| 1 | `apenas_gestor` | ✔︎ | — | — |
| 2 | `gestor_e_representante` | ✔︎ | ✔︎ | — |
| 3 | `gestor_e_vendas_interno` | ✔︎ | — | ✔︎ |
| 4 | `apenas_representante` | — | ✔︎ | — |
| 5 | `direta` | — | — | ✔︎ |

Flag ortogonal `eh_feira=true` adiciona `feira_nome` e roteamento para
pool de feiras.

## Functional Requirements

### FR-01: Formulário público (LP Conexões)

**Descrição:** Substitui a LP n8n, mantendo domínio `blu.com.br`.
Stack: HTML5 + Tailwind + Alpine.js, Inter font, paleta Blu.

**Seções:**

1. **Identificação** — executivo (nome+email), fornecedor (autocomplete
   a partir do `GET /fornecedores`), tipo (`varejo`/`representante`),
   feira (sim/não + select de `GET /feiras`).
2. **Participantes** (só quando `tipo=varejo`) — radio de composição
   (5 opções), dados do GES e/ou REP conforme composição, prioridade
   (`imediato`/`programado` + data condicional).
3. **Lojistas** — array dinâmico (1–50); cada item tem CNPJ, razão social,
   nome fantasia, e-mail, WhatsApp, `tipo_produto` (PagBlu/CredBlu/Split),
   condição especial (bool + descrição) e observações.

**Acceptance Criteria:**

- [ ] CNPJ/CPF validados em tempo real (módulo 11) com feedback inline.
- [ ] Detecção automática CPF vs CNPJ pelo número de dígitos.
- [ ] Progressive disclosure: seção 2 só aparece em `tipo=varejo`;
      `feira_nome` só aparece se `eh_feira=true`; `data_contato` só em
      `prioridade=programado`.
- [ ] Fornecedor e feiras vêm de endpoints (não hard-coded).
- [ ] Submit bloqueado se houver qualquer erro de validação.
- [ ] Toast de sucesso, erro ou dedup (duplicada) após POST.
- [ ] Layout responsivo 375 px – 1440 px.

### FR-02: Endpoint `POST /indicacoes`

**Descrição:** Recebe payload v2, persiste no Supabase, calcula
`idempotency_key` e enfileira sinks.

**Acceptance Criteria:**

- [ ] Payload validado por Pydantic v2 (`IndicacaoCreate`).
- [ ] `idempotency_key = sha256(fornecedor + participantes + lojistas + dia BR)`.
- [ ] Se chave já existir (not deleted), retorna 201 com `duplicada=true`
      (idempotente, não cria registro novo).
- [ ] Upsert cascata: `executivos`, `gestores`, `representantes`, `lojistas`.
- [ ] `created_at = now()` (nunca do payload).
- [ ] Enfileira `integration_events` para os workflows ativos.
- [ ] Retorna p95 < 800 ms.

### FR-03: Resolução automática de UF

**Descrição:** Derivar UF do lojista sem depender de input manual.

**Acceptance Criteria:**

- [ ] 1ª tentativa: `GET brasilapi.com.br/api/cnpj/v1/{cnpj}` (timeout 3 s).
- [ ] 2ª tentativa: DDD do WhatsApp → UF (tabela fixa 88 DDDs).
- [ ] Se falhar, grava `INDEFINIDO` e loga alerta.
- [ ] `uf_resolvida` é persistida em `lojistas.uf` e propagada ao Deal.

### FR-04: Regionalização

**Descrição:** UF → owner do CRM via tabela de configuração
`owners_regionalizacao` (UF text PK, owner_id uuid).

**Acceptance Criteria:**

- [ ] Consulta direta à tabela (cache em memória de 5 min).
- [ ] Fallback para `supervisor geral` quando UF = `INDEFINIDO`.
- [ ] Owner registrado no Deal criado no HubSpot.

### FR-05: Classificação Alto Potencial

**Descrição:** Lojista é `alto_potencial=true` se:
(a) CNPJ na tabela `lojistas_vip`, OU (b) `tipo_produto = Split`,
OU (c) `faturamento_anual > 50_000_000` (quando informado).

**Acceptance Criteria:**

- [ ] Determinado no serviço antes de criar o Deal.
- [ ] Propagado à property `alto_potencial` da company e do Deal.
- [ ] Campo consultável no painel.

### FR-06: WF1 — Indicação Varejo (HubSpot)

Criar/atualizar GES (contato), REP (custom object), Lojista (company);
associar GES ↔ Fornecedor, REP ↔ Fornecedor, Lojista ↔ Fornecedor,
Lojista ↔ GES, Lojista ↔ REP conforme cenário.

### FR-07: WF2 — Cadastro REP/Gestor

Endpoints administrativos `POST /admin/ges` e `POST /admin/rep` para
criar contatos/custom objects fora do fluxo da LP.

### FR-08: WF3 — Criação de Negócios

Para cada lojista, criar Deal no pipeline "Conexões", aplicando cenário
1..6 (tabela em `.claude/wiki_oficial.md` §5.2), regionalização,
Alto Potencial e as 11 associações.

### FR-09: WF4 — Consulta REP/Gestor

`GET /admin/rep?q=` e `GET /admin/ges?q=` com busca parcial (nome,
documento, e-mail) — read-only, cache 5 min.

### FR-10: Sinks assíncronos

Worker consome `integration_events` (status=pending) e publica em:

- HubSpot CRM (WF1 + WF3).
- Excel (append-only com `indicacao_id` em toda linha).
- S3 Parquet (futuro; stub pronto).

### FR-11: Painel interno `/painel.html`

Tabela + busca + filtros (executivo, fornecedor, UF, prioridade,
alto_potencial); export CSV respeita filtros.

### FR-12: Segurança

- CORS allowlist configurável via env.
- Rejeitar headers com CRLF ou `Host`/`Origin` inesperados.
- Rate limit (30 req/min por IP no endpoint público).
- Supabase RLS habilitado; backend usa service_role.
- Segredos apenas em `.env`.

### FR-13: Notificação Teams

Falhas 5xx, HubSpot 5xx, e qualquer `integration_event` com 3 retries
falhos disparam mensagem no canal "Conexões – Alertas".

### FR-14: Observabilidade

- Log JSON estruturado com `indicacao_id`, `idempotency_key`,
  `workflow`, `step`, `duration_ms`, `status`.
- Métricas: indicações/dia, % dedup, % Alto Potencial, latência p95,
  taxa de sucesso por workflow.
- `audit_log` registra diff before/after de qualquer mutação.

## Non-Functional Requirements

- **Performance:** `POST /indicacoes` p95 < 800 ms (sem sinks síncronos).
- **Segurança:** HTTPS only, secrets em env, RLS, CORS allowlist.
- **Disponibilidade:** retry exponencial 3x em sinks; se HubSpot cair,
  indicação ainda é persistida.
- **Compliance:** LGPD — auditoria completa, soft-delete, TTL configurável
  para `audit_log` (180 dias) e `integration_events` (30 dias).
- **Manutenibilidade:** tipagem estrita (Pydantic v2, mypy), separação
  schemas/services/repositories/integrations.

## Tech Stack

- **Frontend:** HTML5 + Tailwind (CDN) + Alpine.js (CDN) + Inter.
- **Backend:** Python 3.11 / FastAPI / Uvicorn.
- **Banco:** Supabase (Postgres 15) via `supabase-py`.
- **HTTP client:** `httpx[http2]`.
- **HubSpot:** Private App token (env) + API v3.
- **Integração externa:** BrasilAPI (CNPJ).
- **Notificações:** Microsoft Teams Incoming Webhook.
- **CI/CD:** a definir (GitHub Actions preferido).
- **Hosting:** backend em Railway/Render; LP no HubSpot CMS (ou Netlify).

## Sprint Plan Summary (9 sprints)

| Sprint | Tema | Duração |
|---|---|---|
| 1 | Infraestrutura + modelo de dados v2 | 1 semana |
| 2 | Backend API completo (idempotência, upserts, UF) | 1 semana |
| 3 | Frontend v2 (LP Conexões) alinhado ao schema real | 1 semana |
| 4 | HubSpot WF4 — Consulta REP/Gestor (read-only) | 1 semana |
| 5 | HubSpot WF2 — Cadastro REP/Gestor (admin) | 1 semana |
| 6 | HubSpot WF1 — Indicação Varejo (orquestrador) | 1 semana |
| 7 | HubSpot WF3 — Criação de Deals (cenários 1..6) | 1 semana |
| 8 | Segurança + Teams + Excel + Rate limit | 1 semana |
| 9 | Observabilidade + carga + rollout gradual | 1 semana |

Detalhamento por tarefa em `spec.json`.

## Risks & Mitigations

| Risco | Impacto | Mitigação |
|---|---|---|
| Wiki oficial incompleto (typeIds) | Alto — bloqueia WF3 | Stubs carregam typeIds do env; tarefa P1 para extrair. |
| BrasilAPI instável | Médio — UF indefinida | Fallback DDD; `INDEFINIDO` roteia para supervisor. |
| Volume inesperado | Médio — latência | Idempotência + worker assíncrono + rate limit. |
| HubSpot 5xx em bulk | Alto — perda de sync | Queue com retry exponencial + Teams alert. |
| LGPD | Alto — exposição | Soft-delete + TTL + RLS + audit_log. |

## Open Questions

- [ ] Onde hospedar o backend (Railway vs Render vs interno Blu)?
- [ ] Webhook Teams do canal "Conexões – Alertas" está liberado?
- [ ] TypeIds das 11 associações — Caio consegue extrair do portal HubSpot?
- [ ] Lista VIP de CNPJs para regra de Alto Potencial — onde vive hoje?
- [ ] Mapa UF → owner definitivo (hoje está em HubDB? em planilha?).
- [ ] O painel interno fica em `blu.com.br/conexoes-painel` ou em
      subdomínio separado com auth SSO?

# Fluxo atual — LP Conexões / Indicação Varejo

> **Objetivo deste doc:** registrar ponta a ponta como o sistema *em produção* funciona
> (LP + n8n + HubSpot + Excel) para que a reimplementação em Python/FastAPI/Supabase
> possa preservar a lógica de negócio e corrigir os problemas identificados.
>
> Fontes:
>
> 1. LP pública `https://blu.com.br/conexoes-indicacao-varejo-n8n` (scraping HTML).
> 2. Repositório atual (MVP escafoldado em `backend/` e `frontend/`).
> 3. PRD (`PRD.md`) e spec de sprints (`spec.json`).
> 4. **Pendente:** export JSON dos fluxos n8n — `8BTetzXoOZ15feAk`
>    (indicação varejo) e `ln9tTinqjLLjkLJB` (criação de negócio no pipe de conexões).
>    Partes marcadas `⚠️ n8n` dependem desses exports para virar fiel ao produção.

---

## 1. Atores e sistemas

| Ator / sistema | Papel |
|---|---|
| **Executivo Blu** | Preenche a LP com uma indicação recebida da indústria. |
| **LP (HubSpot CMS)** | Formulário web multi-seção com validações de frontend. |
| **HubDB 116939574** — *Usuários HubSpot (Inscrito por)* | Catálogo de executivos Blu (lookup). |
| **HubDB 27538329** — *Fornecedores* | Catálogo de indústrias parceiras (código + razão social + CNPJ). |
| **n8n `8BTetzXoOZ15feAk`** — *Fluxo de indicação varejo* | Webhook que recebe o payload da LP, valida, faz lookups e dispara sub-fluxos. |
| **n8n `ln9tTinqjLLjkLJB`** — *Fluxo de criação de negócio* | Cria contatos, empresas e deals no HubSpot ("pipe de conexões"). |
| **Planilha Excel** — `[Conexões] Registro de Indicações.xlsx` | Log histórico manualmente acessível. |
| **HubSpot CRM** | Destino final: contacts, companies, deals. |

---

## 2. Estrutura completa do formulário em produção

Extraído do HTML da LP. Os campos marcados com **\*** são obrigatórios.

### 2.1 Cabeçalho do envio

| Campo | Tipo | Observação |
|---|---|---|
| **Inscrito por** | Lookup HubDB `116939574` | Executivo Blu autenticado / selecionado. |
| **Fornecedor\*** | Lookup HubDB `27538329` | Exibe `CÓDIGO - RAZÃO SOCIAL - CNPJ`. |
| **O que deseja indicar?\*** | Radio | `Indicar Varejo` / `Indicar Representante`. |
| **Indicação Feira?\*** | Radio | `Sim` / `Não`. |
| **Nome da feira\*** | Dropdown (condicional) | Catálogo fixo: ABCASA FAIR, ABF EXPO, ABIMAD, ABIÓPTICA, ABUP SHOW, AJORSUL BUSINESS, AJORSUL FAIR MERCOÓPTICA, BCONECTED, CAMILOTO SHOW ROOM, ELETROLARSHOW, EQUIPOTEL, EVENTO CBC, EVENTO SIMM FEST, EVENTO SINDIMOL, EVENTO VIXLENS, EXPO AJU MOVEIS, EXPO BAHIA MÓVEIS, EXPO MÓVEL (CARUARU / FORTALEZA / GOIAS / NORDESTE / SÃO LUÍS), EXPO SUDOESTE, EXPO VALE (PETROLINA), EXPOVISÃO, FAIR HOUSE (MS / PR / SC), FEIRA MUNDO BIKE, FEBRATEX, FEMOJ, FEMOPE, FEMUR, FENÓPTICA, FERCAM, FIMEC, FORMOBILE, GOTEX SHOW, INTERPLAST, LAAD DEFENCE E SECURITY, LA MODA EXPERIENCE, MERCOMÓVEIS, MÓVEL BRASIL, MOVELPAR, MOVELSUL BRASIL, MOVERGS, PESCA E CIA TRADE SHOW, RIO MÓVEIS / CABO FRIO, SALÃO DE GRAMADO, SALÃO MÓVEL PB, SHIMANO FEST, SHOT FAIR BRASIL, UBÁ SHOWROOM HORTO, UBÁ SHOWROOM TABAJARA, VAREJO EXPERIENCE, YES MÓVEL SHOW (CAMPINAS / GOIAS) etc. |

### 2.2 Participantes da indicação (quando `Indicar Varejo`)

| Campo | Tipo | Observação |
|---|---|---|
| **Quem participou?\*** | Radio | `Apenas o gestor da indústria` · `Gestor e representante` · `Gestor e time de vendas interno` · `Apenas o representante` · `Indicação direta (sem gestor nem representante)`. |
| **Email do Gestor\*** | Texto + botão `Buscar Gestor` | Lookup no HubSpot; abre modal de cadastro se não existir. |
| **CPF/CNPJ do REP\*** | Texto + botão `Buscar REP` | Lookup no HubSpot; abre modal de cadastro se não existir. |

**Modal `Cadastro do Gestor`:** Nome, Email, Celular, Cargo
(CEO/Dono, Diretor Financeiro, Gerente Financeiro, Supervisor Financeiro,
Analista Financeiro, Diretor Comercial, Gerente Comercial,
Supervisor Comercial, Analista Comercial, Outros).

**Modal `Cadastro do REP`:** CPF/CNPJ, Nome, Email, Celular,
Tipo de Bonificação (`RPA` / `Nota Fiscal`), Principal Fornecedor (lookup).

### 2.3 Priorização e agendamento

| Campo | Tipo | Observação |
|---|---|---|
| **Prioridade de Contato\*** | Radio | `Imediato` / `Programado`. |
| **Data para contato\*** | Data (condicional) | Só se `Programado`. **Problema identificado:** a data de *cadastro* da indicação também é perguntada ao usuário — deveria ser gerada automaticamente pelo backend. |

### 2.4 Dados do lojista (repetível — "+ um cadastro de CNPJ")

Cada bloco = 1 lojista indicado. Botão `Remover` por bloco.

| Campo | Tipo | Validação |
|---|---|---|
| **CNPJ do lojista\*** | Texto | 14 dígitos + módulo 11. |
| **Nome fantasia\*** | Texto | Obrigatório. |
| **Nome do lojista (razão social)\*** | Texto | Obrigatório. |
| **Email do lojista\*** | Email | Formato válido. |
| **WhatsApp do lojista\*** | Telefone | Formato válido. |
| **Tipo de produto indicado\*** | Dropdown | `PagBlu` / `CredBlu` / `Split`. |
| **Foi negociada condição especial?\*** | Radio | `Não` / `Sim` → libera textarea (≤ 1000 chars). |
| **Observações** | Textarea opcional | ≤ 1000 chars. |

### 2.5 Ações

- `Enviar CNPJ(s)` — envia a indicação atual (todos os lojistas já preenchidos).
- `Fazer envio para outro fornecedor` — resubmete mantendo parte do contexto.

---

## 3. Fluxo operacional (inferido)

```
┌──────────────┐      POST JSON       ┌───────────────────────────┐
│   LP / HTML  │ ───────────────────▶ │  n8n Webhook (varejo)      │
│   validação  │                      │  8BTetzXoOZ15feAk          │
│   frontend   │                      │                            │
└──────────────┘                      │  1. Normaliza payload      │
                                      │  2. Valida CNPJ/CPF        │
                                      │  3. Lookup Inscrito por    │
                                      │     (HubDB 116939574)      │
                                      │  4. Lookup Fornecedor      │
                                      │     (HubDB 27538329)       │
                                      │  5. Para cada lojista:     │
                                      │     dispara sub-workflow   │
                                      │     de criação de negócio  │
                                      └──────────┬─────────────────┘
                                                 │
                                                 ▼
                                ┌────────────────────────────────┐
                                │ n8n "criação de negócio"       │
                                │ ln9tTinqjLLjkLJB               │
                                │                                 │
                                │ a) Procura/Cria Contact         │
                                │    (gestor, rep, lojista)       │
                                │ b) Procura/Cria Company         │
                                │    (indústria + lojista)        │
                                │ c) Cria Deal no pipe "Conexões" │
                                │ d) Associa Contact↔Company↔Deal │
                                │ e) Append linha no Excel        │
                                │    [Conexões] Registro de       │
                                │    Indicações.xlsx              │
                                └────────────────────────────────┘
```

> ⚠️ **Pendente:** passos exatos 1–5 e a–e serão validados quando os
> JSON dos workflows forem importados para `docs/n8n/`.

---

## 4. Problemas identificados (a corrigir na versão Python)

| # | Problema | Causa raiz inferida | Solução na v2 |
|---|---|---|---|
| **P1** | **Duplicidade de indicações** | Sem chave natural única; retries do usuário e do n8n recriam deal/contato. | Chave natural `(cnpj_industria, doc_representante, cnpj_lojista, data_truncada_dia)` + hash SHA-256 em coluna `idempotency_key` com `UNIQUE INDEX`. Toda indicação passa por `ON CONFLICT DO NOTHING`. |
| **P2** | **Datas em formatos errados** | Excel trata datas como string; timezones inconsistentes; n8n usa formato local do container. | Todas as datas em `timestamptz` no Postgres; serialização ISO-8601 UTC no JSON; nunca perguntar ao usuário a data de cadastro. |
| **P3** | **Sem chave única** | Tabela de destino (Excel) não tem PK; HubSpot usa internalId, mas a correlação entre sistemas não persiste. | `id uuid` no Supabase + `external_refs` JSONB guardando `hubspot_contact_id`, `hubspot_company_id`, `hubspot_deal_id`, `n8n_execution_id`. |
| **P4** | **Data de cadastro perguntada ao usuário** | Campo do form. | Removido do form. `created_at timestamptz default now()` no banco. |
| **P5** | **Persistência só em Excel + HubSpot** | Não há source-of-truth transacional. | Supabase (Postgres) vira source-of-truth. HubSpot e Excel (ou S3/Parquet futuro) são *sinks* secundários alimentados por jobs assíncronos. |
| **P6** | **Falhas silenciosas de integração** | n8n não reprocessa nem alerta quando HubSpot devolve erro. | Tabela `integration_events` com status `pending/sent/failed/skipped` + retries com backoff + alerta em falha definitiva. |
| **P7** | **Rastreabilidade fraca** | Não dá para auditar "o que aconteceu com a indicação X". | Tabela `audit_log` (quem, quando, qual mudança) + `request_id` propagado em todas as chamadas. |
| **P8** | **Modelo 1ª forma violada** (MVP atual) | Campo `cnpjs_varejistas` armazena CSV em uma célula. | Tabela separada `indicacao_lojistas` + `lojistas` (master data). |

---

## 5. Dependências externas a destravar

- [ ] Export JSON de `8BTetzXoOZ15feAk` → `docs/n8n/indicacao_varejo.json`.
- [ ] Export JSON de `ln9tTinqjLLjkLJB` → `docs/n8n/criacao_negocio.json`.
- [ ] Dump das colunas dos HubDBs (116939574 e 27538329) → `docs/hubspot/hubdb_schemas.md`.
- [ ] Token de HubSpot Private App no `.env` como `HUBSPOT_PRIVATE_APP_TOKEN` (quando for hora de ligar a integração).
- [ ] Credenciais Supabase já estão em `.env` ✅.

---

## 6. Escopo da v2 (ordem de entrega)

1. **Modelagem Supabase v2** (Sprint 1) — este commit.
2. **Backend refatorado** com dedup, timestamps auto, integrações stubadas (Sprint 2).
3. **Frontend** alinhado aos campos reais da LP em produção (Sprint 3).
4. **Integração HubSpot** real (HubDB lookups + CRM create) + *sink* Excel/S3 (Sprint 4).
5. **Observabilidade** (logs estruturados, métricas, alertas de falha) (Sprint 5).

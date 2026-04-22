# Contexto Oficial — LP Conexões (Wiki + Workflows n8n/HubSpot)

> Fonte-de-verdade consolidada da operação atual (n8n + HubSpot) para
> referência durante TODA a migração para Python/FastAPI + Supabase.
> Preservar literalmente — base para spec.json, PRD.md e implementação.

---

## 1. Panorama

- **LP pública:** `https://blu.com.br/conexoes-indicacao-varejo-n8n`
  (ainda em produção, hospedada no HubSpot CMS).
- **Backend atual:** 4 workflows n8n + HubDBs + HubSpot CRM + planilha Excel.
- **Objetivo da migração:** substituir os workflows n8n por FastAPI +
  Supabase, mantendo HubSpot como sink plug-and-play.

### Atores

| Ator | Descrição | Identificação |
|---|---|---|
| **Executivo Blu** | Quem preenche a LP; exerce papel de owner de indicação. | Nome + e-mail corporativo (ativo na HubDB de executivos). |
| **Indústria / Fornecedor** | Empresa parceira indicando um varejo. | Código interno (ex.: "0010") + CNPJ — HubDB de fornecedores. |
| **Gestor da Indústria (GES)** | Contato (diretor/gerente) da indústria. | Nome, e-mail, cargo, celular. |
| **Representante (REP)** | Representante comercial externo da indústria. | Nome, CPF ou CNPJ, bonificação (RPA / Nota Fiscal). |
| **Lojista (Varejo)** | Empresa alvo do engajamento. | CNPJ, razão social, nome fantasia, e-mail, WhatsApp. |

---

## 2. Os 4 Workflows atuais

| # | Workflow n8n | Função |
|---|---|---|
| 1 | **Indicação Varejo** (`8BTetzXoOZ15feAk`) | Webhook da LP → valida fornecedor/executivo → cria/atualiza GES/REP/Lojista no CRM → dispara WF3. |
| 2 | **Cadastro REP/Gestor** (interno) | Cria/atualiza contatos e custom objects (REP/GES) fora da indicação (uso administrativo). |
| 3 | **Criação de Negócios** (`ln9tTinqjLLjkLJB`) | Para cada lojista da indicação: cria Deal no pipeline "Conexões" aplicando cenário + regionalização + Alto Potencial. |
| 4 | **Consulta REP/Gestor** (read-only) | Endpoint auxiliar de busca para autocompletar formulários internos. |

---

## 3. Tipos de Indicação

Cinco **tipos** possíveis no formulário (campo `tipo`/`participantes`):

1. **Varejo — apenas Gestor** — indústria indica lojistas; só o gestor participa.
2. **Varejo — Gestor + Representante (REP)** — os dois participam; REP tem bonificação.
3. **Varejo — Gestor + Vendas Interno** — gestor e time interno Blu; sem REP externo.
4. **Varejo — apenas Representante** — só REP externo (sem gestor).
5. **Varejo — Direta** — contato direto entre executivo Blu e o varejo (sem gestor nem REP).

> Nota: o schema Postgres usa `participantes` (enum) para os 5 casos e
> `tipo` (`varejo` | `representante`) como macro-classe.

---

## 4. Fluxo Ponta-a-Ponta

```
[LP Conexões]
    │ POST webhook (hoje: n8n)
    ▼
[WF1 — Indicação Varejo]
    ├─ valida fornecedor no HubDB 27538329
    ├─ valida executivo no HubDB 116939574
    ├─ cria/atualiza GES (contato HubSpot)
    ├─ cria/atualiza REP (custom object "rep")
    ├─ cria/atualiza Lojista (company HubSpot)
    ├─ loga na planilha Excel
    │
    ▼
[WF3 — Criação de Negócios]
    └─ para cada lojista:
          ├─ resolve UF (BrasilAPI CNPJ → senão DDD → senão fallback)
          ├─ aplica cenário (1..6) baseado em participantes
          ├─ aplica regionalização (owner por UF)
          ├─ marca Alto Potencial (flag do lojista)
          ├─ cria Deal no pipeline "Conexões"
          └─ associa Deal ↔ GES/REP/Lojista (typeIds abaixo)
```

Fontes auxiliares:

- `WF2 — Cadastro REP/Gestor` roda fora do fluxo da LP (uso admin).
- `WF4 — Consulta REP/Gestor` atende UIs internas (read-only).

---

## 5. Regras de Negócio Críticas

### 5.1 Determinação de UF do lojista

Ordem de resolução:

1. **BrasilAPI CNPJ** → `https://brasilapi.com.br/api/cnpj/v1/{cnpj}` → `uf`.
2. Se falhar, usa o **DDD do WhatsApp** via tabela DDD → UF.
3. Se ainda não resolver, marca UF como `INDEFINIDO` e roteia para o owner padrão.

### 5.2 Cenários do Workflow 3 (Deal)

Seis cenários deterministas a partir de `participantes`:

| Cenário | Participantes | Associações obrigatórias |
|---|---|---|
| 1 | apenas_gestor | Deal ↔ Lojista, Deal ↔ GES |
| 2 | gestor_e_representante | Deal ↔ Lojista, Deal ↔ GES, Deal ↔ REP |
| 3 | gestor_e_vendas_interno | Deal ↔ Lojista, Deal ↔ GES, Deal ↔ Executivo Blu |
| 4 | apenas_representante | Deal ↔ Lojista, Deal ↔ REP |
| 5 | direta | Deal ↔ Lojista, Deal ↔ Executivo Blu |
| 6 | feira (flag `eh_feira=true`) | Aplica cenários 1–5 + anexa `feira_nome` ao Deal; owner pode ir para pool de feiras. |

### 5.3 Regionalização (owner por UF)

Mapear UF → owner do CRM (tabela em HubDB). Regra padrão:

- UFs do **Sul/Sudeste** → pool A.
- UFs do **Nordeste** → pool B.
- UFs do **Norte/Centro-Oeste** → pool C.
- `INDEFINIDO` ou fallback → supervisor geral.

### 5.4 Alto Potencial

Lojista é marcado como `alto_potencial=true` se atender qualquer critério:

- CNPJ na lista VIP (HubDB interno).
- Produto indicado = `Split` (ticket médio alto).
- Faturamento anual declarado > R$ 50M (se preenchido).

### 5.5 Normalização de Cargo do Gestor

Mapear para o enum fechado (`CargoGestor`):

```
CEO/Dono, Diretor Financeiro, Gerente Financeiro, Supervisor Financeiro,
Analista Financeiro, Diretor Comercial, Gerente Comercial, Supervisor Comercial,
Analista Comercial, Outros
```

---

## 6. HubDBs

| HubDB ID | Nome | Uso |
|---|---|---|
| `116939574` | Executivos Blu | Lookup de nome/e-mail ativo; bloqueia LP se não existir. |
| `27538329` | Fornecedores | Código + CNPJ + razão social + apelido. Fonte do autocomplete da LP. |

> Ambos devem migrar para tabelas Supabase (`executivos`, `fornecedores`)
> como source-of-truth; HubDB pode ser mantido **espelhado** via sink.

---

## 7. Mapeamento de Propriedades (HubSpot CRM)

### 7.1 Contato (GES — gestor da indústria)

| Propriedade HubSpot | Campo da LP |
|---|---|
| `firstname` / `lastname` | `gestor.nome` (split) |
| `email` | `gestor.email` |
| `phone` | `gestor.celular` |
| `cargo_gestor_blu` | `gestor.cargo` (enum) |
| `fornecedor_codigo` | `fornecedor.codigo` |
| `papel_conexoes` | `"GES"` |

### 7.2 Custom Object REP (representante)

| Propriedade HubSpot | Campo da LP |
|---|---|
| `nome` | `representante.nome` |
| `documento` | `representante.documento` (limpo) |
| `tipo_documento` | `CPF` ou `CNPJ` (derivado) |
| `email` | `representante.email` |
| `celular` | `representante.celular` |
| `tipo_bonificacao` | `RPA` ou `NotaFiscal` |
| `fornecedor_principal_codigo` | `representante.fornecedor_principal.codigo` |

### 7.3 Company (Lojista)

| Propriedade HubSpot | Campo da LP |
|---|---|
| `name` | `lojista.razao_social` |
| `domain` / `name_fantasia` | `lojista.nome_fantasia` |
| `cnpj` | `lojista.cnpj` (limpo) |
| `email_principal` | `lojista.email` |
| `whatsapp` | `lojista.whatsapp` |
| `tipo_produto_conexoes` | `PagBlu` / `CredBlu` / `Split` |
| `condicao_especial` | bool |
| `condicao_especial_descricao` | texto livre |
| `observacoes_conexoes` | texto livre |
| `uf_resolvida` | derivada (BrasilAPI/DDD) |
| `alto_potencial` | bool (regra 5.4) |

### 7.4 Deal (pipeline "Conexões")

| Propriedade HubSpot | Campo |
|---|---|
| `dealname` | `"[Conexões] {fornecedor} → {lojista.razao_social}"` |
| `pipeline` | `pipeline_conexoes_id` |
| `dealstage` | `stage_inicial_id` |
| `hubspot_owner_id` | resolvido via regionalização (5.3) |
| `fornecedor_codigo` | `fornecedor.codigo` |
| `executivo_email` | `executivo.email` |
| `tipo_indicacao` | `tipo` |
| `participantes` | `participantes` |
| `eh_feira` / `feira_nome` | condicional |
| `prioridade` | `imediato` / `programado` |
| `data_contato_programada` | condicional |
| `cenario_wf3` | 1..6 |

---

## 8. Associações (typeIds USER_DEFINED)

> Valores reais são custom de cada portal. **O projeto deve ler os typeIds
> do `.env` / tabela de configuração**, não hard-coded:

```
HUBSPOT_ASSOC_DEAL_GES
HUBSPOT_ASSOC_DEAL_REP
HUBSPOT_ASSOC_DEAL_LOJISTA
HUBSPOT_ASSOC_DEAL_EXECUTIVO
HUBSPOT_ASSOC_GES_FORNECEDOR
HUBSPOT_ASSOC_REP_FORNECEDOR
HUBSPOT_ASSOC_LOJISTA_FORNECEDOR
HUBSPOT_ASSOC_LOJISTA_GES
HUBSPOT_ASSOC_LOJISTA_REP
HUBSPOT_ASSOC_GES_REP
HUBSPOT_ASSOC_EXECUTIVO_FORNECEDOR
```

---

## 9. Segurança

- **Origem:** aceitar apenas requisições de `https://blu.com.br` e
  dos ambientes de dev/staging (CORS allowlist).
- **Headers bloqueados:** recusar `X-Forwarded-Host`, `Host` customizado,
  `Origin` incompatível e qualquer header contendo CRLF (`\r` ou `\n`).
- **Rate limit** por IP/executivo (ex.: 30 req/min) no endpoint público.
- **Segredos** (HubSpot token, Supabase service_role) apenas em variáveis
  de ambiente — nunca no frontend.
- **Auditoria:** toda indicação gera registro em `audit_log`
  (before/after JSONB + quem + quando).

---

## 10. Observabilidade & Notificações

- **Notificações de erro** para o canal Teams "Conexões – Alertas"
  em falhas críticas (ex.: HubSpot 5xx, fornecedor ausente).
- **Log estruturado** (JSON) com `indicacao_id`, `idempotency_key`,
  `workflow`, `step`, `duration_ms`.
- **Métricas:** indicações/dia, % dedup, % Alto Potencial, latência p95
  do webhook, taxa de sucesso por workflow.
- **Sink Excel** preservado como backup offline (append-only).

---

## 11. Problemas identificados no fluxo atual (e solução v2)

| # | Problema | Solução v2 |
|---|---|---|
| P1 | Duplicidade de indicações | `idempotency_key` SHA-256 (fornecedor + participantes + lojistas + dia BR) com `UNIQUE INDEX`. |
| P2 | Datas em formatos errados/mistos | `timestamptz` em UTC + ISO-8601; fuso America/Sao_Paulo só na apresentação. |
| P3 | Falta de chave única | UUID v4 em todas as tabelas + `external_refs` JSONB. |
| P4 | Data de contato pedida ao usuário | Removida do payload; `created_at = now()` no banco. Só `data_contato` se `prioridade=programado`. |
| P5 | Só grava Excel + HubSpot | Supabase = source-of-truth; Excel/HubSpot/S3 viram sinks alimentados via `integration_events`. |
| P6 | UF mal resolvida | BrasilAPI → DDD → `INDEFINIDO` (5.1). |
| P7 | Owner atribuído manualmente | Regionalização determinística (5.3). |
| P8 | Alto Potencial era subjetivo | Regras 5.4 explícitas. |

---

## 12. Pendências do usuário (inputs externos)

- [ ] Exportar JSON dos 4 workflows n8n para `docs/n8n/`.
- [ ] Exportar schema (colunas) dos HubDBs `116939574` e `27538329`
      para `docs/hubspot/`.
- [ ] Confirmar typeIds das 11 associações (seção 8).
- [ ] Lista VIP de CNPJs para a regra de Alto Potencial (5.4).
- [ ] Mapa final UF → owner (5.3).

> Até esses inputs chegarem, o código mantém os stubs marcados com
> `NotImplementedError` e lê IDs das variáveis de ambiente.

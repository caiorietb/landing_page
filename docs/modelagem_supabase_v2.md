# Modelagem Supabase v2 — racional de engenharia de dados

> Substitui a migration `001_criar_tabela.sql` (um único `text` com CSV).
> Arquivo SQL: [`backend/migrations/002_modelagem_v2.sql`](../backend/migrations/002_modelagem_v2.sql).

## Por que refazer

A v1 tinha quatro problemas estruturais que o usuário identificou corretamente:

1. **Duplicidade** — nada impede dois POSTs idênticos de criarem duas linhas.
2. **Datas inconsistentes** — não tem garantia de timezone nem formato.
3. **Sem chave única** — só UUID sintético, zero rastreabilidade de negócio.
4. **Persistência errada** — Excel não é banco, HubSpot não é source-of-truth.

Além disso, o campo `cnpjs_varejistas text` (CSV dentro de uma célula) viola 1ª forma normal — impossível de filtrar, agregar ou integrar com HubSpot.

## Diagrama lógico

```
    master data                    transacional                 observabilidade
    ───────────                    ────────────                 ────────────────
                                                               
    executivos ─────────┐                                       
                        │                                       
    fornecedores ──┬────┤                                       audit_log
                   │    │                                       (1 linha por
    feiras ────────┼────┤   ┌─── indicacoes ──┐                 mutação)
                   │    │   │                 │                 
    gestores ──────┼────┼──▶│                 │──▶ indicacao_   integration_
                   │    │   │                 │    lojistas     events
    representantes ┴────┴──▶│                 │                 (fila p/
                                               │                 HubSpot/Excel
    lojistas ◀─────────────────────────────────┘                 /S3)
```

- **Master data**: catálogos deduplicados, atualizáveis, com `hubdb_row_id` ou `hubspot_*_id` para espelhar HubSpot.
- **Indicação** é quase só FKs + contexto + **`idempotency_key`**.
- **Linha por lojista indicado** em `indicacao_lojistas` → resolve o CSV.
- **Fila de eventos de integração** desacopla o POST da escrita no HubSpot/Excel.
- **Audit log** guarda `before/after` JSONB e `request_id` para auditoria ponta-a-ponta.

## Como a idempotência funciona

A cada indicação recebida, o backend calcula:

```python
import hashlib, json

def idempotency_key(payload: dict, dia: str) -> str:
    # Chave natural determinística — mesma combinação no mesmo dia = mesmo hash
    fingerprint = {
        "fornecedor_cnpj":   payload["fornecedor"]["cnpj"],
        "gestor_email":      (payload.get("gestor") or {}).get("email"),
        "rep_doc":           (payload.get("rep") or {}).get("documento"),
        "lojistas":          sorted(l["cnpj"] for l in payload["lojistas"]),
        "tipo":              payload["tipo"],
        "dia":               dia,  # YYYY-MM-DD no fuso America/Sao_Paulo
    }
    raw = json.dumps(fingerprint, sort_keys=True, ensure_ascii=False).encode()
    return hashlib.sha256(raw).hexdigest()
```

O `UNIQUE INDEX uq_indicacoes_idempotency` garante que reenvio do mesmo form no mesmo dia **não cria** um segundo registro — o `INSERT` cai em `ON CONFLICT DO NOTHING` e o backend devolve HTTP 200 com status `duplicada`, referenciando a indicação original.

## Timestamps — nunca mais perguntar data ao usuário

- `created_at timestamptz default now()` em todas as tabelas.
- `updated_at` mantido por trigger `touch_updated_at`.
- `deleted_at` para soft delete.
- A **LP não pergunta mais a data de cadastro** (P4 do doc de problemas).
- O campo `data_contato` (distinto de `created_at`) só existe se `prioridade = 'programado'` — enforçado por CHECK constraint.

## Enums tipados

Substitui strings mágicas por tipos fechados, aparecendo no `\d` e no OpenAPI:

- `tipo_indicacao`, `tipo_produto`, `tipo_documento`, `tipo_bonificacao_rep`
- `prioridade_contato`, `participantes_indicacao`, `cargo_gestor`
- `indicacao_status`, `integration_status`, `audit_action`

## Integração plug-and-play (HubSpot / Excel / S3)

`integration_events` é a fila de tarefas assíncronas. Quando uma indicação é criada, o backend enfileira N eventos:

```
target                    payload
────────                  ────────
hubspot_contact           { email, nome, tipo: gestor|rep|lojista }
hubspot_company           { cnpj, razao_social, fornecedor_id }
hubspot_deal              { fornecedor_id, lojista_id, produto, ... }
excel_append              { row: [...] }   -- quando a planilha ainda existir
s3_snapshot               { key: "...", parquet: {...} }  -- futuro
```

Um worker separado consome a fila com backoff exponencial. O `backend/integrations/` (próxima etapa) só precisa saber ler/atualizar essa tabela — zero acoplamento com o endpoint HTTP.

Migrar para S3/Parquet depois é trocar o target `excel_append` por `s3_parquet`: o schema do banco não muda.

## RLS

- Habilitado em todas as tabelas.
- Política `*_all` permissiva no MVP — igual à 001.
- Depois, quando tivermos auth, trocar por policies baseadas em `auth.email()`.

## Seed inicial

A migration já popula a tabela `feiras` com as ~60 feiras que aparecem no dropdown em produção, extraídas do HTML da LP. Fornecedores e executivos vêm do HubDB — serão importados no passo de integração (próxima sprint).

## Rollback

A migration 002 **não** dropa a tabela antiga `indicacoes` (v1) de propósito — se existir, sobrescreve (já que v2 recria com mesmo nome). **Antes de aplicar em prod**: `pg_dump` das linhas da v1 e um script de backfill `001 → 002` (podemos gerar quando for a hora).

-- ═══════════════════════════════════════════════════════════════════════════
--  Modelagem v2 — Blu Engajamento Comercial / Pipe de Conexões
--
--  Substitui a modelagem 001 (que era 1-tabela-flat com CSV em célula).
--
--  Princípios:
--    • Normalização até a 3ª forma normal nas entidades transacionais.
--    • Master data (fornecedores, feiras, executivos, usuários HubSpot)
--      em tabelas próprias com chaves naturais.
--    • Chaves primárias em UUID v4 (gen_random_uuid()).
--    • Timestamps automáticos (created_at, updated_at) com trigger.
--    • Soft delete (deleted_at) — nunca perdemos histórico.
--    • Auditoria completa via tabela audit_log.
--    • Idempotência forte: coluna idempotency_key com UNIQUE INDEX
--      derivada de chave natural + dia, evitando duplicidade por retry.
--    • Enums tipados para valores fechados.
--    • Observabilidade: integration_events para sincronização async
--      com HubSpot/Excel/S3.
--    • RLS habilitado (política permissiva no MVP, tightened depois).
--
--  Execução:
--    psql $SUPABASE_DB_URL -f backend/migrations/002_modelagem_v2.sql
--
--  ATENÇÃO: antes de rodar em prod, exportar dados da 001 se existirem.
-- ═══════════════════════════════════════════════════════════════════════════

begin;

-- ───────────────────────────────────────────────────────────────────────────
--  0. (Opcional) Drop de artefatos da v1
--
--  A migration 001 criou `indicacoes` como tabela plana com cnpjs em CSV.
--  A v2 reconstrói essa tabela com um schema completamente diferente.
--  Descomente o bloco abaixo APENAS em ambiente de dev/staging,
--  ou após `pg_dump` em prod, para limpar a v1:
-- ───────────────────────────────────────────────────────────────────────────
--
-- drop table if exists indicacao_lojistas cascade;
-- drop table if exists indicacoes          cascade;
--
-- ───────────────────────────────────────────────────────────────────────────
--  Extensões
-- ───────────────────────────────────────────────────────────────────────────
create extension if not exists "pgcrypto";   -- gen_random_uuid(), digest()
create extension if not exists "citext";     -- emails case-insensitive
create extension if not exists "pg_trgm";    -- busca por similaridade (opcional)


-- ───────────────────────────────────────────────────────────────────────────
--  Enums tipados
-- ───────────────────────────────────────────────────────────────────────────

do $$ begin
    create type tipo_indicacao         as enum ('varejo', 'representante');
    create type tipo_produto           as enum ('PagBlu', 'CredBlu', 'Split');
    create type tipo_documento         as enum ('cpf', 'cnpj');
    create type tipo_bonificacao_rep   as enum ('RPA', 'NotaFiscal');
    create type prioridade_contato     as enum ('imediato', 'programado');
    create type participantes_indicacao as enum (
        'apenas_gestor',
        'gestor_e_representante',
        'gestor_e_vendas_interno',
        'apenas_representante',
        'direta'
    );
    create type cargo_gestor as enum (
        'CEO_Dono',
        'Diretor_Financeiro',
        'Gerente_Financeiro',
        'Supervisor_Financeiro',
        'Analista_Financeiro',
        'Diretor_Comercial',
        'Gerente_Comercial',
        'Supervisor_Comercial',
        'Analista_Comercial',
        'Outros'
    );
    create type indicacao_status as enum (
        'recebida',         -- acabou de entrar
        'em_processamento', -- sendo sincronizada com HubSpot
        'concluida',        -- replicada no HubSpot e sinks
        'duplicada',        -- bateu em idempotency_key
        'erro'              -- falha definitiva após retries
    );
    create type integration_status as enum ('pending', 'sent', 'failed', 'skipped');
    create type audit_action       as enum ('insert', 'update', 'soft_delete', 'hard_delete');
exception
    when duplicate_object then null;
end $$;


-- ───────────────────────────────────────────────────────────────────────────
--  Função utilitária: manter updated_at
-- ───────────────────────────────────────────────────────────────────────────

create or replace function touch_updated_at()
returns trigger
language plpgsql
as $$
begin
    new.updated_at = now();
    return new;
end;
$$;


-- ───────────────────────────────────────────────────────────────────────────
--  1. MASTER DATA
-- ───────────────────────────────────────────────────────────────────────────

-- 1.1 Executivos Blu (espelho do HubDB 116939574 — "Inscrito por")
create table if not exists executivos (
    id              uuid primary key default gen_random_uuid(),
    hubdb_row_id    bigint unique,                                      -- id da linha no HubDB
    nome            text not null,
    email           citext not null unique,
    ativo           boolean not null default true,
    created_at      timestamptz not null default now(),
    updated_at      timestamptz not null default now(),
    deleted_at      timestamptz
);
create index if not exists idx_executivos_email_ativo
    on executivos (email) where deleted_at is null and ativo;
create trigger trg_executivos_updated
    before update on executivos
    for each row execute function touch_updated_at();


-- 1.2 Fornecedores / indústrias parceiras (espelho do HubDB 27538329)
create table if not exists fornecedores (
    id              uuid primary key default gen_random_uuid(),
    hubdb_row_id    bigint unique,
    codigo          text not null unique,            -- "0010", "2106" etc.
    razao_social    text not null,
    cnpj            varchar(14) not null,            -- pode haver 2 filiais = cnpj diferente
    apelido         text,                            -- "MATRIZ", "SÃO PAULO"
    ativo           boolean not null default true,
    created_at      timestamptz not null default now(),
    updated_at      timestamptz not null default now(),
    deleted_at      timestamptz,
    constraint fornecedor_cnpj_formato check (cnpj ~ '^[0-9]{14}$')
);
create index if not exists idx_fornecedores_cnpj on fornecedores (cnpj);
create index if not exists idx_fornecedores_codigo_ativo
    on fornecedores (codigo) where deleted_at is null and ativo;
create trigger trg_fornecedores_updated
    before update on fornecedores
    for each row execute function touch_updated_at();


-- 1.3 Feiras (catálogo fechado extraído da LP em produção)
create table if not exists feiras (
    id          uuid primary key default gen_random_uuid(),
    nome        text not null unique,
    ativo       boolean not null default true,
    created_at  timestamptz not null default now(),
    updated_at  timestamptz not null default now()
);
create trigger trg_feiras_updated
    before update on feiras
    for each row execute function touch_updated_at();


-- 1.4 Gestores (contatos do lado da indústria)
create table if not exists gestores (
    id              uuid primary key default gen_random_uuid(),
    hubspot_contact_id  text unique,                -- preenchido pela integração
    nome            text not null,
    email           citext not null unique,
    celular         text,
    cargo           cargo_gestor,
    fornecedor_id   uuid references fornecedores(id) on delete set null,
    created_at      timestamptz not null default now(),
    updated_at      timestamptz not null default now(),
    deleted_at      timestamptz
);
create index if not exists idx_gestores_fornecedor on gestores (fornecedor_id);
create trigger trg_gestores_updated
    before update on gestores
    for each row execute function touch_updated_at();


-- 1.5 Representantes comerciais (REP)
create table if not exists representantes (
    id                  uuid primary key default gen_random_uuid(),
    hubspot_contact_id  text unique,
    nome                text not null,
    email               citext,
    celular             text,
    tipo_documento      tipo_documento not null,
    documento           varchar(14) not null,       -- cpf(11) ou cnpj(14), só dígitos
    tipo_bonificacao    tipo_bonificacao_rep,
    fornecedor_principal_id uuid references fornecedores(id) on delete set null,
    created_at          timestamptz not null default now(),
    updated_at          timestamptz not null default now(),
    deleted_at          timestamptz,
    constraint rep_doc_coerente check (
        (tipo_documento = 'cpf'  and documento ~ '^[0-9]{11}$') or
        (tipo_documento = 'cnpj' and documento ~ '^[0-9]{14}$')
    ),
    constraint rep_doc_unico unique (tipo_documento, documento)
);
create trigger trg_representantes_updated
    before update on representantes
    for each row execute function touch_updated_at();


-- 1.6 Lojistas (varejistas indicados — master data, deduplicado por CNPJ)
create table if not exists lojistas (
    id              uuid primary key default gen_random_uuid(),
    hubspot_company_id text unique,
    cnpj            varchar(14) not null unique,
    razao_social    text not null,
    nome_fantasia   text not null,
    email_principal citext,
    whatsapp        text,
    created_at      timestamptz not null default now(),
    updated_at      timestamptz not null default now(),
    deleted_at      timestamptz,
    constraint lojista_cnpj_formato check (cnpj ~ '^[0-9]{14}$')
);
create index if not exists idx_lojistas_razao on lojistas using gin (razao_social gin_trgm_ops);
create trigger trg_lojistas_updated
    before update on lojistas
    for each row execute function touch_updated_at();


-- ───────────────────────────────────────────────────────────────────────────
--  2. TRANSAÇÃO PRINCIPAL — indicações
-- ───────────────────────────────────────────────────────────────────────────

-- 2.1 Header da indicação (contexto: quem indicou, fornecedor, feira, REP etc.)
create table if not exists indicacoes (
    id                  uuid primary key default gen_random_uuid(),

    -- Quem envia
    executivo_id        uuid references executivos(id) on delete restrict,
    executivo_email_snapshot citext,   -- snapshot para o caso do executivo mudar
    executivo_nome_snapshot  text,

    -- Contexto
    fornecedor_id       uuid not null references fornecedores(id) on delete restrict,
    tipo                tipo_indicacao not null,
    eh_feira            boolean not null default false,
    feira_id            uuid references feiras(id) on delete set null,

    -- Participantes
    participantes       participantes_indicacao,
    gestor_id           uuid references gestores(id) on delete set null,
    representante_id    uuid references representantes(id) on delete set null,

    -- Priorização
    prioridade          prioridade_contato not null default 'imediato',
    data_contato        date,                      -- só se prioridade=programado

    -- Status e referências externas
    status              indicacao_status not null default 'recebida',
    external_refs       jsonb not null default '{}'::jsonb,
    -- ex: {
    --   "hubspot_deal_ids": ["123", "456"],
    --   "n8n_execution_id": "xyz",
    --   "excel_row_ids":    [12, 13]
    -- }

    -- Idempotência: hash determinístico sobre (fornecedor, participantes, dia).
    -- Evita que reenvios acidentais criem indicações duplicadas no mesmo dia.
    idempotency_key     varchar(64) not null,

    -- Timestamps automáticos
    created_at          timestamptz not null default now(),
    updated_at          timestamptz not null default now(),
    deleted_at          timestamptz,

    -- Integridade
    constraint indicacao_feira_coerente check (
        (eh_feira = false and feira_id is null) or
        (eh_feira = true  and feira_id is not null)
    ),
    constraint indicacao_data_contato_coerente check (
        (prioridade = 'imediato'  and data_contato is null) or
        (prioridade = 'programado' and data_contato is not null)
    ),
    constraint indicacao_executivo_identificado check (
        executivo_id is not null or executivo_email_snapshot is not null
    )
);

-- Índice UNIQUE para dedup — só para registros não deletados
create unique index if not exists uq_indicacoes_idempotency
    on indicacoes (idempotency_key) where deleted_at is null;

create index if not exists idx_indicacoes_fornecedor   on indicacoes (fornecedor_id);
create index if not exists idx_indicacoes_executivo    on indicacoes (executivo_id);
create index if not exists idx_indicacoes_status       on indicacoes (status);
create index if not exists idx_indicacoes_created_at   on indicacoes (created_at desc);

create trigger trg_indicacoes_updated
    before update on indicacoes
    for each row execute function touch_updated_at();


-- 2.2 Linhas de lojistas indicados (n:m com "payload" próprio)
create table if not exists indicacao_lojistas (
    id                  uuid primary key default gen_random_uuid(),
    indicacao_id        uuid not null references indicacoes(id) on delete cascade,
    lojista_id          uuid not null references lojistas(id)   on delete restrict,

    tipo_produto                tipo_produto not null,
    condicao_especial           boolean not null default false,
    condicao_especial_descricao text,
    observacoes                 text,

    -- Mesmo lojista pode ser indicado em várias indicações ao longo do tempo,
    -- mas NÃO 2x dentro da mesma indicação.
    constraint uq_indicacao_lojista unique (indicacao_id, lojista_id),

    -- Limite de tamanho das observações (coerente com a LP: 0/1000).
    constraint obs_max_len        check (char_length(coalesce(observacoes, '')) <= 1000),
    constraint cond_esp_max_len   check (char_length(coalesce(condicao_especial_descricao, '')) <= 1000),
    constraint cond_esp_coerente  check (
        (condicao_especial = false and condicao_especial_descricao is null) or
        (condicao_especial = true  and condicao_especial_descricao is not null)
    ),

    external_refs   jsonb not null default '{}'::jsonb,
    created_at      timestamptz not null default now(),
    updated_at      timestamptz not null default now()
);
create index if not exists idx_indicacao_lojistas_indicacao on indicacao_lojistas (indicacao_id);
create index if not exists idx_indicacao_lojistas_lojista   on indicacao_lojistas (lojista_id);

create trigger trg_indicacao_lojistas_updated
    before update on indicacao_lojistas
    for each row execute function touch_updated_at();


-- ───────────────────────────────────────────────────────────────────────────
--  3. OBSERVABILIDADE / SINCRONIZAÇÃO ASSÍNCRONA
-- ───────────────────────────────────────────────────────────────────────────

-- 3.1 Fila de eventos de integração — alimenta HubSpot / Excel / S3
create table if not exists integration_events (
    id              uuid primary key default gen_random_uuid(),
    indicacao_id    uuid not null references indicacoes(id) on delete cascade,
    target          text not null,                     -- 'hubspot_contact', 'hubspot_deal', 'excel', 's3', ...
    payload         jsonb not null,
    status          integration_status not null default 'pending',
    attempts        integer not null default 0,
    last_error      text,
    next_retry_at   timestamptz,
    processed_at    timestamptz,
    created_at      timestamptz not null default now(),
    updated_at      timestamptz not null default now()
);
create index if not exists idx_integration_events_pending
    on integration_events (status, next_retry_at) where status in ('pending', 'failed');
create index if not exists idx_integration_events_indicacao on integration_events (indicacao_id);
create trigger trg_integration_events_updated
    before update on integration_events
    for each row execute function touch_updated_at();


-- 3.2 Audit log — uma linha por mutação em qualquer tabela importante
create table if not exists audit_log (
    id              bigserial primary key,
    occurred_at     timestamptz not null default now(),
    actor_email     citext,                            -- quem disparou (executivo, job async, etc.)
    request_id      uuid,                              -- correlation id da request HTTP
    entity          text not null,                     -- 'indicacoes', 'lojistas', ...
    entity_id       uuid not null,
    action          audit_action not null,
    diff            jsonb not null default '{}'::jsonb -- {before: {...}, after: {...}}
);
create index if not exists idx_audit_entity      on audit_log (entity, entity_id);
create index if not exists idx_audit_occurred_at on audit_log (occurred_at desc);


-- ───────────────────────────────────────────────────────────────────────────
--  4. VIEWS úteis para o painel
-- ───────────────────────────────────────────────────────────────────────────

create or replace view v_indicacoes_detalhe as
select
    i.id,
    i.created_at,
    i.status,
    i.tipo,
    i.prioridade,
    i.data_contato,
    coalesce(e.nome, i.executivo_nome_snapshot)   as executivo_nome,
    coalesce(e.email, i.executivo_email_snapshot) as executivo_email,
    f.codigo      as fornecedor_codigo,
    f.razao_social as fornecedor_nome,
    f.cnpj        as fornecedor_cnpj,
    fe.nome       as feira_nome,
    g.nome        as gestor_nome,
    g.email       as gestor_email,
    r.nome        as representante_nome,
    r.documento   as representante_doc,
    (
        select count(*)::int
        from indicacao_lojistas il
        where il.indicacao_id = i.id
    ) as qtd_lojistas,
    i.external_refs
from indicacoes i
left join executivos   e  on e.id  = i.executivo_id
left join fornecedores f  on f.id  = i.fornecedor_id
left join feiras       fe on fe.id = i.feira_id
left join gestores     g  on g.id  = i.gestor_id
left join representantes r on r.id = i.representante_id
where i.deleted_at is null;


-- ───────────────────────────────────────────────────────────────────────────
--  5. Row Level Security (política permissiva no MVP)
-- ───────────────────────────────────────────────────────────────────────────

alter table executivos        enable row level security;
alter table fornecedores      enable row level security;
alter table feiras            enable row level security;
alter table gestores          enable row level security;
alter table representantes    enable row level security;
alter table lojistas          enable row level security;
alter table indicacoes        enable row level security;
alter table indicacao_lojistas enable row level security;
alter table integration_events enable row level security;
alter table audit_log         enable row level security;

do $$
declare t text;
begin
    for t in
        select unnest(array[
            'executivos','fornecedores','feiras','gestores','representantes',
            'lojistas','indicacoes','indicacao_lojistas','integration_events','audit_log'
        ])
    loop
        execute format($f$
            drop policy if exists %I_all on %I;
            create policy %I_all on %I
                for all
                to public
                using (true)
                with check (true);
        $f$, t || '_all', t, t || '_all', t);
    end loop;
end $$;


-- ───────────────────────────────────────────────────────────────────────────
--  6. Seed inicial das feiras (fonte: LP em produção — seção 2.1)
-- ───────────────────────────────────────────────────────────────────────────

insert into feiras (nome) values
    ('ABCASA FAIR'),('ABF EXPO'),('ABIMAD'),('ABIÓPTICA / EXPOOPTICA'),
    ('ABUP SHOW'),('AJORSUL BUSINESS'),('AJORSUL FAIR MERCOÓPTICA'),
    ('BCONECTED'),('CAMILOTO SHOW ROOM'),('ELETROLARSHOW'),('EQUIPOTEL'),
    ('EVENTO CBC'),('EVENTO SIMM FEST'),('EVENTO SINDIMOL'),('EVENTO VIXLENS'),
    ('EXPO AJU MOVEIS'),('EXPO BAHIA MÓVEIS'),('EXPO MÓVEL - CARUARU'),
    ('EXPO MÓVEL - FORTALEZA'),('EXPO MÓVEL - GOIAS'),
    ('EXPO MÓVEL - NORDESTE/CARUARU'),('EXPO MÓVEL - SÃO LUÍS'),
    ('EXPO SUDOESTE'),('EXPO VALE (PETROLINA)'),('EXPOVISÃO'),
    ('FAIR HOUSE - MATO GROSSO DO SUL'),('FAIR HOUSE - PARANÁ'),
    ('FAIR HOUSE - SANTA CATARINA'),('FEIRA MUNDO BIKE'),('FEBRATEX'),
    ('FEMOJ'),('FEMOPE'),('FEMUR'),('FENÓPTICA'),('FERCAM'),('FIMEC'),
    ('FORMOBILE'),('GOTEX SHOW'),('INTERPLAST'),
    ('LAAD DEFENCE E SECURITY'),('LA MODA EXPERIENCE'),('MERCOMÓVEIS'),
    ('MÓVEL BRASIL'),('MOVELPAR'),('MOVELSUL BRASIL'),('MOVERGS'),
    ('PESCA E CIA TRADE SHOW'),('RIO MÓVEIS / CABO FRIO'),
    ('SALAO DE GRAMADO'),('SALÃO MÓVEL PB'),('SHIMANO FEST'),
    ('SHOT FAIR BRASIL'),('UBÁ SHOWROOM HORTO'),('UBÁ SHOWROOM TABAJARA'),
    ('VAREJO EXPERIENCE'),('YES MÓVEL SHOW - CAMPINAS'),
    ('YES MÓVEL SHOW - GOIAS')
on conflict (nome) do nothing;


commit;

-- ═══════════════════════════════════════════════════════════════════════════
--  FIM da migration 002_modelagem_v2.sql
-- ═══════════════════════════════════════════════════════════════════════════

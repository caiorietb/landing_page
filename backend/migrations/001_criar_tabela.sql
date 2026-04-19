-- Tabela principal de indicações
create table indicacoes (
    id            uuid primary key default gen_random_uuid(),
    executivo     text not null,
    cnpj_industria   text not null,
    doc_representante text not null,
    cnpjs_varejistas  text not null,  -- lista separada por vírgula, simples por ora
    detalhes      text,
    criado_em     timestamptz default now()
);

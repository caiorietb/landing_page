# Product Requirements Document — Blu Engajamento Comercial

## Overview

Ferramenta interna para executivos comerciais da Blu registrarem indicações de varejistas recebidas de indústrias parceiras. O objetivo é centralizar e organizar o pipeline do processo de Engajamento Comercial — a conversão de pagamentos via boleto para PagBlu, método de pagamento que utiliza recebíveis futuros de cartão de crédito gerados na POS da Blu.

## Problem Statement

Atualmente, as indicações de varejistas feitas pelas indústrias parceiras são registradas de forma descentralizada (planilhas, WhatsApp, e-mail), dificultando o acompanhamento do pipeline comercial e a rastreabilidade das indicações por executivo, indústria e representante. Isso gera perda de oportunidades e falta de visibilidade do processo.

## Goals & Success Metrics

- Centralizar 100% das indicações em um único sistema → zero indicações perdidas em planilhas avulsas
- Reduzir o tempo de registro de uma indicação para menos de 2 minutos → formulário validado e enviado sem erros
- Permitir que qualquer executivo acesse o painel de indicações em menos de 5 segundos → tempo de carregamento < 2s
- Viabilizar exportação dos dados para análise comercial → CSV gerado corretamente com todos os campos

## Target Users

**Executivos Comerciais da Blu** — profissionais de vendas internos que atuam no campo, visitam indústrias e varejistas, e são responsáveis pelo processo de engajamento. Têm conhecimento moderado de tecnologia, usam o sistema principalmente pelo celular ou notebook. Precisam de uma interface rápida e sem fricção para registrar indicações no momento da visita ou logo após.

## Scope

### In Scope (MVP)

- Formulário de cadastro de indicação com todos os campos obrigatórios
- Validação em tempo real de CNPJ e CPF (formato + dígitos verificadores)
- Suporte a múltiplos CNPJs de varejistas por indicação
- Registro automático da data/hora de cadastro
- Painel de listagem das indicações (tabela com filtro e busca)
- Exportação das indicações em CSV
- Acesso por link interno sem autenticação complexa

### Out of Scope (Futuro)

- Login com SSO / autenticação por conta Blu
- Notificações automáticas por e-mail ou Slack ao registrar indicação
- Dashboard com métricas e gráficos de conversão
- Integração com CRM (Salesforce, HubSpot)
- Fluxo de aprovação ou status de andamento da indicação
- App mobile nativo

## Functional Requirements

### FR-01: Formulário de Indicação

**Description:** Formulário web com todos os campos necessários para registrar uma indicação de engajamento comercial.

**Campos:**
- Nome do executivo Blu (texto) ou e-mail corporativo
- CNPJ da indústria indicante (input com máscara)
- CPF ou CNPJ do representante comercial da indústria (input com máscara, detecção automática por tamanho)
- CNPJs dos varejistas indicados (campo dinâmico — adicionar/remover múltiplos)
- Data de cadastro (preenchida automaticamente, não editável)
- Detalhes da negociação (textarea livre, opcional)

**Acceptance Criteria:**
- [ ] Todos os campos obrigatórios bloqueiam o envio se vazios, com mensagem de erro inline
- [ ] CNPJ e CPF são validados (formato e dígitos verificadores) antes do envio
- [ ] É possível adicionar no mínimo 1 e no máximo 20 CNPJs de varejistas
- [ ] Após envio bem-sucedido, o formulário é limpo e exibe mensagem de confirmação
- [ ] O envio falha graciosamente com mensagem de erro se o backend estiver indisponível

### FR-02: Validação de Documentos em Tempo Real

**Description:** Validação de CNPJ e CPF no frontend (formato + algoritmo de dígitos verificadores) e no backend antes de gravar no banco.

**Acceptance Criteria:**
- [ ] CNPJ é validado com o algoritmo oficial (módulo 11) assim que o campo perde o foco
- [ ] CPF é validado com o algoritmo oficial (módulo 11) assim que o campo perde o foco
- [ ] O tipo de documento (CPF vs CNPJ) do representante é detectado automaticamente pelo número de dígitos
- [ ] Documentos inválidos exibem mensagem de erro vermelha abaixo do campo
- [ ] O backend rejeita documentos inválidos com HTTP 422 mesmo que o frontend seja bypassado

### FR-03: Painel de Indicações

**Description:** Página separada com listagem tabular de todas as indicações cadastradas, com busca e filtro básicos.

**Acceptance Criteria:**
- [ ] Tabela exibe: executivo, CNPJ da indústria, representante, quantidade de varejistas, data, status resumido dos detalhes
- [ ] Campo de busca filtra por nome do executivo ou CNPJ da indústria em tempo real (frontend)
- [ ] Indicações são ordenadas da mais recente para a mais antiga por padrão
- [ ] Painel carrega em menos de 2 segundos para até 500 registros
- [ ] Linha expansível exibe CNPJs dos varejistas e detalhes da negociação

### FR-04: Exportação CSV

**Description:** Botão no painel que exporta todas as indicações visíveis (considerando filtros ativos) em formato CSV.

**Acceptance Criteria:**
- [ ] CSV inclui todos os campos da indicação, com CNPJs de varejistas separados por ponto-e-vírgula na mesma célula
- [ ] Nome do arquivo segue o padrão `blu_indicacoes_YYYY-MM-DD.csv`
- [ ] CSV usa encoding UTF-8 com BOM para compatibilidade com Excel
- [ ] A exportação respeita os filtros ativos no painel (exporta apenas o que está visível)

### FR-05: API Backend (FastAPI)

**Description:** API RESTful em Python/FastAPI que recebe, valida e persiste as indicações no Supabase.

**Endpoints:**
- `POST /indicacoes` — cria nova indicação
- `GET /indicacoes` — lista todas as indicações (suporte a query params de filtro)
- `GET /indicacoes/export/csv` — retorna CSV das indicações

**Acceptance Criteria:**
- [ ] `POST /indicacoes` valida todos os campos e retorna 201 em sucesso ou 422 com detalhes do erro
- [ ] `GET /indicacoes` aceita parâmetros `?executivo=` e `?cnpj_industria=` para filtro
- [ ] `GET /indicacoes/export/csv` retorna arquivo com `Content-Disposition: attachment`
- [ ] Todos os endpoints retornam JSON com estrutura consistente em caso de erro
- [ ] CORS configurado para permitir apenas a origem do frontend

### FR-06: Persistência no Supabase

**Description:** Todas as indicações são armazenadas no Supabase (PostgreSQL). O schema deve ser normalizado para suportar múltiplos varejistas por indicação.

**Acceptance Criteria:**
- [ ] Tabela `indicacoes` com campos: id, executivo_nome, executivo_email, cnpj_industria, doc_representante, detalhes, criado_em
- [ ] Tabela `varejistas_indicados` com campos: id, indicacao_id (FK), cnpj_varejista
- [ ] Todos os CNPJs são armazenados somente com dígitos (sem máscara)
- [ ] `criado_em` é preenchido automaticamente pelo banco com `now()`
- [ ] Row Level Security (RLS) habilitado com política de leitura/escrita irrestrita (sem auth no MVP)

## Non-Functional Requirements

- **Performance:** Carregamento inicial do formulário < 1.5s; painel com 500 registros < 2s
- **Segurança:** Validação de entrada no backend (nunca confiar apenas no frontend); HTTPS obrigatório em produção; variáveis sensíveis (chaves Supabase) apenas em variáveis de ambiente
- **Responsividade:** Layout funcional em mobile (375px) e desktop (1280px); formulário utilizável em celular
- **Confiabilidade:** Feedback claro ao usuário em caso de erro de rede ou servidor
- **Manutenibilidade:** Código Python com tipagem (Pydantic models); separação clara entre rotas, serviços e schemas

## Tech Stack

- **Frontend:** HTML5 + Tailwind CSS (CDN) + Alpine.js (CDN)
- **Backend:** Python 3.11+ / FastAPI + Uvicorn
- **Banco de Dados:** Supabase (PostgreSQL) via `supabase-py`
- **Hosting:** A definir (Railway ou Render para backend; Netlify ou Vercel para frontend estático)

## Sprint Plan Summary

| Sprint | Tema | Duração |
|--------|------|---------|
| Sprint 1 | Fundação: ambiente, banco de dados e estrutura base | 1 semana |
| Sprint 2 | Funcionalidades core: formulário, API e painel | 1 semana |
| Sprint 3 | Qualidade e entrega: validações, exportação CSV e deploy | 1 semana |

## Open Questions

- [ ] O acesso ao painel precisa de alguma restrição mínima? (ex: senha fixa, IP whitelist)
- [ ] Executivo usa nome OU email, ou ambos os campos devem estar presentes?
- [ ] Existe um limite máximo de varejistas por indicação que faz sentido para o negócio?
- [ ] Qual será o ambiente de hosting final? (Railway, Render, servidor interno Blu)
- [ ] Os dados precisam ser integrados futuramente com algum CRM já em uso na Blu?

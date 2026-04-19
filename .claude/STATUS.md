# Status do Projeto — Blu Engajamento Comercial

**Última atualização:** 2026-04-19  
**Sessão atual:** Sessão 2 — Sprint 2 concluído (validação CNPJ/CPF, varejistas dinâmicos, painel)

---

## Resumo do que foi feito

### Infraestrutura
- Projeto criado em `C:/Users/Caio Riet/Documents/GitHub/landing_page`
- Supabase conectado via MCP (projeto: **StrategyOS**, id: `eilohklurrojjmyivkyb`)
- Tabela `indicacoes` criada no Supabase com migração aplicada via MCP
- `.env` configurado com URL e chave anon do Supabase

### Backend (FastAPI)
- `backend/main.py` — API com 3 rotas: `GET /`, `POST /indicacoes`, `GET /indicacoes`
- `backend/requirements.txt` — dependências instaladas (fastapi, uvicorn, supabase, python-dotenv, httpx[http2])
- Virtualenv criado em `backend/venv/`
- Servidor rodando em `http://localhost:8000`

### Frontend
- `frontend/index.html` — formulário + painel em um único arquivo HTML + Tailwind CSS
- Servidor de desenvolvimento: `python -m http.server 3000` na pasta frontend
- Acesso em `http://localhost:3000`

### Documentação
- `PRD.md` — requisitos completos do produto
- `spec.json` — todas as tarefas organizadas em 3 sprints

---

## Status dos Sprints

### ✅ Sprint 1 — Fundação (CONCLUÍDO)
Todas as tarefas entregues nesta sessão:

| ID | Tarefa | Status |
|----|--------|--------|
| S1-T01 | Estrutura de pastas e arquivos | ✅ done |
| S1-T02 | Ambiente Python + FastAPI rodando | ✅ done |
| S1-T03 | Tabela `indicacoes` no Supabase | ✅ done |
| S1-T04 | Cliente Supabase conectado no backend | ✅ done |
| S1-T05 | Pydantic model básico (Indicacao) | ✅ done |
| S1-T06 | CORS configurado | ✅ done |
| S1-T07 | Layout base HTML + Tailwind | ✅ done |

**Resultado:** MVP funcional — formulário envia dados → FastAPI recebe → grava no Supabase → painel lista.

---

### ✅ Sprint 2 — Funcionalidades Core (CONCLUÍDO)

| ID | Tarefa | Status |
|----|--------|--------|
| S2-T01 | Validação de CNPJ e CPF no frontend (JS) | ✅ done |
| S2-T02 | Formulário com Alpine.js — campos estáticos | ✅ done |
| S2-T03 | Campo dinâmico de múltiplos CNPJs de varejistas | ✅ done |
| S2-T04 | Endpoint POST /indicacoes com validação completa | ✅ done |
| S2-T05 | Endpoint GET /indicacoes com filtros | ✅ done |
| S2-T06 | Painel de listagem com busca e linha expansível | ✅ done |

**Entregas:**
- `frontend/js/validacao.js` — algoritmo módulo 11 para CNPJ/CPF, máscaras, detecção automática
- `frontend/js/formulario.js` — controlador Alpine.js com validação bloqueante (submit não passa se faltar dígito)
- `frontend/js/painel.js` — controlador do painel com busca em tempo real
- `frontend/index.html` — formulário refatorado com Alpine.js + campo dinâmico de varejistas (1-20)
- `frontend/painel.html` — nova página do painel com tabela desktop + cards mobile, linhas expansíveis
- `backend/main.py` — validators Pydantic rejeitam CNPJ/CPF inválidos com HTTP 422 + filtros no GET

**Validações cobertas:**
- CNPJ: 14 dígitos, dígitos verificadores, rejeita sequências iguais (00000000000000, etc.)
- CPF: 11 dígitos, dígitos verificadores, rejeita sequências iguais
- Documento do representante: detecta CPF vs CNPJ pelo número de dígitos
- Varejistas: min 1, max 20, sem duplicados na mesma indicação
- Submit bloqueado se qualquer campo estiver vazio ou inválido (mensagens inline em vermelho)

---

### 🔲 Sprint 3 — Qualidade e Deploy (PENDENTE)

| ID | Tarefa | Status |
|----|--------|--------|
| S3-T01 | Endpoint exportação CSV | 🔲 todo |
| S3-T02 | Botão exportar CSV no painel | 🔲 todo |
| S3-T03 | Edge cases de validação | 🔲 todo |
| S3-T04 | Responsividade mobile | 🔲 todo |
| S3-T05 | Variáveis de ambiente e preparação deploy | 🔲 todo |
| S3-T06 | Testes end-to-end manuais | 🔲 todo |
| S3-T07 | Deploy (Railway/Render + Netlify/Vercel) | 🔲 todo |

---

## Como retomar na próxima sessão

```bash
# Terminal 1 — Backend
cd backend
venv\Scripts\activate
uvicorn main:app --reload

# Terminal 2 — Frontend
cd frontend
python -m http.server 3000
```

- Frontend: http://localhost:3000
- Backend: http://localhost:8000
- API Docs: http://localhost:8000/docs

## Decisões tomadas
- CNPJs de varejistas armazenados como texto separado por vírgula (MVP simples — tabela separada fica no backlog)
- Sem autenticação no MVP — acesso por link interno
- Alpine.js adotado a partir do Sprint 2 para o formulário dinâmico e reatividade do painel
- Supabase projeto: StrategyOS (não criar novo projeto — usar este)
- Frontend envia dígitos limpos (sem máscara) para o backend; banco armazena só dígitos
- Validação é feita em dois níveis: frontend (UX) + Pydantic no backend (garantia mesmo se o frontend for bypassado)

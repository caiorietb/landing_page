"""
backend.integrations
────────────────────
Módulos plug-and-play para sincronizar o Supabase com sistemas externos.

    integrations/
        hubspot/        ← lookup em HubDB + create/update em CRM
        sinks/          ← destinos secundários (Excel/S3 hoje, outros depois)

Regra: nenhum módulo aqui escreve diretamente no Supabase de `indicacoes`.
Eles só são chamados pelo worker que consome `integration_events`.
"""

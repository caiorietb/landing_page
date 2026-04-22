"""
Sinks — destinos secundários para a mesma indicação.

Hoje:
    - `excel.py` — append na planilha "[Conexões] Registro de Indicações.xlsx".

Futuro (quando trocar Excel por data lake):
    - `s3_parquet.py` — snapshot em Parquet em bucket S3.

Todos os sinks expõem a função `emit(indicacao_snapshot) -> dict` e
são chamados pelo mesmo worker que consome `integration_events`.
"""

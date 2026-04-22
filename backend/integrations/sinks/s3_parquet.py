"""
Sink: snapshot em Parquet em S3.

Destino de longo prazo: quando o Excel for aposentado, este sink vira
o espelho analítico. Usa o padrão `s3://blu-conexoes/indicacoes/dt={dia}/part-*.parquet`.

⚠️  SKELETON.
"""

from __future__ import annotations

from typing import Any


def emit(indicacao_snapshot: dict[str, Any]) -> dict[str, Any]:
    """Grava (ou mescla) o snapshot no particionamento diário do S3."""
    raise NotImplementedError(
        "Sink S3/Parquet ainda não implementado. Ativar quando o "
        "Excel for deprecado."
    )

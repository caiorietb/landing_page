"""
Sink: planilha [Conexões] Registro de Indicações.xlsx.

Mantido para paridade com o fluxo n8n legado enquanto a transição
acontece. Assim que o Supabase virar a source-of-truth reconhecida
pela área, este sink pode ser aposentado.

⚠️  SKELETON.
"""

from __future__ import annotations

from typing import Any


def emit(indicacao_snapshot: dict[str, Any]) -> dict[str, Any]:
    """
    Anexa 1 linha por lojista na planilha do SharePoint/OneDrive.
    Retorna `{"excel_row_ids": [...]}`.
    """
    raise NotImplementedError(
        "Sink Excel desligado — implementar com Microsoft Graph API "
        "ou deprecar quando o Supabase virar source-of-truth."
    )

"""
Validadores fiscais brasileiros — CNPJ e CPF (algoritmo oficial, módulo 11).

Puro, sem dependências externas. Usado tanto nos schemas Pydantic
quanto no cálculo da `idempotency_key`.
"""

from __future__ import annotations

import re


_REGEX_NAO_DIGITO = re.compile(r"\D")


def somente_digitos(valor: str | None) -> str:
    return _REGEX_NAO_DIGITO.sub("", valor or "")


def validar_cnpj(cnpj: str) -> bool:
    cnpj = somente_digitos(cnpj)
    if len(cnpj) != 14 or len(set(cnpj)) == 1:
        return False

    pesos1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    pesos2 = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]

    soma = sum(int(cnpj[i]) * pesos1[i] for i in range(12))
    d1 = 11 - (soma % 11)
    if d1 >= 10:
        d1 = 0
    if int(cnpj[12]) != d1:
        return False

    soma = sum(int(cnpj[i]) * pesos2[i] for i in range(13))
    d2 = 11 - (soma % 11)
    if d2 >= 10:
        d2 = 0
    return int(cnpj[13]) == d2


def validar_cpf(cpf: str) -> bool:
    cpf = somente_digitos(cpf)
    if len(cpf) != 11 or len(set(cpf)) == 1:
        return False

    soma = sum(int(cpf[i]) * (10 - i) for i in range(9))
    d1 = 11 - (soma % 11)
    if d1 >= 10:
        d1 = 0
    if int(cpf[9]) != d1:
        return False

    soma = sum(int(cpf[i]) * (11 - i) for i in range(10))
    d2 = 11 - (soma % 11)
    if d2 >= 10:
        d2 = 0
    return int(cpf[10]) == d2

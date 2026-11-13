"""Leitura e interpretação da configuração do OpenWrt (comando `uci show`)."""

import re
import shlex

NOME_VALIDO = re.compile(r"^[A-Za-z0-9_@\[\]-]+$")


def interpretar_uci_show(texto):
    """Transforma a saída do `uci show <pacote>` em {secao: {"tipo": ..., "opcoes": {...}}}.

    Opções com vários valores (listas) viram lista; as demais, texto.
    """
    secoes = {}
    for linha in texto.splitlines():
        if "=" not in linha:
            continue
        chave, valor = linha.split("=", 1)
        partes = chave.split(".")
        if len(partes) == 2:
            secoes[partes[1]] = {"tipo": valor.strip("'"), "opcoes": {}}
        elif len(partes) == 3 and partes[1] in secoes:
            valores = shlex.split(valor)
            secoes[partes[1]]["opcoes"][partes[2]] = valores[0] if len(valores) == 1 else valores
    return secoes

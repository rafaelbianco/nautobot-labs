"""Núcleo do "lego": o que todas as peças e fluxos têm em comum.

COMO FUNCIONA
=============
Toda peça recebe uma lista de ITENS e devolve uma lista de ITENS (como no N8N).
Um item é um dicionário simples, uma "linha" de informação. Chaves padrão:

    nome      -> quem/o que é (ex.: nome do equipamento, "Vlan10")
    ip        -> endereço IP, se houver
    ok        -> True/False: este item está bem até agora?
    mensagem  -> texto curto explicando o que aconteceu

Qualquer outra chave é livre (ex.: "vlan_id", "latencia_ms"). Só use texto,
números, True/False, listas e dicionários (nada de objetos do Nautobot).

Toda peça devolve o mesmo "envelope" (é o pino de encaixe do lego):

    {"peca": "...", "ok": True, "resumo": "...", "itens": [ {...}, {...} ]}

COMO CRIAR UMA PEÇA NOVA
========================
1. Herde de `PecaInicial` (começa a cadeia, não recebe itens) ou de `Peca`
   (recebe itens da peça anterior).
2. Declare os campos do formulário (StringVar, IntegerVar...), como em qualquer Job.
3. Escreva só o método `processar(self, itens, **parametros)` e devolva a lista de itens.
4. Registre com `register_jobs(MinhaPeca)` e importe o arquivo em `jobs/__init__.py`.

COMO MONTAR UM FLUXO
====================
Herde de `Fluxo` e liste os `passos`. Veja `jobs/fluxos/ping_e_avisa.py`.
"""

import json

from nautobot.apps.jobs import Job, ObjectVar
from nautobot.extras.models import JobResult

GRUPO_PECAS = "Lego - Peças"
GRUPO_FLUXOS = "Lego - Fluxos"


def montar_resultado(nome, itens, ok=None, resumo=None):
    """Monta o envelope padrão que liga uma peça à próxima."""
    for item in itens:
        if not isinstance(item, dict):
            raise TypeError(f"Cada item precisa ser um dicionário, recebi: {item!r}")
    try:
        json.dumps(itens)
    except TypeError as erro:
        raise TypeError(
            "Os itens só podem ter texto, números, True/False, listas e dicionários simples. "
            f"Detalhe: {erro}"
        ) from erro

    if ok is None:
        ok = all(item.get("ok", True) for item in itens)
    if resumo is None:
        com_sucesso = sum(1 for item in itens if item.get("ok", True))
        resumo = f"{com_sucesso} de {len(itens)} itens ok"
    return {"peca": nome, "ok": ok, "resumo": resumo, "itens": itens}


def itens_do_resultado(job_result):
    """Lê os itens guardados no resultado de uma execução anterior."""
    resultado = job_result.result
    if not isinstance(resultado, dict) or "itens" not in resultado:
        raise ValueError(
            f"A execução escolhida ({job_result.name}) não devolveu itens no formato do lego. "
            "Escolha o resultado de uma peça ou fluxo desta biblioteca."
        )
    return resultado["itens"]


class Entrada:
    """Usado num fluxo para dizer: 'use o valor que o operador preencheu neste campo'."""

    def __init__(self, campo):
        self.campo = campo


class Passo:
    """Um encaixe dentro de um fluxo.

    peca: a classe da peça.
    sempre: roda mesmo que um passo anterior tenha falhado (bom para avisos/resumos).
    continuar_se_falhar: se este passo falhar, o fluxo segue para o próximo
        (mesmo assim o fluxo termina marcado como falho, para ficar visível).
    parametros: valores dos campos da peça (valor fixo ou `Entrada("campo")`).
    """

    def __init__(self, peca, sempre=False, continuar_se_falhar=False, **parametros):
        self.peca = peca
        self.sempre = sempre
        self.continuar_se_falhar = continuar_se_falhar
        self.parametros = parametros


class PecaBase(Job):
    """Lógica comum a todas as peças. Não herde direto desta; use Peca ou PecaInicial."""

    # False = a peça decide sozinha se deu certo (os itens com ok=False não reprovam a peça).
    avalia_itens = True
    exige_itens = False
    # Por padrão a peça só trabalha nos itens com ok=True; os demais passam direto, intactos.
    # Use True para peças que precisam ver tudo (ex.: o resumo).
    processa_todos = False

    def processar(self, itens, **parametros):
        raise NotImplementedError("Toda peça precisa implementar o método processar().")

    def parametros_padrao(self):
        """Valores padrão dos campos, para a peça funcionar também dentro de um fluxo."""
        padrao = {}
        for nome, variavel in self._get_vars().items():
            inicial = variavel.field_attrs.get("initial")
            if inicial is not None:
                padrao[nome] = inicial
        return padrao

    def executar(self, itens, **parametros):
        """Roda a peça e devolve o envelope. Usado tanto sozinha quanto dentro de um fluxo."""
        if self.exige_itens and not itens:
            raise ValueError(
                "Esta peça precisa receber itens, mas nenhum chegou. "
                "Escolha um 'Resultado anterior' ou coloque-a depois de outra peça."
            )
        valores = {**self.parametros_padrao(), **parametros}
        itens = [dict(item) for item in itens]
        if self.processa_todos:
            a_processar, ignorados = itens, []
        else:
            a_processar = [item for item in itens if item.get("ok", True)]
            ignorados = [item for item in itens if not item.get("ok", True)]
        saida = self.processar(a_processar, **valores) + ignorados
        nome = self.Meta.name if hasattr(self.Meta, "name") else self.__class__.__name__
        resultado = montar_resultado(nome, saida, ok=None if self.avalia_itens else True)
        self.logger.info("[%s] %s", nome, resultado["resumo"])
        return resultado

    def run(self, resultado_anterior=None, **parametros):
        itens = itens_do_resultado(resultado_anterior) if resultado_anterior else []
        resultado = self.executar(itens, **parametros)
        if not resultado["ok"]:
            self.fail(resultado["resumo"])
        return resultado


class PecaInicial(PecaBase):
    """Peça que começa a cadeia (busca dados no Nautobot, lê uma lista...)."""


class Peca(PecaBase):
    """Peça que recebe os itens da peça anterior."""

    exige_itens = True

    resultado_anterior = ObjectVar(
        model=JobResult,
        required=False,
        label="Resultado anterior",
        description="Execução de outra peça/fluxo cujos itens esta peça vai usar. "
        "Dentro de um fluxo isso é automático e deve ficar vazio.",
    )


class Fluxo(Job):
    """Encadeia peças dentro de uma única execução. Preencha `passos` na subclasse."""

    passos = []

    def run(self, **entrada):
        self._validar_passos()
        itens = []
        relatorio = []
        parar = False
        houve_falha = False

        for numero, passo in enumerate(self.passos, start=1):
            peca = passo.peca()
            nome = peca.Meta.name
            if parar and not passo.sempre:
                self.logger.warning("Passo %s (%s) pulado porque um passo anterior falhou.", numero, nome)
                relatorio.append({"passo": numero, "peca": nome, "ok": False, "resumo": "pulado"})
                continue

            peca.job_result = self.job_result
            peca.logger = self.logger
            parametros = {
                chave: entrada[valor.campo] if isinstance(valor, Entrada) else valor
                for chave, valor in passo.parametros.items()
            }
            self.logger.info("Passo %s: %s", numero, nome)
            try:
                resultado = peca.executar(itens, **parametros)
            except Exception as erro:  # pylint: disable=broad-except
                self.logger.error("Passo %s (%s) falhou: %s", numero, nome, erro)
                resultado = {"peca": nome, "ok": False, "resumo": f"erro: {erro}", "itens": itens}

            itens = resultado["itens"]
            relatorio.append({"passo": numero, "peca": nome, "ok": resultado["ok"], "resumo": resultado["resumo"]})
            if not resultado["ok"]:
                houve_falha = True
                parar = parar or not passo.continuar_se_falhar

        ok = not houve_falha
        resumo = f"{sum(1 for p in relatorio if p['ok'])} de {len(relatorio)} passos ok"
        if not ok:
            self.fail(resumo)
        saida = montar_resultado(self.Meta.name, itens, ok=ok, resumo=resumo)
        saida["passos"] = relatorio
        return saida

    def _validar_passos(self):
        """Pega erros de digitação nos nomes dos campos antes de começar a mexer em qualquer coisa."""
        entradas = self._get_vars()
        for numero, passo in enumerate(self.passos, start=1):
            campos = passo.peca._get_vars()
            for chave, valor in passo.parametros.items():
                if chave not in campos:
                    raise ValueError(f"Passo {numero}: a peça {passo.peca.__name__} não tem o campo '{chave}'.")
                if isinstance(valor, Entrada) and valor.campo not in entradas:
                    raise ValueError(f"Passo {numero}: o fluxo não tem o campo de entrada '{valor.campo}'.")

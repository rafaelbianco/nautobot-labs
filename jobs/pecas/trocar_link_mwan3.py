import re
import shlex

from nautobot.apps.jobs import BooleanVar, ChoiceVar, IntegerVar, StringVar, register_jobs

from ..lego.core import GRUPO_PECAS, Peca
from ..lego.ssh import abrir_sessao, explicar_erro
from ..lego.uci import NOME_VALIDO
from .ler_regras_mwan3 import ler_mwan3

POLITICAS = (
    ("vivo", "vivo (WAN vivo como titular, nipbr de reserva)"),
    ("nipbr", "nipbr (WAN nipbr como titular, vivo de reserva)"),
)


def separar_nomes(texto):
    """'a, b  c' -> ['a', 'b', 'c'] (sem repetir)."""
    return list(dict.fromkeys(n for n in re.split(r"[,;\s]+", (texto or "").strip()) if n))


def planejar(mwan3, nomes, politica):
    """Compara o pedido com o que existe. Devolve (erros, mudanças). Não mexe em nada."""
    erros = []
    if not nomes:
        erros.append("nenhuma regra informada")
    if politica not in mwan3["politicas"]:
        erros.append(f"política '{politica}' não existe (existentes: {', '.join(mwan3['politicas'])})")
    for nome in nomes:
        if nome not in mwan3["regras"] or not NOME_VALIDO.match(nome):
            erros.append(f"regra '{nome}' não existe (existentes: {', '.join(mwan3['regras'])})")
    if erros:
        return erros, []
    mudancas = [
        {"regra": nome, "de": mwan3["regras"][nome]["politica"], "para": politica}
        for nome in nomes
        if mwan3["regras"][nome]["politica"] != politica
    ]
    return [], mudancas


def _executar(sessao, comando):
    codigo, saida = sessao.rodar(comando)
    if codigo != 0:
        raise RuntimeError(f"comando '{comando}' falhou: {saida}")


def _gravar(sessao, regra_para_politica):
    for regra, politica in regra_para_politica.items():
        _executar(sessao, f"uci set mwan3.{shlex.quote(regra)}.use_policy={shlex.quote(politica)}")
    _executar(sessao, "uci commit mwan3")
    _executar(sessao, "/etc/init.d/mwan3 restart")


def aplicar_com_conferencia(sessao, mudancas):
    """Grava as mudanças, confere o resultado e desfaz tudo se algo não bater."""
    novo = {m["regra"]: m["para"] for m in mudancas}
    antigo = {m["regra"]: m["de"] for m in mudancas}
    try:
        _gravar(sessao, novo)
        atual = ler_mwan3(sessao)["regras"]
        divergentes = [r for r, p in novo.items() if atual[r]["politica"] != p]
        if divergentes:
            raise RuntimeError(f"conferência falhou nas regras: {', '.join(divergentes)}")
    except Exception as erro:
        sessao.rodar("uci revert mwan3")
        try:
            _gravar(sessao, antigo)
            desfeito = "alterações desfeitas"
        except Exception as erro_desfazer:  # pylint: disable=broad-except
            desfeito = f"ATENÇÃO: não foi possível desfazer ({erro_desfazer}); confira o equipamento"
        raise RuntimeError(f"{erro}; {desfeito}") from erro


class TrocarLinkMwan3(Peca):
    """Muda a política (link de saída) de regras do MultiWAN. Simula por padrão."""

    class Meta:
        name = "Peça: Trocar link das regras MultiWAN"
        grouping = GRUPO_PECAS
        description = (
            "Troca a política (use_policy) das regras informadas. Os nomes são validados no equipamento antes de "
            "qualquer mudança. Com 'Aplicar' desmarcado, só mostra o que mudaria."
        )

    regras = StringVar(
        label="Regras",
        description="Nomes separados por vírgula ou espaço (a peça 'Ler regras MultiWAN' mostra os nomes atuais).",
    )
    politica = ChoiceVar(label="Link de destino", choices=POLITICAS)
    aplicar = BooleanVar(
        label="APLICAR no equipamento (desmarcado = só simula)",
        default=False,
        required=False,
    )
    timeout = IntegerVar(label="Timeout da conexão (s)", default=10, min_value=1, max_value=60)

    def processar(self, itens, regras="", politica="", aplicar=False, timeout=10, **_):
        nomes = separar_nomes(regras)
        for item in itens:
            nome = item.get("nome")
            try:
                with abrir_sessao(item, timeout) as sessao:
                    erros, mudancas = planejar(ler_mwan3(sessao), nomes, politica)
                    if erros:
                        raise ValueError("Pedido inválido, nada foi alterado: " + "; ".join(erros))
                    item["mudancas"] = mudancas
                    item["detalhes"] = [f"{m['regra']}: {m['de']} → {m['para']}" for m in mudancas]
                    item["aplicado"] = False
                    if not mudancas:
                        item["mensagem"] = f"Nada a alterar: as regras já usam '{politica}'"
                    elif not aplicar:
                        item["mensagem"] = f"SIMULAÇÃO: {len(mudancas)} regra(s) mudariam para '{politica}'"
                    else:
                        aplicar_com_conferencia(sessao, mudancas)
                        item["aplicado"] = True
                        item["mensagem"] = f"APLICADO: {len(mudancas)} regra(s) agora usam '{politica}'"
                log = self.logger.success if (item["aplicado"] or not mudancas) else self.logger.warning
                log("%s: %s", nome, item["mensagem"])
                for linha in item["detalhes"]:
                    self.logger.info("%s: %s", nome, linha)
            except ValueError as erro:
                item.update(ok=False, aplicado=False, mensagem=str(erro))
                self.logger.failure("%s: %s", nome, item["mensagem"])
            except Exception as erro:  # pylint: disable=broad-except
                item.update(ok=False, aplicado=False, mensagem=explicar_erro(erro, item))
                self.logger.failure("%s: %s", nome, item["mensagem"])
        return itens


register_jobs(TrocarLinkMwan3)

from nautobot.apps.jobs import IntegerVar, register_jobs

from ..lego.core import GRUPO_PECAS, Peca
from ..lego.ssh import abrir_sessao, explicar_erro
from ..lego.uci import interpretar_uci_show


def ler_mwan3(sessao):
    """Lê o MultiWAN do equipamento. Devolve {"regras": {...}, "politicas": {...}}."""
    codigo, saida = sessao.rodar("uci show mwan3")
    secoes = interpretar_uci_show(saida) if codigo == 0 else {}
    if not any(s["tipo"] in ("rule", "policy") for s in secoes.values()):
        raise LookupError("MultiWAN (mwan3) não encontrado ou sem regras neste equipamento")
    regras = {
        nome: {"src_ip": s["opcoes"].get("src_ip"), "politica": s["opcoes"].get("use_policy")}
        for nome, s in secoes.items()
        if s["tipo"] == "rule"
    }
    politicas = {
        nome: {"membros": s["opcoes"].get("use_member", [])} for nome, s in secoes.items() if s["tipo"] == "policy"
    }
    return {"regras": regras, "politicas": politicas}


class LerRegrasMwan3(Peca):
    """Lê as regras do MultiWAN (mwan3) e mostra por qual política (link) cada uma sai. Não altera nada."""

    class Meta:
        name = "Peça: Ler regras MultiWAN"
        grouping = GRUPO_PECAS
        description = "Lê via SSH as regras e políticas do mwan3 de cada item. Somente leitura."

    timeout = IntegerVar(label="Timeout da conexão (s)", default=10, min_value=1, max_value=60)

    def processar(self, itens, timeout=10, **_):
        for item in itens:
            try:
                with abrir_sessao(item, timeout) as sessao:
                    mwan3 = ler_mwan3(sessao)
                item["mwan3"] = mwan3
                item["detalhes"] = [
                    f"{nome} ({r['src_ip']}) → {r['politica']}" for nome, r in mwan3["regras"].items()
                ]
                item["mensagem"] = f"{len(mwan3['regras'])} regras, políticas: {', '.join(mwan3['politicas'])}"
                self.logger.success("%s: %s", item.get("nome"), item["mensagem"])
                for linha in item["detalhes"]:
                    self.logger.info("%s: regra %s", item.get("nome"), linha)
            except Exception as erro:  # pylint: disable=broad-except
                item.update(ok=False, mensagem=explicar_erro(erro, item))
                self.logger.failure("%s: %s", item.get("nome"), item["mensagem"])
        return itens


register_jobs(LerRegrasMwan3)

from nautobot.apps.jobs import IntegerVar, register_jobs

from ..lego.core import GRUPO_PECAS, Peca
from ..lego.ssh import abrir_sessao, explicar_erro


class TestarAcessoSSH(Peca):
    """Gate de acesso: só deixa passar adiante os devices onde o login SSH realmente funcionou."""

    class Meta:
        name = "Peça: Testar acesso SSH"
        grouping = GRUPO_PECAS
        description = (
            "Conecta por SSH em cada item (porta do config context 'ssh_port', senão 22; "
            "usuário e senha do Secrets Group do device) e roda 'echo ok'. Não altera nada."
        )

    timeout = IntegerVar(label="Timeout da conexão (s)", default=10, min_value=1, max_value=60)

    def processar(self, itens, timeout=10, **_):
        for item in itens:
            nome = item.get("nome")
            try:
                with abrir_sessao(item, timeout) as sessao:
                    _, saida = sessao.rodar("echo ok")
                if saida != "ok":
                    raise RuntimeError("O equipamento aceitou o login mas não executou o comando de teste")
                item.update(ok=True, mensagem=f"Login SSH ok na porta {item['porta']}")
                self.logger.success("%s: SSH ok (%s:%s).", nome, item.get("ip"), item["porta"])
            except Exception as erro:  # pylint: disable=broad-except
                item.update(ok=False, mensagem=explicar_erro(erro, item))
                self.logger.failure("%s: %s", nome, item["mensagem"])
        return itens


register_jobs(TestarAcessoSSH)

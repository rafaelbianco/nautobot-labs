import os

import requests
from nautobot.apps.jobs import BooleanVar, StringVar, register_jobs

from ..lego.core import GRUPO_PECAS, Peca

# O endereço do webhook é um segredo: fica numa variável de ambiente do container, nunca no código.
VARIAVEL_WEBHOOK = "GOOGLE_CHAT_WEBHOOK_URL"


class ResumoGoogleChat(Peca):
    """Envia para o Google Chat um resumo dos itens recebidos. Devolve os itens sem alterar."""

    avalia_itens = False
    processa_todos = True

    class Meta:
        name = "Peça: Resumo no Google Chat"
        grouping = GRUPO_PECAS
        description = f"Envia o resumo dos itens para o webhook definido na variável {VARIAVEL_WEBHOOK}."

    titulo = StringVar(label="Título da mensagem", default="Resumo da automação")
    somente_mostrar = BooleanVar(
        label="Só mostrar a mensagem (não enviar)",
        description="Marque para testar sem mandar nada ao Google Chat.",
        default=False,
        required=False,
    )

    def processar(self, itens, titulo="Resumo da automação", somente_mostrar=False, **_):
        linhas = [f"*{titulo}*"]
        for item in itens:
            icone = "✅" if item.get("ok", True) else "❌"
            ip = f" ({item['ip']})" if item.get("ip") else ""
            mensagem = f" - {item['mensagem']}" if item.get("mensagem") else ""
            linhas.append(f"{icone} {item.get('nome', '?')}{ip}{mensagem}")
        texto = "\n".join(linhas)

        if somente_mostrar:
            self.logger.info("Mensagem (não enviada):\n%s", texto)
            return itens

        url = os.environ.get(VARIAVEL_WEBHOOK)
        if not url:
            raise RuntimeError(f"A variável de ambiente {VARIAVEL_WEBHOOK} não está configurada no Nautobot.")
        resposta = requests.post(url, json={"text": texto}, timeout=10)
        resposta.raise_for_status()
        self.logger.success("Resumo enviado ao Google Chat.")
        return itens


register_jobs(ResumoGoogleChat)

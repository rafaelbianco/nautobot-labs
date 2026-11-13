import ipaddress
import re
import subprocess

from nautobot.apps.jobs import IntegerVar, register_jobs

from ..lego.core import GRUPO_PECAS, Peca


class PingItens(Peca):
    """Dá ping no campo 'ip' de cada item recebido e marca ok True/False."""

    class Meta:
        name = "Peça: Ping nos itens"
        grouping = GRUPO_PECAS
        description = "Pinga o IP de cada item recebido (feito a partir do worker do Nautobot)."

    quantidade = IntegerVar(label="Quantidade de pings", default=2, min_value=1, max_value=10)
    timeout = IntegerVar(label="Timeout por ping (s)", default=2, min_value=1, max_value=10)

    def processar(self, itens, quantidade=2, timeout=2, **_):
        for item in itens:
            try:
                # Garante que é mesmo um IP, já que o item pode vir de qualquer execução anterior.
                ip = str(ipaddress.ip_address(item.get("ip")))
            except ValueError:
                item.update(ok=False, mensagem="Item sem IP válido")
                self.logger.warning("%s: sem IP válido, ping ignorado.", item.get("nome"))
                continue

            res = subprocess.run(
                ["ping", "-c", str(quantidade), "-W", str(timeout), ip],
                capture_output=True,
                text=True,
                check=False,
            )
            latencia = re.search(r"= [\d.]+/([\d.]+)/", res.stdout)
            item["ok"] = res.returncode == 0
            item["latencia_ms"] = float(latencia.group(1)) if latencia else None
            item["mensagem"] = "Respondeu ao ping" if item["ok"] else "Sem resposta ao ping"
            log = self.logger.success if item["ok"] else self.logger.failure
            log("%s (%s): %s", item.get("nome"), ip, item["mensagem"])
        return itens


register_jobs(PingItens)

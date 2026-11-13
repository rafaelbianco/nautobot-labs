import socket

import paramiko
from nautobot.apps.jobs import IntegerVar, register_jobs
from nautobot.dcim.models import Device
from nautobot.extras.choices import SecretsGroupAccessTypeChoices, SecretsGroupSecretTypeChoices

from ..lego.core import GRUPO_PECAS, Peca

PORTA_PADRAO = 22


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
                device = Device.objects.get(pk=item.get("device_id"))
                porta = int(device.get_config_context().get("ssh_port", PORTA_PADRAO))
                item["porta"] = porta
                usuario, senha = self._credenciais(device)
                self._testar(item.get("ip"), porta, usuario, senha, timeout)
                item.update(ok=True, mensagem=f"Login SSH ok na porta {porta}")
                self.logger.success("%s: SSH ok (%s:%s).", nome, item.get("ip"), porta)
            except Exception as erro:  # pylint: disable=broad-except
                item.update(ok=False, mensagem=self._explicar(erro, item))
                self.logger.failure("%s: %s", nome, item["mensagem"])
        return itens

    @staticmethod
    def _credenciais(device):
        grupo = device.secrets_group
        if grupo is None:
            raise LookupError("Device sem Secrets Group (usuário/senha) cadastrado")
        usuario = grupo.get_secret_value(
            SecretsGroupAccessTypeChoices.TYPE_SSH, SecretsGroupSecretTypeChoices.TYPE_USERNAME, obj=device
        )
        senha = grupo.get_secret_value(
            SecretsGroupAccessTypeChoices.TYPE_SSH, SecretsGroupSecretTypeChoices.TYPE_PASSWORD, obj=device
        )
        return usuario, senha

    @staticmethod
    def _testar(ip, porta, usuario, senha, timeout):
        # Laboratório: aceita qualquer chave de host. Em produção, trocar por verificação de known_hosts.
        cliente = paramiko.SSHClient()
        cliente.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            cliente.connect(
                ip,
                port=porta,
                username=usuario,
                password=senha,
                timeout=timeout,
                banner_timeout=timeout,
                auth_timeout=timeout,
                look_for_keys=False,
                allow_agent=False,
            )
            _, saida, _ = cliente.exec_command("echo ok", timeout=timeout)
            if saida.read().decode().strip() != "ok":
                raise RuntimeError("O equipamento aceitou o login mas não executou o comando de teste")
        finally:
            cliente.close()

    @staticmethod
    def _explicar(erro, item):
        porta = item.get("porta", PORTA_PADRAO)
        if isinstance(erro, LookupError):
            return str(erro)
        if isinstance(erro, Device.DoesNotExist):
            return "Device não encontrado no Nautobot (item sem device_id válido)"
        if isinstance(erro, paramiko.AuthenticationException):
            return "Autenticação falhou (usuário ou senha incorretos)"
        if isinstance(erro, (socket.timeout, TimeoutError)):
            return f"Timeout ao conectar em {item.get('ip')}:{porta}"
        if isinstance(erro, paramiko.ssh_exception.NoValidConnectionsError) or isinstance(erro, ConnectionRefusedError):
            return f"Conexão recusada em {item.get('ip')}:{porta} (porta SSH correta?)"
        if isinstance(erro, paramiko.SSHException):
            return f"Erro de SSH: {erro}"
        return f"{type(erro).__name__}: {erro}"


register_jobs(TestarAcessoSSH)

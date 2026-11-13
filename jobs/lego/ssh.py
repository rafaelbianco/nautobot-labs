"""Conexão SSH compartilhada pelas peças que falam com equipamentos."""

import socket

import paramiko
from nautobot.dcim.models import Device
from nautobot.extras.choices import SecretsGroupAccessTypeChoices, SecretsGroupSecretTypeChoices

PORTA_PADRAO = 22


def credenciais(device):
    """Usuário e senha vêm do Secrets Group do device (nunca do código)."""
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


class Sessao:
    """Uma conexão SSH aberta. Use com `with`."""

    def __init__(self, ip, porta, usuario, senha, timeout):
        self.timeout = timeout
        self._args = {"hostname": ip, "port": porta, "username": usuario, "password": senha}
        self._cliente = paramiko.SSHClient()
        # Laboratório: aceita qualquer chave de host. Em produção, trocar por verificação de known_hosts.
        self._cliente.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    def __enter__(self):
        self._cliente.connect(
            **self._args,
            timeout=self.timeout,
            banner_timeout=self.timeout,
            auth_timeout=self.timeout,
            look_for_keys=False,
            allow_agent=False,
        )
        return self

    def __exit__(self, *_):
        self._cliente.close()

    def rodar(self, comando):
        """Executa um comando e devolve (código_de_saída, texto_de_saída)."""
        _, saida, erro = self._cliente.exec_command(comando, timeout=self.timeout)
        texto = saida.read().decode(errors="replace")
        texto_erro = erro.read().decode(errors="replace")
        return saida.channel.recv_exit_status(), (texto + texto_erro).strip()


def abrir_sessao(item, timeout=10):
    """Abre a sessão SSH para o device do item. Anota a porta usada em item['porta']."""
    device = Device.objects.get(pk=item.get("device_id"))
    item["porta"] = int(device.get_config_context().get("ssh_port", PORTA_PADRAO))
    usuario, senha = credenciais(device)
    return Sessao(item.get("ip"), item["porta"], usuario, senha, timeout)


def explicar_erro(erro, item):
    """Traduz erros técnicos em frases que o operador entende."""
    porta = item.get("porta", PORTA_PADRAO)
    if isinstance(erro, (LookupError, RuntimeError, ValueError)):
        return str(erro)
    if isinstance(erro, Device.DoesNotExist):
        return "Device não encontrado no Nautobot (item sem device_id válido)"
    if isinstance(erro, paramiko.AuthenticationException):
        return "Autenticação falhou (usuário ou senha incorretos)"
    if isinstance(erro, (socket.timeout, TimeoutError)):
        return f"Timeout ao conectar em {item.get('ip')}:{porta}"
    if isinstance(erro, (paramiko.ssh_exception.NoValidConnectionsError, ConnectionRefusedError)):
        return f"Conexão recusada em {item.get('ip')}:{porta} (porta SSH correta?)"
    if isinstance(erro, paramiko.SSHException):
        return f"Erro de SSH: {erro}"
    return f"{type(erro).__name__}: {erro}"

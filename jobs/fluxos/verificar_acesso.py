from nautobot.apps.jobs import MultiObjectVar, register_jobs
from nautobot.dcim.models import Device

from ..lego.core import GRUPO_FLUXOS, Entrada, Fluxo, Passo
from ..pecas.ping_itens import PingItens
from ..pecas.resumo_google_chat import ResumoGoogleChat
from ..pecas.selecionar_devices import SelecionarDevices
from ..pecas.testar_acesso_ssh import TestarAcessoSSH


class VerificarAcesso(Fluxo):
    """Confere se cada device responde ao ping e aceita login SSH, e avisa o resultado."""

    class Meta:
        name = "Fluxo: Verificar acesso aos devices"
        grouping = GRUPO_FLUXOS
        description = "Ping, depois teste de login SSH (somente leitura), e resumo no Google Chat."

    dispositivos = MultiObjectVar(model=Device, label="Dispositivos", required=True)

    passos = [
        Passo(SelecionarDevices, continuar_se_falhar=True, dispositivos=Entrada("dispositivos")),
        Passo(PingItens, continuar_se_falhar=True, quantidade=2),
        Passo(TestarAcessoSSH, continuar_se_falhar=True),
        Passo(ResumoGoogleChat, sempre=True, titulo="Verificação de acesso"),
    ]


register_jobs(VerificarAcesso)

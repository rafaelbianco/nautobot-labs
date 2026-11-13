from nautobot.apps.jobs import MultiObjectVar, register_jobs
from nautobot.dcim.models import Device

from ..lego.core import GRUPO_FLUXOS, Entrada, Fluxo, Passo
from ..pecas.ping_itens import PingItens
from ..pecas.resumo_google_chat import ResumoGoogleChat
from ..pecas.selecionar_devices import SelecionarDevices


class PingEAvisa(Fluxo):
    """Exemplo de fluxo: selecionar devices -> ping -> resumo no Google Chat."""

    class Meta:
        name = "Fluxo: Ping em devices e aviso no Google Chat"
        grouping = GRUPO_FLUXOS
        description = "Pinga os devices escolhidos e envia o resumo ao Google Chat, mesmo se algum falhar."

    dispositivos = MultiObjectVar(model=Device, label="Dispositivos", required=True)

    passos = [
        Passo(SelecionarDevices, continuar_se_falhar=True, dispositivos=Entrada("dispositivos")),
        Passo(PingItens, quantidade=2),
        Passo(ResumoGoogleChat, sempre=True, titulo="Teste de ping"),
    ]


register_jobs(PingEAvisa)

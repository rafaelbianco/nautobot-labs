from nautobot.apps.jobs import MultiObjectVar, register_jobs
from nautobot.dcim.models import Device

from ..lego.core import GRUPO_PECAS, PecaInicial


class SelecionarDevices(PecaInicial):
    """Transforma os devices escolhidos em itens (nome + IP primário) para as próximas peças."""

    class Meta:
        name = "Peça: Selecionar devices"
        grouping = GRUPO_PECAS
        description = "Escolhe devices do Nautobot e entrega nome e IP primário de cada um."

    dispositivos = MultiObjectVar(model=Device, label="Dispositivos", required=True)

    def processar(self, itens, dispositivos=(), **_):
        saida = []
        for device in dispositivos:
            ip = device.primary_ip.host if device.primary_ip else None
            saida.append(
                {
                    "nome": device.name,
                    "device_id": str(device.pk),
                    "ip": ip,
                    "ok": ip is not None,
                    "mensagem": "" if ip else "Sem IP primário cadastrado",
                }
            )
        return saida


register_jobs(SelecionarDevices)

from nautobot.apps.jobs import BooleanVar, ChoiceVar, MultiObjectVar, StringVar, register_jobs
from nautobot.dcim.models import Device

from ..lego.core import GRUPO_FLUXOS, Entrada, Fluxo, Passo
from ..pecas.ler_regras_mwan3 import LerRegrasMwan3
from ..pecas.ping_itens import PingItens
from ..pecas.resumo_google_chat import ResumoGoogleChat
from ..pecas.selecionar_devices import SelecionarDevices
from ..pecas.testar_acesso_ssh import TestarAcessoSSH
from ..pecas.trocar_link_mwan3 import POLITICAS, TrocarLinkMwan3

PASSOS_DE_ACESSO = [
    Passo(SelecionarDevices, continuar_se_falhar=True, dispositivos=Entrada("dispositivos")),
    Passo(PingItens, continuar_se_falhar=True, quantidade=2),
    Passo(TestarAcessoSSH, continuar_se_falhar=True),
]


class ConsultarRegrasMwan3(Fluxo):
    """Passo 1 da troca de link: mostra por qual link cada regra do MultiWAN sai hoje."""

    class Meta:
        name = "Fluxo: Consultar regras MultiWAN"
        grouping = GRUPO_FLUXOS
        description = "Somente leitura. Mostra as regras e a política (link) de cada uma, no resultado e no Google Chat."

    dispositivos = MultiObjectVar(model=Device, label="Dispositivos", required=True)

    passos = PASSOS_DE_ACESSO + [
        Passo(LerRegrasMwan3, continuar_se_falhar=True),
        Passo(ResumoGoogleChat, sempre=True, titulo="Regras MultiWAN"),
    ]


class TrocarLinkMwan3Fluxo(Fluxo):
    """Passo 2: troca o link das regras escolhidas, com simulação ligada por padrão."""

    class Meta:
        name = "Fluxo: Trocar link das regras MultiWAN"
        grouping = GRUPO_FLUXOS
        description = (
            "Confere acesso, valida as regras no equipamento e troca o link. "
            "Com 'Aplicar' desmarcado, só simula e mostra o que mudaria."
        )

    dispositivos = MultiObjectVar(model=Device, label="Dispositivos", required=True)
    regras = StringVar(
        label="Regras",
        description="Nomes separados por vírgula ou espaço. Use o fluxo 'Consultar regras MultiWAN' para ver os nomes.",
    )
    politica = ChoiceVar(label="Link de destino", choices=POLITICAS)
    aplicar = BooleanVar(
        label="APLICAR no equipamento (desmarcado = só simula)",
        default=False,
        required=False,
    )

    passos = PASSOS_DE_ACESSO + [
        Passo(
            TrocarLinkMwan3,
            continuar_se_falhar=True,
            regras=Entrada("regras"),
            politica=Entrada("politica"),
            aplicar=Entrada("aplicar"),
        ),
        Passo(ResumoGoogleChat, sempre=True, titulo="Troca de link MultiWAN"),
    ]


register_jobs(ConsultarRegrasMwan3, TrocarLinkMwan3Fluxo)

import subprocess
from nautobot.apps.jobs import Job, ObjectVar, register_jobs
from nautobot.dcim.models import Device

class PingViaGit(Job):
    class Meta:
        name = "Ping via GitHub (Dinâmico)"
        grouping = "Git Lab - Conectividade"
        description = "Job carregado dinamicamente direto do GitHub sem restart."

    device = ObjectVar(
        model=Device,
        description="Selecione o dispositivo",
        required=True,
    )

    def run(self, device):
        if not device.primary_ip:
            self.logger.error(f"{device.name} está sem IP primário.")
            return "Sem IP"

        ip = str(device.primary_ip.address.ip)
        self.logger.info(f"Testando ping (código vindo do Git) para {ip}...")
        res = subprocess.run(["ping", "-c", "2", ip], capture_output=True, text=True)

        if res.returncode == 0:
            self.logger.success(f"Sucesso!\n{res.stdout}")
            return "OK"
        else:
            self.logger.failure(f"Falha!\n{res.stderr or res.stdout}")
            return "Falha"

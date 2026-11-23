"""Implanta a plataforma BetterWay no AWS Academy (Learner Lab): S3 para os prints e o pacote, EC2 para o app.

Pré-requisito: as credenciais do Learner Lab em ~/.aws/credentials (AWS Details → AWS CLI → copiar para o arquivo).
Elas expiram junto com a sessão do laboratório (cerca de 4 h); a instância e o bucket continuam na conta.

    python deploy/aws/implantar.py            # cria (ou reaproveita) bucket, pacote, grupo de segurança e instância
    python deploy/aws/implantar.py --status   # mostra o endereço da plataforma
    python deploy/aws/implantar.py --encerrar # encerra a instância (o bucket fica)

O que sobe:
- S3 `betterway-<conta>`: `deploy/betterway.tar.gz` (código, banco, modelos de risco, vídeos já processados) e,
  depois, `registros/` com os prints dos relatórios (a plataforma grava lá com BETTERWAY_S3_BUCKET).
- EC2 t3.small, Ubuntu 24.04, com o perfil LabInstanceProfile (função LabRole do Academy): baixa o pacote do S3,
  instala as dependências e roda o Streamlit como serviço na porta 8501.
Nenhuma chave vai para dentro da instância: ela usa a função do laboratório.
"""
from __future__ import annotations

import argparse
import io
import sys
import tarfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
REGIAO = "us-east-1"
NOME = "betterway"
PORTA = 8501
INCLUIR = ["src/operador", "src/central", "src/estudo_b_risco_vida", "src/visao/visao.py", "src/visao/faixas_veo3",
           "assets/marca", "assets/simulacao", ".streamlit/config.toml",
           "data/processed/seguranca_viaria.db", "docs/evidencias/estudo_a", "docs/evidencias/operador",
           "models/modelo_risco.joblib", "models/modelo_gravidade.joblib", "deploy/aws/requirements-servidor.txt"]
VIDEOS = "data/processed/veo3"
FORA = ("__pycache__", ".pyc", "static/", "assets/marca/login-video.mp4")

USER_DATA = """#!/bin/bash
set -eux
apt-get update -y
apt-get install -y python3-venv python3-pip awscli || apt-get install -y python3-venv python3-pip unzip
command -v aws || (snap install aws-cli --classic)
mkdir -p /opt/betterway && cd /opt/betterway
aws s3 cp s3://{bucket}/deploy/betterway.tar.gz /tmp/betterway.tar.gz --region {regiao}
tar -xzf /tmp/betterway.tar.gz -C /opt/betterway
python3 -m venv /opt/betterway/.venv
/opt/betterway/.venv/bin/pip install --upgrade pip
/opt/betterway/.venv/bin/pip install -r /opt/betterway/deploy/aws/requirements-servidor.txt
cat > /etc/systemd/system/betterway.service <<'EOF'
[Unit]
Description=BetterWay (Streamlit)
After=network-online.target
[Service]
WorkingDirectory=/opt/betterway
Environment=BETTERWAY_S3_BUCKET={bucket}
Environment=AWS_REGION={regiao}
ExecStart=/opt/betterway/.venv/bin/python -m streamlit run src/operador/app.py --server.port {porta} --server.address 0.0.0.0 --server.headless true
Restart=always
[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
systemctl enable --now betterway
"""


def _arquivos() -> list[Path]:
    saida = []
    for item in INCLUIR:
        p = RAIZ / item
        if p.is_dir():
            saida += [f for f in p.rglob("*") if f.is_file() and not any(x in f.as_posix() for x in FORA)]
        elif p.is_file():
            saida.append(p)
    saida += sorted((RAIZ / VIDEOS).glob("*_anotado.mp4"))
    return saida


def pacote() -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for f in _arquivos():
            tar.add(f, arcname=f.relative_to(RAIZ).as_posix())
    return buf.getvalue()


def _sessao():
    import boto3
    return boto3.session.Session(region_name=REGIAO)


def _bucket(s) -> str:
    conta = s.client("sts").get_caller_identity()["Account"]
    nome = f"{NOME}-{conta}"
    s3 = s.client("s3")
    try:
        s3.head_bucket(Bucket=nome)
    except Exception:
        s3.create_bucket(Bucket=nome)
        s3.put_public_access_block(Bucket=nome, PublicAccessBlockConfiguration={
            "BlockPublicAcls": True, "IgnorePublicAcls": True, "BlockPublicPolicy": True, "RestrictPublicBuckets": True})
    return nome


def _grupo(ec2) -> str:
    try:
        return ec2.describe_security_groups(GroupNames=[NOME])["SecurityGroups"][0]["GroupId"]
    except Exception:
        gid = ec2.create_security_group(GroupName=NOME, Description="BetterWay: acesso web a plataforma")["GroupId"]
        ec2.authorize_security_group_ingress(GroupId=gid, IpPermissions=[{
            "IpProtocol": "tcp", "FromPort": PORTA, "ToPort": PORTA, "IpRanges": [{"CidrIp": "0.0.0.0/0",
                                                                              "Description": "plataforma"}]}])
        return gid


def _instancia(ec2):
    r = ec2.describe_instances(Filters=[{"Name": "tag:Name", "Values": [NOME]},
                                        {"Name": "instance-state-name", "Values": ["pending", "running"]}])
    inst = [i for res in r["Reservations"] for i in res["Instances"]]
    return inst[0] if inst else None


def implantar() -> None:
    s = _sessao()
    bucket = _bucket(s)
    dados = pacote()
    s.client("s3").put_object(Bucket=bucket, Key="deploy/betterway.tar.gz", Body=dados)
    print(f"pacote: s3://{bucket}/deploy/betterway.tar.gz ({len(dados) / 1e6:.1f} MB)")
    ec2 = s.client("ec2")
    if _instancia(ec2):
        print("a instância já existe; para reinstalar com o pacote novo, encerre (--encerrar) e rode de novo")
        return status()
    ami = s.client("ssm").get_parameter(
        Name="/aws/service/canonical/ubuntu/server/24.04/stable/current/amd64/hvm/ebs-gp3/ami-id")["Parameter"]["Value"]
    ec2.run_instances(ImageId=ami, InstanceType="t3.small", MinCount=1, MaxCount=1,
                      SecurityGroupIds=[_grupo(ec2)], IamInstanceProfile={"Name": "LabInstanceProfile"},
                      UserData=USER_DATA.format(bucket=bucket, regiao=REGIAO, porta=PORTA),
                      BlockDeviceMappings=[{"DeviceName": "/dev/sda1", "Ebs": {"VolumeSize": 16, "VolumeType": "gp3"}}],
                      TagSpecifications=[{"ResourceType": "instance", "Tags": [{"Key": "Name", "Value": NOME}]}])
    print("instância criada; a instalação leva de 5 a 8 minutos. Depois: python deploy/aws/implantar.py --status")


def status() -> None:
    i = _instancia(_sessao().client("ec2"))
    if not i:
        print("nenhuma instância BetterWay rodando")
        return
    ip = i.get("PublicIpAddress", "ainda sem IP")
    print(f"instância {i['InstanceId']} ({i['State']['Name']}): http://{ip}:{PORTA}")


def encerrar() -> None:
    ec2 = _sessao().client("ec2")
    i = _instancia(ec2)
    if i:
        ec2.terminate_instances(InstanceIds=[i["InstanceId"]])
        print(f"encerrando {i['InstanceId']}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser()
    p.add_argument("--status", action="store_true")
    p.add_argument("--encerrar", action="store_true")
    a = p.parse_args()
    encerrar() if a.encerrar else status() if a.status else implantar()

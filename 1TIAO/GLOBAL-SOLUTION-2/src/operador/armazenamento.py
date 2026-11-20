"""Onde ficam os prints dos relatórios: na pasta local (padrão) ou também num bucket S3 da AWS.

Com a variável BETTERWAY_S3_BUCKET definida (ex.: na instância EC2, com a função LabRole do AWS Academy), cada
print é enviado para s3://<bucket>/registros/<arquivo> e o relatório guarda esse endereço. Sem ela, nada muda:
o arquivo fica só na pasta local. A leitura aceita os dois formatos.
"""
from __future__ import annotations

import os
from pathlib import Path

PREFIXO = "registros/"


def bucket() -> str | None:
    return os.environ.get("BETTERWAY_S3_BUCKET") or None


def _cliente(cliente=None):
    if cliente is not None:
        return cliente
    import boto3
    return boto3.client("s3", region_name=os.environ.get("AWS_REGION", "us-east-1"))


def guardar(arquivo_local: Path, cliente=None) -> str:
    """Envia o print ao S3 quando há bucket configurado; devolve o endereço a gravar no relatório."""
    b = bucket()
    if not b:
        return str(arquivo_local)
    chave = PREFIXO + Path(arquivo_local).name
    _cliente(cliente).upload_file(str(arquivo_local), b, chave, ExtraArgs={"ContentType": "image/png"})
    return f"s3://{b}/{chave}"


def _partes(endereco: str) -> tuple[str, str]:
    resto = endereco.removeprefix("s3://")
    b, _, chave = resto.partition("/")
    return b, chave


def existe(endereco: str, cliente=None) -> bool:
    if not endereco.startswith("s3://"):
        return Path(endereco).exists()
    b, chave = _partes(endereco)
    try:
        _cliente(cliente).head_object(Bucket=b, Key=chave)
        return True
    except Exception:
        return False


def ler(endereco: str, cliente=None) -> bytes:
    """Bytes da imagem (para mostrar na tela), venha ela do disco ou do S3."""
    if not endereco.startswith("s3://"):
        return Path(endereco).read_bytes()
    b, chave = _partes(endereco)
    return _cliente(cliente).get_object(Bucket=b, Key=chave)["Body"].read()


def apagar(endereco: str, cliente=None) -> None:
    if endereco.startswith("s3://"):
        b, chave = _partes(endereco)
        _cliente(cliente).delete_object(Bucket=b, Key=chave)
    else:
        Path(endereco).unlink(missing_ok=True)


# ---------------------------------------------------------------- print guardado no disco, com cópia no S3
def copiar_para_nuvem(arquivo_local: Path, cliente=None) -> bool:
    """Envia a cópia do print ao S3 (mesmo nome) quando há bucket configurado."""
    if not bucket():
        return False
    guardar(arquivo_local, cliente)
    return True


def ler_print(arquivo_local: Path, cliente=None) -> bytes | None:
    """O print do disco; se ele não estiver aqui (outra instância), a cópia do S3; sem nenhum dos dois, None."""
    p = Path(arquivo_local)
    if p.exists():
        return p.read_bytes()
    b = bucket()
    if not b:
        return None
    try:
        return ler(f"s3://{b}/{PREFIXO}{p.name}", cliente)
    except Exception:
        return None


def apagar_print(arquivo_local: Path, cliente=None) -> None:
    Path(arquivo_local).unlink(missing_ok=True)
    b = bucket()
    if b:
        apagar(f"s3://{b}/{PREFIXO}{Path(arquivo_local).name}", cliente)

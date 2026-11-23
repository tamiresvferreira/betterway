"""Código de 6 dígitos que muda a cada 30 s (TOTP, RFC 6238), compatível com Google/Microsoft Authenticator.

Só biblioteca padrão: HMAC-SHA1 sobre o número do passo de 30 s, truncado (RFC 4226).
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import struct
import time
from urllib.parse import quote

PASSO_S = 30
EMISSOR = "BetterWay"


def gerar_segredo() -> str:
    """160 bits aleatórios em base32 (o formato que os aplicativos leem)."""
    return base64.b32encode(secrets.token_bytes(20)).decode().rstrip("=")


def _chave(segredo: str) -> bytes:
    s = segredo.strip().replace(" ", "").upper()
    return base64.b32decode(s + "=" * (-len(s) % 8))


def codigo(segredo: str, t: float | None = None, digitos: int = 6) -> str:
    passo = int((time.time() if t is None else t) // PASSO_S)
    h = hmac.new(_chave(segredo), struct.pack(">Q", passo), hashlib.sha1).digest()
    o = h[-1] & 0x0F
    n = (struct.unpack(">I", h[o:o + 4])[0] & 0x7FFFFFFF) % 10 ** digitos
    return str(n).zfill(digitos)


def verificar(segredo: str, recebido: str, t: float | None = None, janela: int = 1) -> bool:
    """Aceita o passo atual e os vizinhos (relógio do celular um pouco fora). Comparação em tempo constante."""
    recebido = (recebido or "").strip().replace(" ", "")
    if len(recebido) != 6 or not recebido.isdigit():
        return False
    t = time.time() if t is None else t
    return any(hmac.compare_digest(codigo(segredo, t + d * PASSO_S), recebido) for d in range(-janela, janela + 1))


def uri(segredo: str, usuario: str, emissor: str = EMISSOR) -> str:
    """Link otpauth:// que o QR Code carrega."""
    return (f"otpauth://totp/{quote(emissor)}:{quote(usuario)}?secret={segredo}&issuer={quote(emissor)}"
            f"&digits=6&period={PASSO_S}")

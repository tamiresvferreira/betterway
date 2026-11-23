"""Prints dos relatórios: disco sempre; cópia no S3 só com BETTERWAY_S3_BUCKET (cliente falso, sem rede)."""
import armazenamento as arm


class S3Falso:
    def __init__(self):
        self.objetos = {}

    def upload_file(self, origem, bucket, chave, ExtraArgs=None):
        self.objetos[(bucket, chave)] = open(origem, "rb").read()

    def get_object(self, Bucket, Key):
        import io
        return {"Body": io.BytesIO(self.objetos[(Bucket, Key)])}

    def head_object(self, Bucket, Key):
        if (Bucket, Key) not in self.objetos:
            raise KeyError(Key)

    def delete_object(self, Bucket, Key):
        self.objetos.pop((Bucket, Key), None)


def test_sem_bucket_fica_so_no_disco(tmp_path, monkeypatch):
    monkeypatch.delenv("BETTERWAY_S3_BUCKET", raising=False)
    f = tmp_path / "registro_0001.png"
    f.write_bytes(b"png")
    s3 = S3Falso()
    assert arm.copiar_para_nuvem(f, s3) is False and s3.objetos == {}
    assert arm.ler_print(f, s3) == b"png"


def test_com_bucket_copia_le_da_nuvem_e_apaga(tmp_path, monkeypatch):
    monkeypatch.setenv("BETTERWAY_S3_BUCKET", "betterway-teste")
    f = tmp_path / "registro_0002.png"
    f.write_bytes(b"png2")
    s3 = S3Falso()
    assert arm.copiar_para_nuvem(f, s3) is True
    assert ("betterway-teste", "registros/registro_0002.png") in s3.objetos
    f.unlink()                                       # outra instância: o disco não tem, a nuvem tem
    assert arm.ler_print(f, s3) == b"png2"
    arm.apagar_print(f, s3)
    assert s3.objetos == {} and arm.ler_print(f, s3) is None

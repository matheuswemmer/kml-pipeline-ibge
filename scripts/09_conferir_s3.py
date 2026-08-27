"""09 — Descobre quais arquivos do bucket ainda são a versão antiga.

Uso:
    aws s3 ls s3://amostrando-klm/ --recursive > lista_s3.txt
    python scripts/09_conferir_s3.py lista_s3.txt

Compara o tamanho de cada objeto no bucket com o do arquivo correspondente em
`publicacao/`. Tamanho diferente significa que aquele objeto não foi
substituído — o conteúdo novo é maior em praticamente todos os casos, porque
ganhou a tabela HTML do balão e os indicadores.

Serve para separar as duas causas quando parte do site mostra dado novo e
parte mostra dado antigo: se os arquivos divergentes aparecem aqui, foi upload
incompleto; se todos batem, o problema é cache em alguma camada do front.
"""

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from kmlpipe import logging_setup  # noqa: E402

PUBLICACAO = ROOT / "publicacao"

# Linha do `aws s3 ls --recursive`:
#   2026-08-27 15:19:03     567146 GO/Goianira/1755882187190.kml
LINHA = re.compile(r"^\s*(\S+)\s+(\S+)\s+(\d+)\s+(.+?)\s*$")


def _ler_lista(caminho: Path, log) -> str:
    """Lê a listagem seja qual for a codificação em que ela foi gravada.

    O `>` do Windows PowerShell 5.1 grava em UTF-16 LE, não em UTF-8 — o
    arquivo começa com o BOM `FF FE` e uma leitura como UTF-8 quebra logo no
    primeiro byte. Em vez de exigir `-Encoding utf8` no redirecionamento,
    detectamos o BOM e decodificamos de acordo.
    """
    bruto = caminho.read_bytes()
    marcas = [
        (b"\xff\xfe", "utf-16-le"),
        (b"\xfe\xff", "utf-16-be"),
        (b"\xef\xbb\xbf", "utf-8-sig"),
    ]
    for bom, codificacao in marcas:
        if bruto.startswith(bom):
            log.info("listagem em %s (BOM detectado)", codificacao)
            return bruto.decode(codificacao)

    for codificacao in ("utf-8", "latin-1"):
        try:
            return bruto.decode(codificacao)
        except UnicodeDecodeError:
            continue
    raise ValueError(f"não consegui decodificar {caminho}")


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("lista", help="saída de `aws s3 ls s3://BUCKET/ --recursive`")
    p.add_argument("--mostrar", type=int, default=15,
                   help="quantos divergentes listar (padrão 15)")
    args = p.parse_args()

    log = logging_setup.setup("conferir_s3")

    if not PUBLICACAO.exists():
        log.error("publicacao/ não existe — rode scripts/08_publicar.py")
        return 1

    esperado = {
        str(f.relative_to(PUBLICACAO)).replace("\\", "/"): f.stat().st_size
        for f in PUBLICACAO.rglob("*.kml")
    }
    log.info("%d arquivo(s) esperados em publicacao/", len(esperado))

    no_bucket: dict[str, int] = {}
    for linha in _ler_lista(Path(args.lista), log).splitlines():
        m = LINHA.match(linha)
        if m and m.group(4).endswith(".kml"):
            no_bucket[m.group(4)] = int(m.group(3))
    log.info("%d arquivo(s) .kml no bucket", len(no_bucket))

    faltando = sorted(set(esperado) - set(no_bucket))
    sobrando = sorted(set(no_bucket) - set(esperado))
    divergentes = sorted(
        (chave, no_bucket[chave], esperado[chave])
        for chave in set(esperado) & set(no_bucket)
        if no_bucket[chave] != esperado[chave]
    )

    print()
    print(f"esperados          {len(esperado):>6}")
    print(f"no bucket          {len(no_bucket):>6}")
    print(f"ausentes no bucket {len(faltando):>6}")
    print(f"sobrando no bucket {len(sobrando):>6}")
    print(f"tamanho divergente {len(divergentes):>6}   <- estes ainda são a versão antiga")

    if faltando:
        print(f"\nausentes ({len(faltando)}):")
        for chave in faltando[:args.mostrar]:
            print(f"  {chave}")

    if sobrando:
        print(f"\nsobrando — não correspondem a nenhum arquivo gerado ({len(sobrando)}):")
        for chave in sobrando[:args.mostrar]:
            print(f"  {chave}")

    if divergentes:
        print(f"\ndivergentes ({len(divergentes)}), bucket x esperado:")
        for chave, tem, quer in divergentes[:args.mostrar]:
            print(f"  {tem:>9,} x {quer:>9,}   {chave}")

        # Concentração por UF ajuda a ver se o sync parou no meio de um estado.
        import collections
        por_uf = collections.Counter(c.split("/")[0] for c, _, _ in divergentes)
        print("\n  por UF:", dict(sorted(por_uf.items())))

        alvo = ROOT / "data" / "interim" / "reenviar.txt"
        alvo.write_text("\n".join(c for c, _, _ in divergentes) + "\n",
                        encoding="utf-8")
        print(f"\n  lista completa para reenvio: {alvo}")

    if not (faltando or divergentes):
        print("\nok: todo objeto do bucket tem o tamanho do arquivo novo.")
        print("Se o front ainda mostra dado antigo, o problema é cache — não upload.")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())

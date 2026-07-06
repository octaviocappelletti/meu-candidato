"""
Download e upload de fotos de candidatos TSE 2022 → Supabase Storage

Pré-requisito: criar bucket público "fotos-candidatos" no Supabase
  (Storage → New bucket → nome: fotos-candidatos → Public: ON)

Uso:
    python baixar_fotos.py [--ufs SP RJ ...] [--dry-run]

Sem --ufs processa todas as 27 UFs + BR.
"""

import argparse
import io
import os
import re
import sys
import zipfile
from pathlib import Path

import requests
from dotenv import load_dotenv
from PIL import Image
from supabase import create_client

# ---------------------------------------------------------------------------
# Configuração
# ---------------------------------------------------------------------------

FOTO_ZIP_URL = (
    "https://cdn.tse.jus.br/estatistica/sead/eleicoes/eleicoes2022/fotos/"
    "foto_cand2022_{uf}_div.zip"
)

BUCKET = "fotos-candidatos"

# Tamanho máximo da foto (mantém proporção)
MAX_SIZE = (300, 400)

ALL_UFS = [
    "AC","AL","AP","AM","BA","CE","DF","ES","GO",
    "MA","MT","MS","MG","PA","PB","PR","PE","PI",
    "RJ","RN","RS","RO","RR","SC","SP","SE","TO","BR",
]

# Regex para extrair SQ_CANDIDATO do nome do arquivo
# Padrão: F{UF}{SQ_CANDIDATO}_div.{jpeg|jpg}
NOME_RE = re.compile(r"^F[A-Z]{2}(\d+)_div\.(jpeg|jpg)$", re.IGNORECASE)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def baixar_zip(uf: str) -> zipfile.ZipFile | None:
    url = FOTO_ZIP_URL.format(uf=uf)
    print(f"  Baixando fotos {uf}...", end=" ", flush=True)
    try:
        r = requests.get(url, timeout=120)
        r.raise_for_status()
        print(f"{len(r.content) // 1024} KB")
        return zipfile.ZipFile(io.BytesIO(r.content))
    except requests.HTTPError as e:
        print(f"ERRO HTTP {e.response.status_code}")
        return None


def redimensionar(dados: bytes) -> bytes:
    img = Image.open(io.BytesIO(dados)).convert("RGB")
    img.thumbnail(MAX_SIZE, Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=82, optimize=True)
    return buf.getvalue()


def upload_foto(client, sq: str, dados_jpeg: bytes, dry_run: bool) -> bool:
    if dry_run:
        return True
    path = f"{sq}.jpeg"
    try:
        client.storage.from_(BUCKET).upload(
            path=path,
            file=dados_jpeg,
            file_options={"content-type": "image/jpeg", "upsert": "true"},
        )
        return True
    except Exception as e:
        print(f"\n    Upload falhou para {sq}: {e}")
        return False


# ---------------------------------------------------------------------------
# Pipeline principal
# ---------------------------------------------------------------------------

def processar(ufs: list[str], dry_run: bool):
    load_dotenv(Path(__file__).parent.parent.parent / ".env.local")

    supabase_url = os.environ.get("NEXT_PUBLIC_SUPABASE_URL")
    service_key  = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")

    if not dry_run and (not supabase_url or not service_key):
        sys.exit("Erro: defina NEXT_PUBLIC_SUPABASE_URL e SUPABASE_SERVICE_ROLE_KEY no .env.local")

    client = create_client(supabase_url, service_key) if not dry_run else None

    ufs_alvo = ufs if ufs else ALL_UFS
    total_ok = 0
    total_erro = 0
    sqs_enviados: list[str] = []

    for uf in ufs_alvo:
        print(f"\n--- UF: {uf} ---")
        zf = baixar_zip(uf)
        if not zf:
            continue

        arquivos = [n for n in zf.namelist() if NOME_RE.match(n)]
        print(f"  Fotos no ZIP: {len(arquivos)}")

        for i, nome in enumerate(arquivos, 1):
            m = NOME_RE.match(nome)
            if not m:
                continue
            sq = m.group(1)

            try:
                dados_originais = zf.read(nome)
                dados_redim = redimensionar(dados_originais)
                ok = upload_foto(client, sq, dados_redim, dry_run)
                if ok:
                    total_ok += 1
                    sqs_enviados.append(sq)
                else:
                    total_erro += 1
            except Exception as e:
                print(f"\n    Erro ao processar {nome}: {e}")
                total_erro += 1

            if i % 100 == 0 or i == len(arquivos):
                print(f"  {i}/{len(arquivos)} processadas", end="\r")

        print(f"  {len(arquivos)}/{len(arquivos)} processadas")

    print(f"\nTotal: {total_ok} enviadas, {total_erro} erros")

    if dry_run:
        print("[DRY RUN] Nenhum dado enviado.")
        return

    # Atualiza url_foto no banco em um único UPDATE via SQL
    if sqs_enviados and client:
        print("\nAtualizando url_foto no banco...")
        storage_base = f"{supabase_url}/storage/v1/object/public/{BUCKET}"
        # Batch: atualiza todos de uma vez via SQL executado pelo client
        sql = f"""
            UPDATE public.candidatos
            SET url_foto = '{storage_base}/' || nr_sequencial || '.jpeg'
            WHERE nr_sequencial IS NOT NULL AND nr_sequencial != '';
        """
        try:
            client.rpc("exec_sql", {"query": sql}).execute()
            print("url_foto atualizado via RPC.")
        except Exception:
            # Fallback: imprime o SQL para rodar manualmente
            print("\nNao foi possivel executar via RPC. Rode manualmente no Supabase SQL Editor:")
            print("-" * 60)
            print(sql.strip())
            print("-" * 60)

    print("\nScript concluido.")


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Download fotos TSE -> Supabase Storage")
    parser.add_argument("--ufs", nargs="*", metavar="UF")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    processar(ufs=[u.upper() for u in args.ufs] if args.ufs else [], dry_run=args.dry_run)

"""
Ingestão de propostas de governo do TSE para o Supabase.

Processo:
  1. Baixa proposta_governo_{ano}_{uf}.zip do CDN do TSE
  2. Extrai os nr_sequencial dos nomes de arquivo
  3. Consulta o banco apenas para esses nr_sequencial (sem risco de paginação)
  4. Extrai texto via pypdf e faz upload do PDF para o Supabase Storage
  5. Faz upsert em public.propostas_governo

Pré-requisito:
  - Criar bucket "propostas-governo" (público) em app.supabase.com → Storage
  - Candidatos já ingeridos via ingesta_tse.py (coluna nr_sequencial populada)

Uso:
    python ingestao_propostas.py --ano 2022
    python ingestao_propostas.py --ano 2022 --uf SP
"""

import argparse
import io
import os
import re
import zipfile
from pathlib import Path

import requests
from dotenv import load_dotenv
from pypdf import PdfReader
from supabase import create_client, Client

load_dotenv(Path(__file__).parent.parent.parent / ".env.local")

SUPABASE_URL = os.environ.get("NEXT_PUBLIC_SUPABASE_URL", "")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")

BUCKET = "propostas-governo"

ALL_UFS = [
    "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO",
    "MA", "MT", "MS", "MG", "PA", "PB", "PR", "PE", "PI",
    "RJ", "RN", "RS", "RO", "RR", "SC", "SP", "SE", "TO",
]


def url_zip(ano: int, uf: str) -> str:
    return (
        f"https://cdn.tse.jus.br/estatistica/sead/odsele/"
        f"proposta_governo/proposta_governo_{ano}_{uf}.zip"
    )


def baixar_pdfs_do_zip(ano: int, uf: str) -> dict[str, bytes]:
    """Baixa o ZIP e retorna {filename: bytes} para cada PDF encontrado."""
    resp = requests.get(url_zip(ano, uf), timeout=180)
    resp.raise_for_status()
    pdfs: dict[str, bytes] = {}
    with zipfile.ZipFile(io.BytesIO(resp.content)) as z:
        for name in z.namelist():
            if name.lower().endswith(".pdf"):
                pdfs[name] = z.read(name)
    return pdfs


def extrair_nr_sequencial(filename: str) -> str | None:
    """
    Extrai o SQ_CANDIDATO do nome do arquivo PDF.
    O TSE nomeia: {ano}{UF}{nr_sequencial}.pdf — ex: 2022SP250001652196.pdf
    Retornamos a sequência numérica mais longa (o nr_sequencial).
    """
    stem = Path(filename).stem
    matches = re.findall(r'\d+', stem)
    if not matches:
        return None
    candidato = max(matches, key=len)
    return candidato if len(candidato) >= 6 else None


def buscar_candidatos_por_sequenciais(
    client: Client, sequenciais: list[str]
) -> dict[str, dict]:
    """
    Consulta o banco pelos nr_sequencial extraídos dos PDFs.
    Divide em chunks de 200 para evitar URLs longas e o limite de 1000 linhas do Supabase.
    """
    if not sequenciais:
        return {}

    resultado: dict[str, dict] = {}
    CHUNK = 200

    for i in range(0, len(sequenciais), CHUNK):
        chunk = sequenciais[i : i + CHUNK]
        resp = (
            client.table("candidatos")
            .select("numero_eleitoral, cargo, uf, nr_sequencial")
            .in_("nr_sequencial", chunk)
            .neq("nr_sequencial", "")
            .execute()
        )
        for row in resp.data or []:
            if row.get("nr_sequencial"):
                resultado[row["nr_sequencial"]] = row

    return resultado


def extrair_texto_pdf(pdf_bytes: bytes) -> str:
    """Extrai e normaliza o texto de todas as páginas do PDF."""
    reader = PdfReader(io.BytesIO(pdf_bytes))
    paginas: list[str] = []
    for page in reader.pages:
        texto = page.extract_text() or ""
        paginas.append(texto)

    texto_completo = "\n\n".join(paginas)
    linhas = [linha.rstrip() for linha in texto_completo.splitlines()]
    texto_limpo = re.sub(r'\n{3,}', '\n\n', "\n".join(linhas)).strip()
    # Remove null bytes que causam erro no Postgres (código 22P05)
    return texto_limpo.replace("\x00", "")


def garantir_bucket(client: Client) -> None:
    """Tenta criar o bucket se não existir; avisa caso não tenha permissão."""
    try:
        buckets = [b.name for b in client.storage.list_buckets()]
        if BUCKET not in buckets:
            client.storage.create_bucket(BUCKET, options={"public": True})
            print(f"Bucket '{BUCKET}' criado.")
    except Exception as exc:
        print(f"Aviso: não foi possível verificar/criar o bucket: {exc}")
        print(f"Crie-o manualmente no painel do Supabase (Storage → '{BUCKET}', público).")


def upload_pdf(client: Client, pdf_bytes: bytes, path: str) -> str:
    """Faz upload do PDF no Storage e retorna a URL pública."""
    client.storage.from_(BUCKET).upload(
        path,
        pdf_bytes,
        {"content-type": "application/pdf", "upsert": "true"},
    )
    return client.storage.from_(BUCKET).get_public_url(path)


def processar_uf(ano: int, uf: str, client: Client) -> int:
    """Processa uma UF; retorna quantidade de propostas gravadas."""
    print(f"  Baixando ZIP {uf}...", end=" ", flush=True)
    try:
        pdfs = baixar_pdfs_do_zip(ano, uf)
    except requests.HTTPError as exc:
        print(f"\n  ZIP não disponível: {exc}")
        return 0

    print(f"{len(pdfs)} PDFs")
    if not pdfs:
        return 0

    for nome in list(pdfs.keys())[:2]:
        print(f"    ex: {nome}")

    # Extrai os nr_sequencial dos nomes dos arquivos
    mapa_seq: dict[str, str] = {}  # {nr_sequencial: filename}
    for filename in pdfs:
        sq = extrair_nr_sequencial(filename)
        if sq:
            mapa_seq[sq] = filename

    if not mapa_seq:
        print(f"  Nenhum nr_sequencial extraído dos nomes de arquivo.")
        return 0

    # Consulta o banco só para esses sequenciais — sem limite de paginação
    idx_candidatos = buscar_candidatos_por_sequenciais(client, list(mapa_seq.keys()))
    print(f"  {len(idx_candidatos)}/{len(mapa_seq)} sequenciais encontrados no banco")

    registros: list[dict] = []

    for sq, filename in mapa_seq.items():
        candidato = idx_candidatos.get(sq)
        if not candidato:
            continue

        pdf_bytes = pdfs[filename]
        try:
            texto = extrair_texto_pdf(pdf_bytes)
            storage_path = f"{ano}/{uf}/{sq}.pdf"
            url_pdf = upload_pdf(client, pdf_bytes, storage_path)
            registros.append({
                "numero_eleitoral": candidato["numero_eleitoral"],
                "cargo": candidato["cargo"],
                "uf": uf,
                "texto": texto,
                "url_pdf": url_pdf,
            })
        except Exception as exc:
            print(f"    Erro em {filename}: {exc}")

    sem_match = [sq for sq in mapa_seq if sq not in idx_candidatos]
    if sem_match:
        print(f"  {len(sem_match)} PDFs sem candidato correspondente no banco:")
        for sq in sem_match:
            print(f"    nr_sequencial: {sq} ({mapa_seq[sq]})")

    if registros:
        client.table("propostas_governo").upsert(
            registros, on_conflict="cargo,uf,numero_eleitoral"
        ).execute()
        print(f"  ✓ {len(registros)} propostas gravadas")

    return len(registros)


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingestão de propostas de governo do TSE")
    parser.add_argument("--ano", type=int, default=2022)
    parser.add_argument("--uf", type=str, default=None, help="UF específica (ex: SP)")
    args = parser.parse_args()

    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        raise SystemExit(
            "Defina NEXT_PUBLIC_SUPABASE_URL e SUPABASE_SERVICE_ROLE_KEY no .env.local"
        )

    client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
    ufs = [args.uf.upper()] if args.uf else ALL_UFS

    garantir_bucket(client)

    total = 0
    for uf in ufs:
        print(f"\n[{uf}]")
        try:
            total += processar_uf(args.ano, uf, client)
        except Exception as exc:
            print(f"  ✗ Falhou: {exc}")

    print(f"\nTotal: {total} propostas gravadas.")


if __name__ == "__main__":
    main()

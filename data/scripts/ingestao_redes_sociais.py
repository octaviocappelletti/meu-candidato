"""
Ingestão de redes sociais dos candidatos do TSE para o Supabase.

Fonte: https://cdn.tse.jus.br/estatistica/sead/odsele/consulta_cand/
       rede_social_candidato_{ano}_{uf}.zip

Processo:
  1. Baixa o ZIP por UF
  2. Extrai e normaliza o CSV (match por SQ_CANDIDATO = nr_sequencial)
  3. Atualiza as colunas de rede social na tabela candidatos

Uso:
    python ingestao_redes_sociais.py --ano 2022
    python ingestao_redes_sociais.py --ano 2022 --uf AC
"""

import argparse
import io
import os
import zipfile
from pathlib import Path

import pandas as pd
import requests
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv(Path(__file__).parent.parent.parent / ".env.local")

SUPABASE_URL = os.environ.get("NEXT_PUBLIC_SUPABASE_URL", "")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")

ALL_UFS = [
    "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO",
    "MA", "MT", "MS", "MG", "PA", "PB", "PR", "PE", "PI",
    "RJ", "RN", "RS", "RO", "RR", "SC", "SP", "SE", "TO",
]

COLUNAS_REDES = ["url_facebook", "url_instagram", "url_twitter", "url_youtube", "email_campanha"]


def detectar_rede(url: str) -> str | None:
    """Infere a rede social pelo domínio da URL ou pelo formato de e-mail."""
    u = url.lower().strip()
    if "facebook.com" in u or "fb.com" in u:
        return "url_facebook"
    if "instagram.com" in u:
        return "url_instagram"
    if "twitter.com" in u or "x.com" in u:
        return "url_twitter"
    if "youtube.com" in u or "youtu.be" in u:
        return "url_youtube"
    if "@" in u and not u.startswith("http"):
        return "email_campanha"
    return None


def url_zip(ano: int, uf: str) -> str:
    return (
        f"https://cdn.tse.jus.br/estatistica/sead/odsele/consulta_cand/"
        f"rede_social_candidato_{ano}_{uf}.zip"
    )


def baixar_csv(ano: int, uf: str) -> pd.DataFrame:
    """Baixa o ZIP e retorna o DataFrame do CSV de redes sociais."""
    resp = requests.get(url_zip(ano, uf), timeout=120)
    resp.raise_for_status()

    with zipfile.ZipFile(io.BytesIO(resp.content)) as z:
        csv_name = next((n for n in z.namelist() if n.lower().endswith(".csv")), None)
        if not csv_name:
            raise ValueError("Nenhum CSV encontrado no ZIP")
        with z.open(csv_name) as f:
            return pd.read_csv(f, sep=";", encoding="latin-1", dtype=str, on_bad_lines="skip")


def normalizar(df: pd.DataFrame) -> dict[str, dict[str, str]]:
    """
    Retorna {sq_candidato: {url_facebook: ..., url_instagram: ..., ...}}.
    A rede social é inferida pelo domínio da URL (não há coluna de tipo no CSV do TSE).
    """
    col_sq  = next((c for c in df.columns if "SQ_CANDIDATO" in c.upper()), None)
    col_url = next((c for c in df.columns if c.upper() == "DS_URL"), None)

    if not col_sq or not col_url:
        print(f"    Colunas disponíveis: {list(df.columns)}")
        raise ValueError(f"Colunas esperadas não encontradas — SQ={col_sq}, URL={col_url}")

    resultado: dict[str, dict[str, str]] = {}

    for _, row in df.iterrows():
        sq  = str(row[col_sq]).strip()  if pd.notna(row[col_sq])  else ""
        url = str(row[col_url]).strip() if pd.notna(row[col_url]) else ""

        if not sq or not url or url.lower() == "nan":
            continue

        coluna = detectar_rede(url)
        if not coluna:
            continue

        if sq not in resultado:
            resultado[sq] = {c: "" for c in COLUNAS_REDES}
        resultado[sq][coluna] = url

    return resultado


def buscar_candidatos_por_sequenciais(
    client: Client, sequenciais: list[str]
) -> dict[str, dict]:
    """
    Retorna {nr_sequencial: {id, nome_urna, ...}} para os sequenciais fornecidos.
    Divide em chunks de 200 para evitar URLs longas (erro 400) e o limite de 1000 linhas do Supabase.
    """
    if not sequenciais:
        return {}

    resultado: dict[str, dict] = {}
    CHUNK = 200

    for i in range(0, len(sequenciais), CHUNK):
        chunk = sequenciais[i : i + CHUNK]
        resp = (
            client.table("candidatos")
            .select("id, nr_sequencial, nome_urna, nome_completo, numero_eleitoral, cargo, uf, partido, situacao")
            .in_("nr_sequencial", chunk)
            .execute()
        )
        for row in resp.data or []:
            if row.get("nr_sequencial") and row.get("id"):
                resultado[row["nr_sequencial"]] = row

    return resultado


def processar_uf(ano: int, uf: str, client: Client) -> int:
    """Processa uma UF; retorna quantidade de candidatos atualizados."""
    print(f"  Baixando ZIP {uf}...", end=" ", flush=True)
    try:
        df = baixar_csv(ano, uf)
    except requests.HTTPError as exc:
        print(f"\n  ZIP não disponível: {exc}")
        return 0

    print(f"{len(df)} linhas")

    mapa_redes = normalizar(df)
    if not mapa_redes:
        print("  Nenhuma rede social encontrada")
        return 0

    print(f"  {len(mapa_redes)} candidatos com redes sociais no CSV")

    idx = buscar_candidatos_por_sequenciais(client, list(mapa_redes.keys()))
    print(f"  {len(idx)}/{len(mapa_redes)} encontrados no banco")

    # Monta registros incluindo os campos NOT NULL obrigatórios para o upsert não falhar
    registros = []
    for sq, redes in mapa_redes.items():
        cand = idx.get(sq)
        if not cand:
            continue
        registros.append({
            "id":               cand["id"],
            "nome_urna":        cand["nome_urna"],
            "nome_completo":    cand["nome_completo"],
            "numero_eleitoral": cand["numero_eleitoral"],
            "cargo":            cand["cargo"],
            "uf":               cand["uf"],
            "partido":          cand["partido"],
            "situacao":         cand["situacao"],
            **redes,
        })

    if not registros:
        return 0

    for i in range(0, len(registros), 500):
        lote = registros[i : i + 500]
        client.table("candidatos").upsert(lote, on_conflict="id").execute()

    print(f"  ✓ {len(registros)} candidatos atualizados")
    return len(registros)


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingestão de redes sociais do TSE")
    parser.add_argument("--ano", type=int, default=2022)
    parser.add_argument("--uf", type=str, default=None, help="UF específica (ex: AC)")
    args = parser.parse_args()

    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        raise SystemExit(
            "Defina NEXT_PUBLIC_SUPABASE_URL e SUPABASE_SERVICE_ROLE_KEY no .env.local"
        )

    client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
    ufs = [args.uf.upper()] if args.uf else ALL_UFS

    total = 0
    for uf in ufs:
        print(f"\n[{uf}]")
        try:
            total += processar_uf(args.ano, uf, client)
        except Exception as exc:
            print(f"  ✗ Falhou: {exc}")

    print(f"\nTotal: {total} candidatos com redes sociais atualizados.")


if __name__ == "__main__":
    main()

"""
Ingestão de dados do TSE para o Supabase.

Fonte: https://dadosabertos.tse.jus.br/
Processo: baixa CSVs de candidaturas → limpa → normaliza → grava no Supabase.

Uso:
    python ingestao_tse.py --ano 2026
    python ingestao_tse.py --ano 2026 --uf SP
"""

import argparse
import os
import io
import zipfile

import pandas as pd
import requests
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_SERVICE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

BASE_URL_TSE = "https://dadosabertos.tse.jus.br/dataset/candidatos-{ano}/resource"

UFS_BRASIL = [
    "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO",
    "MA", "MT", "MS", "MG", "PA", "PB", "PR", "PE", "PI",
    "RJ", "RN", "RS", "RO", "RR", "SC", "SP", "SE", "TO",
]

MAPA_CARGOS = {
    "PRESIDENTE": "presidente",
    "VICE-PRESIDENTE": "presidente",
    "GOVERNADOR": "governador",
    "VICE-GOVERNADOR": "governador",
    "SENADOR": "senador",
    "DEPUTADO FEDERAL": "deputado-federal",
    "DEPUTADO ESTADUAL": "deputado-estadual",
}

SITUACOES_APTAS = {
    "DEFERIDO",
    "DEFERIDO COM RECURSO",
}


def baixar_candidaturas(ano: int, uf: str) -> pd.DataFrame:
    """Baixa e descompacta o CSV de candidaturas do TSE para um estado e ano."""
    # TODO: substituir pela URL real do TSE quando as candidaturas 2026 forem abertas
    url = f"https://dadosabertos.tse.jus.br/dataset/candidatos-{ano}/resource/candidatos_{uf}_{ano}.zip"
    response = requests.get(url, timeout=60)
    response.raise_for_status()

    with zipfile.ZipFile(io.BytesIO(response.content)) as z:
        csv_name = next(n for n in z.namelist() if n.endswith(".csv"))
        with z.open(csv_name) as f:
            return pd.read_csv(f, sep=";", encoding="latin-1", dtype=str)


def limpar_dados(df: pd.DataFrame) -> pd.DataFrame:
    """Seleciona, renomeia e limpa colunas relevantes do CSV do TSE."""
    # Mapeamento de colunas TSE → nosso schema
    colunas = {
        "NM_URNA_CANDIDATO": "nome_urna",
        "NM_CANDIDATO": "nome_completo",
        "NR_CANDIDATO": "numero_eleitoral",
        "DS_CARGO": "cargo_tse",
        "SG_UF": "uf",
        "SG_PARTIDO": "partido",
        "DS_SITUACAO_CANDIDATURA": "situacao",
        "SQ_CANDIDATO": "sq_candidato",
    }
    df = df.rename(columns=colunas)[list(colunas.values())]

    df["cargo"] = df["cargo_tse"].str.upper().map(MAPA_CARGOS)
    df = df.dropna(subset=["cargo"])

    df["situacao_apta"] = df["situacao"].str.upper().isin(SITUACOES_APTAS)

    df["nome_urna"] = df["nome_urna"].str.strip().str.upper()
    df["nome_completo"] = df["nome_completo"].str.strip().str.title()
    df["numero_eleitoral"] = pd.to_numeric(df["numero_eleitoral"], errors="coerce")
    df["uf"] = df["uf"].str.upper()

    df["url_foto"] = df["sq_candidato"].apply(
        lambda sq: f"https://divulgacandcontas.tse.jus.br/candidaturas/oficial/2026/BR/BR/2040600614/candidatos/{sq}/foto.jpeg"
        if pd.notna(sq)
        else None
    )

    return df.drop(columns=["cargo_tse", "sq_candidato"])


def gravar_supabase(df: pd.DataFrame, client: Client) -> None:
    """Faz upsert dos candidatos normalizados no Supabase."""
    registros = df.where(pd.notna(df), None).to_dict(orient="records")
    client.table("candidatos").upsert(registros, on_conflict="numero_eleitoral,uf").execute()
    print(f"  {len(registros)} registros gravados")


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingestão de dados do TSE")
    parser.add_argument("--ano", type=int, default=2026)
    parser.add_argument("--uf", type=str, default=None, help="UF específica (ex: SP)")
    args = parser.parse_args()

    client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
    ufs = [args.uf.upper()] if args.uf else UFS_BRASIL

    for uf in ufs:
        print(f"Processando {uf}...")
        try:
            df = baixar_candidaturas(args.ano, uf)
            df = limpar_dados(df)
            gravar_supabase(df, client)
            print(f"✓ {uf} concluído")
        except Exception as e:
            print(f"✗ {uf} falhou: {e}")


if __name__ == "__main__":
    main()

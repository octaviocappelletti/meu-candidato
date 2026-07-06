"""
Ingestão de dados do TSE para o Supabase.

Fonte: https://dadosabertos.tse.jus.br/
Processo: baixa ZIP do TSE (ou usa arquivo local) -> limpa -> normaliza -> grava no Supabase.

Uso:
    # Baixa e processa um estado:
    python ingestao_tse.py --ano 2022 --uf SP

    # Baixa e processa todos os estados:
    python ingestao_tse.py --ano 2022

    # Usa arquivo ZIP já baixado do TSE (mais rápido):
    python ingestao_tse.py --ano 2022 --arquivo consulta_cand_2022_SP.zip
"""

import argparse
import io
import math
import os
import zipfile

import pandas as pd
import requests
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_SERVICE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

# URL do CDN do TSE — arquivo nacional único (todos os estados)
URL_TSE = (
    "https://cdn.tse.jus.br/estatistica/sead/odsele/consulta_cand/"
    "consulta_cand_{ano}.zip"
)

UFS_BRASIL = [
    "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO",
    "MA", "MT", "MS", "MG", "PA", "PB", "PR", "PE", "PI",
    "RJ", "RN", "RS", "RO", "RR", "SC", "SP", "SE", "TO",
]

# Colunas que queremos do CSV do TSE -> nome interno
COLUNAS_TSE = {
    "SQ_CANDIDATO":          "sq_candidato",
    "NM_URNA_CANDIDATO":     "nome_urna",
    "NM_CANDIDATO":          "nome_completo",
    "NR_CANDIDATO":          "numero_eleitoral",
    "DS_CARGO":              "cargo_tse",
    "SG_UF":                 "uf",
    "SG_PARTIDO":            "partido",
    "DS_SITUACAO_CANDIDATURA": "situacao",
    "CD_ELEICAO":            "cd_eleicao",
}

MAPA_CARGOS: dict[str, str] = {
    "PRESIDENTE":                    "presidente",
    "VICE-PRESIDENTE DA REPÚBLICA":  "presidente",
    "VICE-PRESIDENTE":               "presidente",
    "GOVERNADOR":                    "governador",
    "VICE-GOVERNADOR":               "governador",
    "SENADOR":                       "senador",
    "DEPUTADO FEDERAL":              "deputado-federal",
    "DEPUTADO ESTADUAL":             "deputado-estadual",
}

MAPA_SUBCARGO: dict[str, str | None] = {
    "PRESIDENTE":                    None,
    "VICE-PRESIDENTE DA REPÚBLICA":  "vice-presidente",
    "VICE-PRESIDENTE":               "vice-presidente",
    "GOVERNADOR":                    None,
    "VICE-GOVERNADOR":               "vice-governador",
    "SENADOR":                       None,
    "DEPUTADO FEDERAL":              None,
    "DEPUTADO ESTADUAL":             None,
}

SITUACOES_APTAS = {"APTO", "DEFERIDO", "DEFERIDO COM RECURSO"}


def _ler_zip_bytes(dados: bytes) -> pd.DataFrame:
    """Abre um ZIP em memória e lê todos os CSVs dentro dele."""
    frames: list[pd.DataFrame] = []
    with zipfile.ZipFile(io.BytesIO(dados)) as z:
        csvs = [n for n in z.namelist() if n.lower().endswith(".csv")]
        for nome in csvs:
            with z.open(nome) as f:
                df = pd.read_csv(
                    f, sep=";", encoding="latin-1",
                    dtype=str, on_bad_lines="skip",
                )
                frames.append(df)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def baixar(ano: int) -> pd.DataFrame:
    """Baixa o ZIP nacional do CDN do TSE (todos os estados) e retorna o DataFrame bruto."""
    url = URL_TSE.format(ano=ano)
    print(f"  Baixando {url} ...")
    print("  (arquivo nacional ~150 MB, aguarde...)")
    r = requests.get(url, timeout=300)
    r.raise_for_status()
    return _ler_zip_bytes(r.content)


def ler_arquivo(caminho: str) -> pd.DataFrame:
    """Lê um ZIP ou CSV local do TSE."""
    import pathlib
    p = pathlib.Path(caminho)
    if p.suffix.lower() == ".zip":
        return _ler_zip_bytes(p.read_bytes())
    return pd.read_csv(p, sep=";", encoding="latin-1", dtype=str, on_bad_lines="skip")


def limpar(df: pd.DataFrame, ano: int) -> pd.DataFrame:
    """Seleciona, renomeia e normaliza colunas; gera URL da foto."""
    presentes = {k: v for k, v in COLUNAS_TSE.items() if k in df.columns}
    ausentes = set(COLUNAS_TSE) - set(presentes)
    if ausentes:
        print(f"  Aviso: colunas ausentes no CSV: {ausentes}")

    df = df.rename(columns=presentes)[list(presentes.values())].copy()

    # Cargo e subcargo
    cargo_upper = df["cargo_tse"].str.strip().str.upper()
    df["cargo"]    = cargo_upper.map(MAPA_CARGOS)
    df["subcargo"] = cargo_upper.map(MAPA_SUBCARGO)
    df = df.dropna(subset=["cargo"])

    # Campos de texto
    df["nome_urna"]    = df["nome_urna"].str.strip().str.upper()
    df["nome_completo"] = df["nome_completo"].str.strip().str.title()
    df["uf"]           = df["uf"].str.strip().str.upper()
    df["partido"]      = df["partido"].str.strip()
    df["situacao"]     = df["situacao"].str.strip()

    # Número eleitoral como int Python nativo (evita erro de serialização JSON)
    df["numero_eleitoral"] = (
        pd.to_numeric(df["numero_eleitoral"], errors="coerce")
        .dropna()
        .astype(int)
    )

    # Situação apta
    df["situacao_apta"] = df["situacao"].str.upper().isin(SITUACOES_APTAS)

    # Ano eleitoral
    df["ano_eleicao"] = ano

    # URL da foto usando CD_ELEICAO que vem no próprio CSV do TSE
    if "cd_eleicao" in df.columns:
        df["url_foto"] = df.apply(
            lambda r: (
                f"https://divulgacandcontas.tse.jus.br/candidaturas/oficial/{ano}"
                f"/BR/{r['uf']}/{r['cd_eleicao']}/candidatos/{r['sq_candidato']}/foto.jpeg"
                if pd.notna(r.get("cd_eleicao")) and pd.notna(r.get("sq_candidato"))
                else None
            ),
            axis=1,
        )
    else:
        df["url_foto"] = None

    colunas_finais = [
        "sq_candidato", "nome_urna", "nome_completo", "numero_eleitoral",
        "cargo", "subcargo", "uf", "partido", "situacao", "situacao_apta",
        "url_foto", "ano_eleicao",
    ]
    return df[[c for c in colunas_finais if c in df.columns]]


def gravar(df: pd.DataFrame, client: Client, lote: int = 500) -> None:
    """Faz upsert dos candidatos normalizados no Supabase em lotes."""
    # TSE pode ter múltiplas linhas para o mesmo candidato — fica com a última
    df = df.drop_duplicates(subset=["sq_candidato", "ano_eleicao"], keep="last").reset_index(drop=True)

    def _limpar(v: object) -> object:
        if isinstance(v, float) and math.isnan(v):
            return None
        return v

    registros = [
        {k: _limpar(v) for k, v in row.items()}
        for row in df.to_dict(orient="records")
    ]
    total = len(registros)

    for inicio in range(0, total, lote):
        fatia = registros[inicio : inicio + lote]
        client.table("candidatos").upsert(
            fatia,
            on_conflict="sq_candidato,ano_eleicao",
        ).execute()
        print(f"  {min(inicio + lote, total)}/{total} registros gravados...")

    print(f"  Concluido: {total} registros no Supabase")


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingestão TSE -> Supabase")
    parser.add_argument("--ano", type=int, default=2022, help="Ano eleitoral")
    parser.add_argument("--uf",  type=str, default=None,  help="UF (ex: SP). Omita para todas.")
    parser.add_argument("--arquivo", type=str, default=None, help="ZIP ou CSV local do TSE")
    args = parser.parse_args()

    client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

    if args.arquivo:
        print(f"Lendo arquivo local: {args.arquivo}")
        df_raw = ler_arquivo(args.arquivo)
    else:
        df_raw = baixar(args.ano)

    df = limpar(df_raw, args.ano)

    if args.uf:
        df = df[df["uf"] == args.uf.upper()]
        print(f"Filtrando UF: {args.uf.upper()} ({len(df)} registros)")

    gravar(df, client)
    print("Concluido.")


if __name__ == "__main__":
    main()

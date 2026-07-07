"""
Ingestão de dados do TSE — Candidatos 2022
Fonte: https://dadosabertos.tse.jus.br/dataset/candidatos-2022

Uso:
    python ingesta_tse.py [--ufs SP RJ MG ...] [--dry-run]

Sem --ufs processa todas as 27 UFs + BR (presidência).
"""

import argparse
import io
import os
import sys
import zipfile
from pathlib import Path

import pandas as pd
import requests
from dotenv import load_dotenv
from supabase import create_client

load_dotenv(Path(__file__).parent.parent.parent / ".env.local")
SUPABASE_URL = os.environ.get("NEXT_PUBLIC_SUPABASE_URL", "")

# ---------------------------------------------------------------------------
# Configuração
# ---------------------------------------------------------------------------

CANDIDATOS_ZIP_URL = (
    "https://cdn.tse.jus.br/estatistica/sead/odsele/consulta_cand/"
    "consulta_cand_2022.zip"
)
BENS_ZIP_URL = (
    "https://cdn.tse.jus.br/estatistica/sead/odsele/bem_candidato/"
    "bem_candidato_2022.zip"
)

# URL pública da foto no Supabase Storage (bucket fotos-candidatos, arquivo {nr_sequencial}.jpg)
# Defina NEXT_PUBLIC_SUPABASE_URL no .env.local — ex: https://abc.supabase.co
FOTO_BUCKET = "fotos-candidatos"

ALL_UFS = [
    "AC","AL","AP","AM","BA","CE","DF","ES","GO",
    "MA","MT","MS","MG","PA","PB","PR","PE","PI",
    "RJ","RN","RS","RO","RR","SC","SP","SE","TO",
]

# DS_CARGO (TSE) → slug do projeto
CARGO_MAP = {
    "PRESIDENTE":        "presidente",
    "VICE-PRESIDENTE":   "vice-presidente",
    "GOVERNADOR":        "governador",
    "VICE-GOVERNADOR":   "vice-governador",
    "SENADOR":           "senador",
    "DEPUTADO FEDERAL":  "deputado-federal",
    "DEPUTADO ESTADUAL": "deputado-estadual",
    "DEPUTADO DISTRITAL":"deputado-estadual",
}

# Cargo do vice → cargo do titular (para o pairing)
VICE_PARA_TITULAR = {
    "vice-presidente": "presidente",
    "vice-governador": "governador",
}

SITUACOES_APTAS = {"APTO", "DEFERIDO", "DEFERIDO COM RECURSO"}

OUTPUT_DIR = Path(__file__).parent.parent / "output"

# ---------------------------------------------------------------------------
# Download
# ---------------------------------------------------------------------------

def baixar_zip(url: str, descricao: str) -> zipfile.ZipFile:
    print(f"  Baixando {descricao}...", end=" ", flush=True)
    resp = requests.get(url, timeout=180)
    resp.raise_for_status()
    print(f"{len(resp.content) // 1024} KB")
    return zipfile.ZipFile(io.BytesIO(resp.content))


def ler_csv_do_zip(zf: zipfile.ZipFile, filename: str) -> pd.DataFrame:
    with zf.open(filename) as f:
        return pd.read_csv(
            f,
            sep=";",
            encoding="latin-1",
            dtype=str,
            on_bad_lines="skip",
        )

# ---------------------------------------------------------------------------
# Normalização de candidatos
# ---------------------------------------------------------------------------

def col(df: pd.DataFrame, nome: str, default: str = "") -> pd.Series:
    """Retorna coluna do df ou série de strings vazias se não existir."""
    return df[nome] if nome in df.columns else pd.Series(default, index=df.index)


def normalizar_candidatos(df: pd.DataFrame) -> pd.DataFrame:
    # Filtra cargos relevantes
    df = df[df["DS_CARGO"].str.upper().isin(CARGO_MAP)].copy()

    df["_cargo_tse"]    = df["DS_CARGO"].str.strip().str.upper()
    df["cargo"]         = df["_cargo_tse"].map(CARGO_MAP)
    df["uf"]            = df["SG_UF"].str.strip().str.upper()
    df["nome_urna"]     = df["NM_URNA_CANDIDATO"].str.strip().str.upper()
    df["nome_completo"] = df["NM_CANDIDATO"].str.strip().str.upper()
    df["nr_candidato"]  = df["NR_CANDIDATO"].str.strip()          # número eleitoral (texto)
    df["numero_eleitoral"] = pd.to_numeric(df["NR_CANDIDATO"], errors="coerce")
    df["nr_sequencial"] = col(df, "SQ_CANDIDATO").str.strip()
    df["partido"]       = df["SG_PARTIDO"].str.strip().str.upper()
    df["coligacao"]     = col(df, "NM_COLIGACAO").fillna("").str.strip()
    df["situacao"]      = df["DS_SITUACAO_CANDIDATURA"].str.strip().str.upper()
    df["situacao_apta"] = df["situacao"].isin(SITUACOES_APTAS)
    df["grau_instrucao"]= col(df, "DS_GRAU_INSTRUCAO").fillna("").str.strip()
    df["ocupacao"]      = col(df, "DS_OCUPACAO").fillna("").str.strip()
    df["genero"]        = col(df, "DS_GENERO").fillna("").str.strip().str.upper()
    df["cor_raca"]      = col(df, "DS_COR_RACA").fillna("").str.strip().str.upper()
    df["email_campanha"]= col(df, "DS_EMAIL").fillna("").str.strip().str.lower()

    # Data de nascimento DD/MM/AAAA → AAAA-MM-DD
    if "DT_NASCIMENTO" in df.columns:
        df["data_nascimento"] = pd.to_datetime(
            df["DT_NASCIMENTO"], format="%d/%m/%Y", errors="coerce"
        ).dt.strftime("%Y-%m-%d")
    else:
        df["data_nascimento"] = None

    # Presidente: UF vira BR
    df.loc[df["cargo"] == "presidente", "uf"] = "BR"

    # URL da foto no Supabase Storage
    base_storage = f"{SUPABASE_URL.rstrip('/')}/storage/v1/object/public/{FOTO_BUCKET}"
    df["url_foto"] = df["nr_sequencial"].apply(
        lambda sq: f"{base_storage}/{sq}.jpg" if sq else ""
    )

    # Redes sociais não estão no CSV (enriquecimento futuro via API DivulgaCand)
    for col_rs in ("url_facebook", "url_instagram", "url_twitter", "url_youtube"):
        df[col_rs] = ""

    df["total_bens"]         = 0.0
    df["nome_vice"]          = ""
    df["nr_sequencial_vice"] = ""
    df["url_foto_vice"]      = ""

    return df.dropna(subset=["numero_eleitoral"]).reset_index(drop=True)


def parear_vices(df: pd.DataFrame) -> pd.DataFrame:
    """
    Para presidente e governador, os vices são linhas separadas no CSV do TSE.
    Este método:
      1. Mescla o nome/foto do vice na linha do titular (para exibir o par na UI)
      2. Mantém as linhas dos vices no dataframe (cargo vice-presidente/vice-governador)
         para que seus bens e redes sociais sejam ingeridos normalmente.
    """
    mask_vice = df["_cargo_tse"].isin({"VICE-PRESIDENTE", "VICE-GOVERNADOR"})
    titulares = df[~mask_vice].copy()
    vices     = df[mask_vice].copy()

    # Monta tabela de pairing: ajusta cargo do vice para o cargo do titular antes do merge
    vice_info = vices[["cargo","uf","numero_eleitoral","nome_urna","nr_sequencial","url_foto"]].copy()
    vice_info["cargo"] = vice_info["cargo"].map(VICE_PARA_TITULAR)
    vice_info = vice_info.rename(columns={
        "nome_urna":     "nome_vice",
        "nr_sequencial": "nr_sequencial_vice",
        "url_foto":      "url_foto_vice",
    })

    titulares = titulares.merge(
        vice_info,
        on=["cargo","uf","numero_eleitoral"],
        how="left",
        suffixes=("","_v"),
    )

    # Sobrescreve as colunas de vice com os valores do merge (se existirem)
    for c in ("nome_vice","nr_sequencial_vice","url_foto_vice"):
        col_v = c + "_v"
        if col_v in titulares.columns:
            titulares[c] = titulares[col_v].fillna("").where(
                titulares[col_v].notna(), titulares[c]
            )
            titulares.drop(columns=[col_v], inplace=True)

    # Vices ficam no banco com seu próprio cargo (vice-presidente/vice-governador)
    # para que bens e redes sociais possam ser consultados independentemente.
    return pd.concat([titulares, vices], ignore_index=True).reset_index(drop=True)


# ---------------------------------------------------------------------------
# Normalização de bens
# ---------------------------------------------------------------------------

def normalizar_bens(df_bens_raw: pd.DataFrame, df_cand: pd.DataFrame) -> pd.DataFrame:
    """
    Bens não têm NR_CANDIDATO/DS_CARGO — usam SQ_CANDIDATO como chave.
    Fazemos join com candidatos pelo sequencial para obter cargo/uf/numero_eleitoral.
    """
    df = df_bens_raw.copy()

    df["nr_sequencial"] = col(df, "SQ_CANDIDATO").str.strip()
    df["ordem"]         = pd.to_numeric(col(df, "NR_ORDEM_BEM_CANDIDATO", "0"), errors="coerce").fillna(0).astype(int)
    df["descricao"]     = col(df, "DS_BEM_CANDIDATO").fillna("").str.strip()
    df["valor"]         = (
        col(df, "VR_BEM_CANDIDATO", "0")
        .str.replace(",", ".", regex=False)
        .pipe(pd.to_numeric, errors="coerce")
        .fillna(0)
    )

    # Join com candidatos para obter cargo/uf/numero_eleitoral
    chave_cand = df_cand[["nr_sequencial","cargo","uf","numero_eleitoral"]].drop_duplicates("nr_sequencial")
    df = df.merge(chave_cand, on="nr_sequencial", how="inner")

    return (
        df[["numero_eleitoral","cargo","uf","ordem","descricao","valor"]]
        .dropna(subset=["numero_eleitoral","cargo"])
        .reset_index(drop=True)
    )


# ---------------------------------------------------------------------------
# Carga no Supabase
# ---------------------------------------------------------------------------

def upsert_em_lotes(client, tabela: str, registros: list[dict], conflict: str, chunksize: int = 500):
    total = len(registros)
    for i in range(0, total, chunksize):
        lote = registros[i:i + chunksize]
        client.table(tabela).upsert(lote, on_conflict=conflict).execute()
        print(f"    {min(i + chunksize, total)}/{total}", end="\r")
    print()


# ---------------------------------------------------------------------------
# Pipeline principal
# ---------------------------------------------------------------------------

def nome_arquivo_uf(zf: zipfile.ZipFile, prefixo: str, uf: str) -> str | None:
    """Localiza o arquivo CSV de uma UF dentro do zip."""
    candidatos = [n for n in zf.namelist() if n.endswith(".csv")]
    # Tenta match exato pela UF (ex: _SP. ou _BR.)
    for nome in candidatos:
        stem = nome.upper().replace(".CSV", "")
        if stem.endswith(f"_{uf}"):
            return nome
    return None


def processar(ufs: list[str], dry_run: bool):
    load_dotenv(Path(__file__).parent.parent.parent / ".env.local")

    supabase_url = os.environ.get("NEXT_PUBLIC_SUPABASE_URL")
    service_key  = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")

    if not dry_run and (not supabase_url or not service_key):
        sys.exit("Erro: defina NEXT_PUBLIC_SUPABASE_URL e SUPABASE_SERVICE_ROLE_KEY no .env.local")

    client = create_client(supabase_url, service_key) if not dry_run else None

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print("\n=== Download dos arquivos TSE ===")
    zip_cand = baixar_zip(CANDIDATOS_ZIP_URL, "candidatos")
    zip_bens = baixar_zip(BENS_ZIP_URL, "bens")

    ufs_alvo = ufs if ufs else ALL_UFS + ["BR"]

    todos_candidatos: list[pd.DataFrame] = []
    todos_bens:       list[pd.DataFrame] = []

    for uf in ufs_alvo:
        print(f"\n--- UF: {uf} ---")

        arq_cand = nome_arquivo_uf(zip_cand, "consulta_cand_2022", uf)
        arq_bens = nome_arquivo_uf(zip_bens, "bem_candidato_2022", uf)

        if not arq_cand:
            print(f"  Arquivo de candidatos não encontrado para {uf}, pulando.")
            continue

        df_cand_raw = ler_csv_do_zip(zip_cand, arq_cand)
        df_cand = normalizar_candidatos(df_cand_raw)
        df_cand = parear_vices(df_cand)
        print(f"  Candidatos: {len(df_cand)}")
        todos_candidatos.append(df_cand)

        if arq_bens:
            df_bens_raw = ler_csv_do_zip(zip_bens, arq_bens)
            df_bens = normalizar_bens(df_bens_raw, df_cand)
            print(f"  Bens: {len(df_bens)}")
            todos_bens.append(df_bens)
        else:
            print(f"  Bens não encontrados para {uf}.")

    df_cand_final = pd.concat(todos_candidatos, ignore_index=True) if todos_candidatos else pd.DataFrame()
    df_bens_final = pd.concat(todos_bens, ignore_index=True) if todos_bens else pd.DataFrame()

    # Deduplica dentro de cada dataset
    antes = len(df_cand_final)
    df_cand_final = df_cand_final.drop_duplicates(subset=["cargo","uf","numero_eleitoral"], keep="last").reset_index(drop=True)
    df_bens_final = df_bens_final.drop_duplicates(subset=["cargo","uf","numero_eleitoral","ordem"], keep="last").reset_index(drop=True)
    if antes != len(df_cand_final):
        print(f"  Deduplicados: {antes} -> {len(df_cand_final)} candidatos")

    # Pre-calcula total_bens e incorpora em df_cand_final (evita UPDATEs individuais depois)
    if not df_bens_final.empty:
        totais = (
            df_bens_final.groupby(["cargo","uf","numero_eleitoral"])["valor"]
            .sum().reset_index().rename(columns={"valor": "total_bens"})
        )
        df_cand_final = df_cand_final.drop(columns=["total_bens"], errors="ignore")
        df_cand_final = df_cand_final.merge(totais, on=["cargo","uf","numero_eleitoral"], how="left")
        df_cand_final["total_bens"] = df_cand_final["total_bens"].fillna(0.0)

    print(f"\nTotal: {len(df_cand_final)} candidatos, {len(df_bens_final)} bens")

    # Salva JSONs locais
    df_cand_final.drop(columns=["_cargo_tse","nr_candidato"], errors="ignore").to_json(
        OUTPUT_DIR / "candidatos.json", orient="records", force_ascii=False, indent=2
    )
    df_bens_final.to_json(
        OUTPUT_DIR / "bens.json", orient="records", force_ascii=False, indent=2
    )
    print(f"JSONs salvos em {OUTPUT_DIR}")

    if dry_run:
        print("\n[DRY RUN] Nenhum dado enviado ao Supabase.")
        # Mostra amostra
        cols_amostra = ["nome_urna","cargo","uf","partido","numero_eleitoral","situacao_apta","nome_vice"]
        print(df_cand_final[[c for c in cols_amostra if c in df_cand_final.columns]].head(10).to_string())
        return

    # Colunas que vão para o banco (exclui colunas auxiliares)
    colunas_db = [
        "nome_urna","nome_completo","numero_eleitoral","nr_sequencial",
        "cargo","uf","partido","coligacao","situacao","situacao_apta",
        "nome_vice","nr_sequencial_vice","url_foto","url_foto_vice",
        "data_nascimento","grau_instrucao","ocupacao","genero","cor_raca",
        "email_campanha","url_facebook","url_instagram","url_twitter","url_youtube","total_bens",
    ]
    df_para_db = df_cand_final[[c for c in colunas_db if c in df_cand_final.columns]]

    print(f"\n=== Enviando candidatos ({len(df_para_db)}) ao Supabase ===")
    registros_cand = [
        {k: (None if pd.isna(v) else v) for k, v in row.items()}
        for row in df_para_db.to_dict(orient="records")
    ]
    upsert_em_lotes(client, "candidatos", registros_cand, "cargo,uf,numero_eleitoral")

    print(f"=== Enviando bens ({len(df_bens_final)}) ao Supabase ===")
    registros_bens = [
        {k: (None if pd.isna(v) else v) for k, v in row.items()}
        for row in df_bens_final.to_dict(orient="records")
    ]
    upsert_em_lotes(client, "bens_candidatos", registros_bens, "cargo,uf,numero_eleitoral,ordem")

    print("\nIngestão concluída.")


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingestão TSE 2022 → Supabase")
    parser.add_argument("--ufs", nargs="*", metavar="UF", help="UFs a processar (padrão: todas)")
    parser.add_argument("--dry-run", action="store_true", help="Normaliza mas não envia ao Supabase")
    args = parser.parse_args()

    processar(ufs=[u.upper() for u in args.ufs] if args.ufs else [], dry_run=args.dry_run)

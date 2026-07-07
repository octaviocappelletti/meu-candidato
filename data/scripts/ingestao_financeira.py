"""
Ingestão financeira TSE 2022 — Protótipo
Fonte: https://cdn.tse.jus.br/estatistica/sead/odsele/prestacao_contas/
       prestacao_de_contas_eleitorais_candidatos_2022.zip

Uso:
    python ingestao_financeira.py [--ufs SP RJ ...] [--dry-run]

Sem --ufs processa todas as UFs + BR (presidência).

Saída:
  data/output/financeiro/{uf}.json  — arquivo canônico
  public/financeiro/{uf}.json       — servido pelo Next.js (arquivo estático)

Cada JSON é um objeto indexado por sq_candidato (= SQ_CANDIDATO do TSE,
mesmo valor que nr_sequencial na tabela candidatos do Supabase).

AVISO LGPD: CPF e nome de doadores NÃO são exportados — apenas contagem.
"""

import argparse
import json
import zipfile
from pathlib import Path

import pandas as pd
import requests

# ---------------------------------------------------------------------------
# Configuração
# ---------------------------------------------------------------------------

ZIP_URL = (
    "https://cdn.tse.jus.br/estatistica/sead/odsele/prestacao_contas/"
    "prestacao_de_contas_eleitorais_candidatos_2022.zip"
)

ROOT_DIR    = Path(__file__).parent.parent.parent
CACHE_DIR   = Path(__file__).parent.parent / ".cache"
OUTPUT_JSON = ROOT_DIR / "data" / "output" / "financeiro"
OUTPUT_PUB  = ROOT_DIR / "public" / "financeiro"

ALL_UFS = [
    "AC","AL","AP","AM","BA","CE","DF","ES","GO",
    "MA","MT","MS","MG","PA","PB","PR","PE","PI",
    "RJ","RN","RS","RO","RR","SC","SP","SE","TO",
    "BR",
]

CARGO_MAP = {
    "PRESIDENTE":         "presidente",
    "VICE-PRESIDENTE":    "vice-presidente",
    "GOVERNADOR":         "governador",
    "VICE-GOVERNADOR":    "vice-governador",
    "SENADOR":            "senador",
    "DEPUTADO FEDERAL":   "deputado-federal",
    "DEPUTADO ESTADUAL":  "deputado-estadual",
    "DEPUTADO DISTRITAL": "deputado-estadual",
}

# DS_FONTE_RECEITA → grupo
FONTES_PUBLICAS = {"FUNDO ESPECIAL", "FUNDO PARTIDARIO"}

# DS_ORIGEM_RECEITA → grupo (quando DS_FONTE_RECEITA == "OUTROS RECURSOS")
ORIGENS_PROPRIAS = {"Recursos próprios"}
ORIGENS_PF       = {"Recursos de pessoas físicas"}

# DS_ORIGEM_DESPESA — excluir transferências entre contas, devoluções e saques
EXCLUIR_DESPESA_RE = r"devolução|transferência entre contas|saque de fundo"

# ---------------------------------------------------------------------------
# Download / cache
# ---------------------------------------------------------------------------

def obter_zip() -> zipfile.ZipFile:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_path = CACHE_DIR / "prestacao_contas_2022.zip"
    if cache_path.exists():
        print(f"  Usando cache: {cache_path}")
        return zipfile.ZipFile(cache_path)
    print("  Baixando ZIP do TSE...", end=" ", flush=True)
    resp = requests.get(ZIP_URL, timeout=600)
    resp.raise_for_status()
    cache_path.write_bytes(resp.content)
    print(f"ok ({len(resp.content) // 1024 // 1024} MB)")
    return zipfile.ZipFile(cache_path)


def achar(nomes: list[str], prefixo: str, uf: str) -> str | None:
    sufixo = "BRASIL" if uf == "BR" else uf
    for n in nomes:
        stem = n.upper().replace(".CSV", "")
        if prefixo.upper() in stem and stem.endswith(f"_{sufixo}"):
            return n
    return None


# ---------------------------------------------------------------------------
# Leitura de CSV do ZIP
# ---------------------------------------------------------------------------

def ler_csv(zf: zipfile.ZipFile, nome: str, cols: list[str]) -> pd.DataFrame:
    cols_set = set(cols)
    with zf.open(nome) as f:
        df = pd.read_csv(
            f,
            sep=";",
            encoding="latin-1",
            dtype=str,
            on_bad_lines="skip",
            usecols=lambda c: c in cols_set,
        )
    for c in cols:
        if c not in df.columns:
            df[c] = ""
    return df[cols].copy()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def para_float(s: pd.Series) -> pd.Series:
    """Converte string no formato brasileiro (1.234,56) para float."""
    return (
        s.str.strip()
         .str.replace(".", "", regex=False)
         .str.replace(",", ".", regex=False)
         .pipe(pd.to_numeric, errors="coerce")
         .fillna(0.0)
    )


def max_data_iso(s: pd.Series) -> str:
    """Retorna a maior data DD/MM/AAAA como AAAA-MM-DD."""
    parsed = pd.to_datetime(s, format="%d/%m/%Y", errors="coerce")
    mx = parsed.max()
    return "" if pd.isna(mx) else mx.strftime("%Y-%m-%d")


def classificar_origem(fonte: str, origem: str) -> str:
    f = (fonte or "").strip()
    o = (origem or "").strip()
    if f in FONTES_PUBLICAS:
        return "publico"
    if o in ORIGENS_PROPRIAS:
        return "proprio"
    if o in ORIGENS_PF:
        return "pessoa_fisica"
    return "outros"


# ---------------------------------------------------------------------------
# Agregados puros (facilitam testes unitários)
# ---------------------------------------------------------------------------

CAND_INFO_COLS = ["SQ_CANDIDATO", "NR_CANDIDATO", "NM_CANDIDATO",
                  "SG_UF", "SG_PARTIDO", "DS_CARGO"]
MAPA_COLS      = ["SQ_PRESTADOR_CONTAS"] + CAND_INFO_COLS


def agregar_receitas(df: pd.DataFrame) -> pd.DataFrame:
    """
    Entrada: receitas_candidatos com colunas SQ_CANDIDATO, VR_RECEITA,
      DS_FONTE_RECEITA, DS_ORIGEM_RECEITA, NR_CPF_CNPJ_DOADOR, DT_PRESTACAO_CONTAS.
    Saída: um DataFrame indexado por SQ_CANDIDATO com colunas de totais.
    """
    d = df.copy()
    d["VR_RECEITA"] = para_float(d["VR_RECEITA"])
    d["grupo"] = d.apply(
        lambda r: classificar_origem(r["DS_FONTE_RECEITA"], r["DS_ORIGEM_RECEITA"]),
        axis=1,
    )

    total = d.groupby("SQ_CANDIDATO")["VR_RECEITA"].sum().rename("total_arrecadado")

    doadores = (
        d[d["NR_CPF_CNPJ_DOADOR"].str.strip().ne("")]
        .groupby("SQ_CANDIDATO")["NR_CPF_CNPJ_DOADOR"]
        .nunique()
        .rename("num_doadores")
    )

    por_grupo = (
        d.groupby(["SQ_CANDIDATO", "grupo"])["VR_RECEITA"]
        .sum()
        .unstack(fill_value=0.0)
        .reindex(columns=["publico", "proprio", "pessoa_fisica", "outros"], fill_value=0.0)
        .add_prefix("rec_")
    )

    data_ref = (
        d.groupby("SQ_CANDIDATO")["DT_PRESTACAO_CONTAS"]
        .apply(max_data_iso)
        .rename("data_referencia")
    )

    return pd.concat([total, doadores, por_grupo, data_ref], axis=1).reset_index()


def agregar_despesas(
    df_pagas: pd.DataFrame,
    mapa: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Entrada:
      df_pagas: despesas_pagas com SQ_PRESTADOR_CONTAS, VR_PAGTO_DESPESA,
                DS_ORIGEM_DESPESA.
      mapa: SQ_PRESTADOR_CONTAS → SQ_CANDIDATO (e mais metadados).
    Saída: (total_por_candidato, breakdown_por_categoria).
    Exclui transferências entre contas, devoluções e saques.
    """
    d = df_pagas.copy()
    excl = d["DS_ORIGEM_DESPESA"].str.contains(
        EXCLUIR_DESPESA_RE, case=False, na=False, regex=True
    )
    d = d[~excl]
    d = d.merge(mapa[["SQ_PRESTADOR_CONTAS", "SQ_CANDIDATO"]], on="SQ_PRESTADOR_CONTAS", how="inner")
    d["VR_PAGTO_DESPESA"] = para_float(d["VR_PAGTO_DESPESA"])

    totais = (
        d.groupby("SQ_CANDIDATO")["VR_PAGTO_DESPESA"]
        .sum()
        .rename("total_gasto")
        .reset_index()
    )
    cats = (
        d.groupby(["SQ_CANDIDATO", "DS_ORIGEM_DESPESA"])["VR_PAGTO_DESPESA"]
        .sum()
        .reset_index()
        .sort_values("VR_PAGTO_DESPESA", ascending=False)
    )
    return totais, cats


# ---------------------------------------------------------------------------
# Montagem do JSON final
# ---------------------------------------------------------------------------

def montar_registros(
    info: pd.DataFrame,
    rec: pd.DataFrame,
    desp_tot: pd.DataFrame,
    desp_cat: pd.DataFrame,
) -> dict[str, dict]:
    merged = (
        info
        .merge(rec,      on="SQ_CANDIDATO", how="left")
        .merge(desp_tot, on="SQ_CANDIDATO", how="left")
    )

    def col_float(nome: str) -> pd.Series:
        return merged[nome].fillna(0.0) if nome in merged.columns else pd.Series(0.0, index=merged.index)

    merged["total_arrecadado"] = col_float("total_arrecadado")
    merged["total_gasto"]      = col_float("total_gasto")
    merged["num_doadores"]     = col_float("num_doadores").astype(int)
    for g in ["publico", "proprio", "pessoa_fisica", "outros"]:
        merged[f"rec_{g}"] = col_float(f"rec_{g}")
    if "data_referencia" not in merged.columns:
        merged["data_referencia"] = ""

    # Pré-índice de categorias por SQ_CANDIDATO
    cats_idx: dict = {}
    if not desp_cat.empty:
        for sq, grp in desp_cat.groupby("SQ_CANDIDATO"):
            cats_idx[sq] = [
                {"categoria": r["DS_ORIGEM_DESPESA"], "valor": round(float(r["VR_PAGTO_DESPESA"]), 2)}
                for _, r in grp.head(10).iterrows()
            ]

    resultado: dict[str, dict] = {}
    for _, row in merged.iterrows():
        sq  = str(row["SQ_CANDIDATO"]).strip()
        tot = float(row["total_arrecadado"])

        def pct(v: float) -> float:
            return round(v / tot * 100, 2) if tot > 0 else 0.0

        pub  = float(row["rec_publico"])
        prop = float(row["rec_proprio"])
        pf   = float(row["rec_pessoa_fisica"])
        out  = float(row["rec_outros"])

        nr_raw = str(row.get("NR_CANDIDATO", "")).strip()
        resultado[sq] = {
            "sq_candidato":     sq,
            "nr_candidato":     int(nr_raw) if nr_raw.isdigit() else None,
            "nm_candidato":     str(row.get("NM_CANDIDATO", "")).strip(),
            "cargo":            str(row.get("cargo_slug", "")),
            "uf":               str(row.get("SG_UF", "")),
            "partido":          str(row.get("SG_PARTIDO", "")),
            "total_arrecadado": round(tot, 2),
            "total_gasto":      round(float(row["total_gasto"]), 2),
            "num_doadores":     int(row["num_doadores"]),
            "origem_recursos": {
                "publico":       {"valor": round(pub,  2), "pct": pct(pub)},
                "proprio":       {"valor": round(prop, 2), "pct": pct(prop)},
                "pessoa_fisica": {"valor": round(pf,   2), "pct": pct(pf)},
                "outros":        {"valor": round(out,  2), "pct": pct(out)},
            },
            "pct_autofinanciamento": pct(prop),
            "despesas_por_categoria": cats_idx.get(row["SQ_CANDIDATO"], []),
            "data_referencia": str(row.get("data_referencia", "") or ""),
        }

    return resultado


# ---------------------------------------------------------------------------
# Processamento por UF
# ---------------------------------------------------------------------------

def processar_uf(zf: zipfile.ZipFile, nomes: list[str], uf: str) -> dict[str, dict]:
    arq_rec   = achar(nomes, "receitas_candidatos_2022",             uf)
    arq_cont  = achar(nomes, "despesas_contratadas_candidatos_2022", uf)
    arq_pagas = achar(nomes, "despesas_pagas_candidatos_2022",       uf)

    if not arq_rec and not arq_cont:
        print("  Arquivos não encontrados, pulando.")
        return {}

    mapa_parts: list[pd.DataFrame] = []

    # ── Receitas ──────────────────────────────────────────────────────────
    rec_raw = None
    if arq_rec:
        rec_raw = ler_csv(zf, arq_rec, MAPA_COLS + [
            "VR_RECEITA", "DS_FONTE_RECEITA", "DS_ORIGEM_RECEITA",
            "NR_CPF_CNPJ_DOADOR", "DT_PRESTACAO_CONTAS",
        ])
        rec_raw["cargo_slug"] = rec_raw["DS_CARGO"].str.strip().str.upper().map(CARGO_MAP)
        mapa_parts.append(rec_raw[MAPA_COLS + ["cargo_slug"]])
        print(f"  Receitas: {len(rec_raw):,} linhas")

    # ── Despesas contratadas (enriquece o mapa de candidatos) ─────────────
    if arq_cont:
        cont = ler_csv(zf, arq_cont, MAPA_COLS)
        cont["cargo_slug"] = cont["DS_CARGO"].str.strip().str.upper().map(CARGO_MAP)
        mapa_parts.append(cont[MAPA_COLS + ["cargo_slug"]])

    if not mapa_parts:
        print("  Sem dados suficientes para o mapa de candidatos.")
        return {}

    mapa = (
        pd.concat(mapa_parts, ignore_index=True)
        .drop_duplicates("SQ_PRESTADOR_CONTAS")
        .reset_index(drop=True)
    )

    # ── Receitas — agrega ─────────────────────────────────────────────────
    rec_agg = pd.DataFrame({"SQ_CANDIDATO": pd.Series(dtype=str)})
    if rec_raw is not None and not rec_raw.empty:
        rec_agg = agregar_receitas(rec_raw)

    # ── Despesas pagas ────────────────────────────────────────────────────
    desp_tot = pd.DataFrame(columns=["SQ_CANDIDATO", "total_gasto"])
    desp_cat = pd.DataFrame(columns=["SQ_CANDIDATO", "DS_ORIGEM_DESPESA", "VR_PAGTO_DESPESA"])
    if arq_pagas:
        pagas = ler_csv(zf, arq_pagas, [
            "SQ_PRESTADOR_CONTAS", "VR_PAGTO_DESPESA",
            "DS_ORIGEM_DESPESA", "DT_PRESTACAO_CONTAS",
        ])
        print(f"  Despesas pagas: {len(pagas):,} linhas")
        desp_tot, desp_cat = agregar_despesas(pagas, mapa)

    # ── Info base dos candidatos ──────────────────────────────────────────
    info = (
        mapa[CAND_INFO_COLS + ["cargo_slug"]]
        .drop_duplicates("SQ_CANDIDATO")
        .reset_index(drop=True)
    )

    resultado = montar_registros(info, rec_agg, desp_tot, desp_cat)
    print(f"  Candidatos: {len(resultado):,}")
    return resultado


# ---------------------------------------------------------------------------
# Pipeline principal
# ---------------------------------------------------------------------------

def processar(ufs: list[str], dry_run: bool) -> None:
    if not dry_run:
        OUTPUT_JSON.mkdir(parents=True, exist_ok=True)
        OUTPUT_PUB.mkdir(parents=True, exist_ok=True)

    print("\n=== Obtendo ZIP ===")
    zf    = obter_zip()
    nomes = zf.namelist()

    for uf in (ufs or ALL_UFS):
        print(f"\n--- {uf} ---")
        dados = processar_uf(zf, nomes, uf)
        if not dados:
            continue

        payload = json.dumps(dados, ensure_ascii=False, separators=(",", ":"))

        if dry_run:
            print(f"  [DRY RUN] {len(dados):,} candidatos — não salvo.")
            print(json.dumps(next(iter(dados.values())), ensure_ascii=False, indent=2))
            continue

        uf_lower = uf.lower()
        for destino in (
            OUTPUT_JSON / f"{uf_lower}.json",
            OUTPUT_PUB  / f"{uf_lower}.json",
        ):
            destino.write_text(payload, encoding="utf-8")
        kb = (OUTPUT_PUB / f"{uf_lower}.json").stat().st_size // 1024
        print(f"  Salvo: {uf_lower}.json ({kb} KB)")

    print("\nIngestão financeira concluída.")


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingestão financeira TSE 2022")
    parser.add_argument("--ufs", nargs="*", metavar="UF", help="UFs a processar (padrão: todas + BR)")
    parser.add_argument("--dry-run", action="store_true", help="Processa mas não grava arquivos")
    args = parser.parse_args()
    processar(
        ufs=[u.upper() for u in args.ufs] if args.ufs else [],
        dry_run=args.dry_run,
    )

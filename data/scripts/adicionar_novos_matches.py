"""
adicionar_novos_matches.py

1. Lê sem_match_resultados.csv e valida quais matches são corretos.
2. Gera matches_finais.csv com todos os matches conhecidos (antigos + novos).
3. Busca proposições para os novos parlamentares e atualiza legislativo.json.

Critério de validação automática:
  - Flag == "OK" (mesma UF)
  - Primeira palavra significativa (>3 chars, não-título) do nome_tse
    aparece no nome_api
  - ID não está na lista de falsos positivos conhecidos

Overrides manuais para nomes de apelido (ex: TOINHO = Antonio):
  MANUAL_INCLUDES: {sq_candidato: id_parlamentar}
"""

import csv
import json
import sys
from datetime import date
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).parent))
from ingestao_legislativa import (
    _TITULOS,
    OUTPUT_DIR,
    PUBLIC_DIR,
    agregar_camara,
    buscar_detalhes_paralelo,
    buscar_proposicoes_camara,
    norm,
)

ROOT            = Path(__file__).parent.parent.parent
SEM_MATCH_CSV   = OUTPUT_DIR / "sem_match_resultados.csv"
DEPARA_CSV      = OUTPUT_DIR / "depara.csv"
MATCHES_CSV     = OUTPUT_DIR / "matches_finais.csv"
LEG_JSON_OUT    = OUTPUT_DIR / "legislativo.json"
LEG_JSON_PUB    = PUBLIC_DIR / "legislativo.json"
CAND_JSON       = ROOT / "data" / "output" / "candidatos.json"

# ── Configurações manuais ──────────────────────────────────────────────────────

# IDs da API que são falsos positivos conhecidos — excluir mesmo que passem no filtro
IDS_EXCLUIR = {
    74856,   # Laura Carneiro (não é WALDECK CARNEIRO)
    160600,  # Arthur Oliveira Maia (não é TALITA OLIVEIRA)
    221338,  # Professora Luciene (não é PROFESSOR HOC)
}

# Matches por apelido que não passam no filtro automático mas são corretos
# {sq_candidato: id_parlamentar_na_api}
MANUAL_INCLUDES: dict[str, int] = {
    "270001654159": 220544,  # TOINHO ANDRADE TO/REPUBLICANOS → Antonio Andrade
}


# ── Validação de matches ───────────────────────────────────────────────────────

def confirmar_match(row: dict) -> bool:
    """
    Retorna True se o match em sem_match_resultados.csv é provavelmente correto.
    Só avalia linhas com flag preenchido (o melhor resultado por candidato).
    """
    if not row.get("flag"):
        return False
    if row["flag"] != "OK":
        return False

    id_api = int(row["id_api"])
    if id_api in IDS_EXCLUIR:
        return False

    sq = row["sq_candidato"]
    if sq in MANUAL_INCLUDES:
        return True

    nome_tse = row["nome_tse"]
    nome_api = row["nome_api"]

    palavras_tse = [
        p for p in norm(nome_tse).split()
        if len(p) > 3 and p not in _TITULOS
    ]

    if not palavras_tse:
        # Nome muito curto (TUM, MAX) ou só título: exige UF + partido (score 3)
        return int(row["score_afinidade"]) >= 3

    primeira = palavras_tse[0]
    return primeira in norm(nome_api).split()


# ── Pipeline ───────────────────────────────────────────────────────────────────

def main() -> None:
    # ── 1. Carrega dados ───────────────────────────────────────────────────────
    if not SEM_MATCH_CSV.exists():
        raise FileNotFoundError(f"{SEM_MATCH_CSV} nao encontrado. Execute verificar_sem_match.py primeiro.")

    with open(SEM_MATCH_CSV, encoding="utf-8") as f:
        sem_match_rows = list(csv.DictReader(f))

    with open(DEPARA_CSV, encoding="utf-8") as f:
        depara_rows = list(csv.DictReader(f))

    with open(LEG_JSON_OUT, encoding="utf-8") as f:
        legislativo: dict = json.load(f)

    # Mapa sq_candidato → linha do depara (para pegar nome_tse, uf, partido, cargo)
    depara_por_sq = {r["sq_candidato"]: r for r in depara_rows}

    # ── 2. Filtra matches confirmados ──────────────────────────────────────────
    novos: list[dict] = []  # {sq_candidato, id_api, nome_tse, nome_api, uf, partido, cargo}

    for row in sem_match_rows:
        if not confirmar_match(row):
            continue

        sq = row["sq_candidato"]
        id_api = MANUAL_INCLUDES.get(sq) or int(row["id_api"])
        nome_api = row["nome_api"]

        # Pode ter chegado via override manual (id diferente do CSV)
        if sq in MANUAL_INCLUDES:
            # Busca nome_api correto do resultado que tem esse id
            for r2 in sem_match_rows:
                if r2["sq_candidato"] == sq and int(r2["id_api"]) == id_api:
                    nome_api = r2["nome_api"]
                    break

        dep_info = depara_por_sq.get(sq, {})
        novos.append({
            "sq_candidato": sq,
            "id_api":        id_api,
            "nome_tse":      row["nome_tse"],
            "nome_api":      nome_api,
            "uf":            dep_info.get("uf", row.get("uf_tse", "")),
            "partido":       dep_info.get("partido", row.get("partido_tse", "")),
            "cargo":         dep_info.get("cargo", "deputado-federal"),
        })

    # Adiciona overrides manuais que não aparecem no sem_match_resultados com flag preenchido
    sqs_ja = {n["sq_candidato"] for n in novos}
    for sq, id_api in MANUAL_INCLUDES.items():
        if sq not in sqs_ja:
            dep_info = depara_por_sq.get(sq, {})
            novos.append({
                "sq_candidato": sq,
                "id_api":        id_api,
                "nome_tse":      dep_info.get("nome_tse", ""),
                "nome_api":      f"(override manual id={id_api})",
                "uf":            dep_info.get("uf", ""),
                "partido":       dep_info.get("partido", ""),
                "cargo":         dep_info.get("cargo", "deputado-federal"),
            })

    print(f"Novos matches confirmados: {len(novos)}")
    for n in novos:
        print(f"  {n['nome_tse']:<42} {n['uf']}/{n['partido']:<15} -> id={n['id_api']} {n['nome_api']}")

    # ── 3. Gera matches_finais.csv ─────────────────────────────────────────────
    ja_ok = [r for r in depara_rows if r["status"] != "sem_match"]

    linhas_finais: list[dict] = []
    for r in ja_ok:
        linhas_finais.append({
            "sq_candidato":   r["sq_candidato"],
            "nome_tse":       r["nome_tse"],
            "uf":             r["uf"],
            "partido":        r["partido"],
            "cargo":          r["cargo"],
            "id_parlamentar": r["id_parlamentar"],
            "nome_parlamentar": r["nome_parlamentar"],
            "confianca":      r["confianca"],
            "status":         r["status"],
            "metodo":         r["metodo"],
        })

    for n in novos:
        linhas_finais.append({
            "sq_candidato":   n["sq_candidato"],
            "nome_tse":       n["nome_tse"],
            "uf":             n["uf"],
            "partido":        n["partido"],
            "cargo":          n["cargo"],
            "id_parlamentar": str(n["id_api"]),
            "nome_parlamentar": n["nome_api"],
            "confianca":      "0.80",
            "status":         "nome_api_ok",
            "metodo":         "nome_busca",
        })

    with open(MATCHES_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(linhas_finais[0].keys()))
        writer.writeheader()
        writer.writerows(linhas_finais)

    ja_ok_count = len(ja_ok)
    print(f"\nmatches_finais.csv: {len(linhas_finais)} total  ({ja_ok_count} anteriores + {len(novos)} novos)")
    print(f"  -> {MATCHES_CSV}")

    # ── 4. Busca proposições dos novos matches e atualiza legislativo.json ─────
    session = requests.Session()
    session.headers.update({"Accept": "application/json"})

    ja_no_json = set(legislativo.keys())
    pendentes = [n for n in novos if n["sq_candidato"] not in ja_no_json]
    print(f"\nNovos a processar (não estão no JSON atual): {len(pendentes)}")

    for i, n in enumerate(pendentes, 1):
        sq     = n["sq_candidato"]
        id_dep = n["id_api"]
        nome   = n["nome_tse"]
        print(f"  [{i:>2}/{len(pendentes)}] {nome} (id={id_dep})")

        try:
            props    = buscar_proposicoes_camara(session, id_dep)
            detalhes = buscar_detalhes_paralelo([p["id"] for p in props])
            agg      = agregar_camara(props, detalhes)
        except Exception as exc:
            print(f"    [erro] {exc} — pulando")
            continue

        legislativo[sq] = {
            "sq_candidato":    sq,
            "nome_urna":       nome,
            "cargo_pretendido": n["cargo"],
            "uf":              n["uf"],
            "partido":         n["partido"],
            "casa":            "camara",
            "id_parlamentar":  id_dep,
            "confianca_match": 0.80,
            **agg,
            "data_referencia": date.today().isoformat(),
        }
        print(f"    -> {agg['total_apresentadas']} proposicoes, {len(agg['exemplos'])} exemplos")

    # ── 5. Salva JSON ──────────────────────────────────────────────────────────
    texto = json.dumps(legislativo, ensure_ascii=False, indent=2)
    LEG_JSON_OUT.write_text(texto, encoding="utf-8")
    PUBLIC_DIR.mkdir(parents=True, exist_ok=True)
    LEG_JSON_PUB.write_text(texto, encoding="utf-8")

    novos_no_json = len(legislativo) - len(ja_no_json)
    print(f"\nlegislativo.json atualizado: {len(legislativo)} registros (+{novos_no_json} novos)")
    print(f"  output  -> {LEG_JSON_OUT}")
    print(f"  public  -> {LEG_JSON_PUB}")
    print("\nConcluido.")


if __name__ == "__main__":
    main()

"""
Ingestao de despesas (CEAP) de deputados federais candidatos a reeleicao
Fonte: GET /api/v2/deputados/{id}/despesas

Pre-requisito: public/legislativo/legislativo.json (gerado por ingestao_legislativa.py)

Uso:
    python ingestao_despesas.py                        # todos os deputados (4 anos)
    python ingestao_despesas.py --id 204379            # um deputado especifico
    python ingestao_despesas.py --id 204379 --ano 2025 # um deputado, um ano
    python ingestao_despesas.py --force                # re-baixa mesmo que o arquivo exista

Saida: public/despesas/{nr_sequencial}.json (um arquivo por deputado)
"""

import argparse
import json
import time
from collections import defaultdict
from datetime import date
from pathlib import Path
from urllib.parse import urlparse, parse_qs

import requests

ROOT        = Path(__file__).parent.parent.parent
CACHE_DIR   = ROOT / "data" / ".cache" / "despesas"
PUBLIC_DIR  = ROOT / "public" / "despesas"
LEGISLATIVO = ROOT / "public" / "legislativo" / "legislativo.json"

CAMARA_BASE  = "https://dadosabertos.camara.leg.br/api/v2"
RATE_LIMIT_S = 0.30
# Ultimos 4 anos completos (ex: hoje 2026 -> 2022, 2023, 2024, 2025)
ANOS_PADRAO  = list(range(date.today().year - 4, date.today().year))


# ── Cache em disco ────────────────────────────────────────────────────────────

def _cache_path(key: str) -> Path:
    return CACHE_DIR / f"{key}.json"

def cache_get(key: str):
    p = _cache_path(key)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None

def cache_set(key: str, data) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    _cache_path(key).write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


# ── HTTP com retry e backoff exponencial ──────────────────────────────────────

def fetch_json(session: requests.Session, url: str,
               params: dict = None, cache_key: str = None) -> dict:
    if cache_key:
        hit = cache_get(cache_key)
        if hit is not None:
            return hit
    for tentativa in range(4):
        time.sleep(RATE_LIMIT_S + tentativa * 2)
        try:
            r = session.get(url, params=params, timeout=45)
            if r.status_code in (429, 502, 503, 504) and tentativa < 3:
                espera = 4 ** tentativa
                print(f"    [HTTP {r.status_code}] aguardando {espera}s...")
                time.sleep(espera)
                continue
            r.raise_for_status()
            data = r.json()
            if cache_key:
                cache_set(cache_key, data)
            return data
        except requests.exceptions.Timeout:
            if tentativa < 3:
                print(f"    [Timeout] tentativa {tentativa + 1}/4...")
                continue
            raise
    raise RuntimeError(f"Falha apos 4 tentativas: {url}")


def _ultima_pagina(links: list) -> int:
    """Extrai o numero da ultima pagina do bloco links da API."""
    for link in links:
        if link.get("rel") == "last":
            qs = parse_qs(urlparse(link["href"]).query)
            return int(qs.get("pagina", ["1"])[0])
    return 1  # sem link "last" = apenas 1 pagina


# ── Coleta de dados ───────────────────────────────────────────────────────────

def buscar_nome(session: requests.Session, id_dep: int) -> str:
    """Busca nome civil do deputado via /deputados/{id}."""
    data = fetch_json(
        session,
        f"{CAMARA_BASE}/deputados/{id_dep}",
        cache_key=f"dep_nome_{id_dep}",
    )
    return data.get("dados", {}).get("nomeCivil", "")


def coletar_ano(session: requests.Session, id_dep: int, ano: int) -> list:
    """Coleta todas as paginas de despesas de um deputado em um ano."""
    resp = fetch_json(
        session,
        f"{CAMARA_BASE}/deputados/{id_dep}/despesas",
        params={"ano": ano, "itens": 100, "pagina": 1},
        cache_key=f"desp_{id_dep}_{ano}_p1",
    )
    todos = list(resp.get("dados", []))
    ultima = _ultima_pagina(resp.get("links", []))

    for pag in range(2, ultima + 1):
        resp_p = fetch_json(
            session,
            f"{CAMARA_BASE}/deputados/{id_dep}/despesas",
            params={"ano": ano, "itens": 100, "pagina": pag},
            cache_key=f"desp_{id_dep}_{ano}_p{pag}",
        )
        todos.extend(resp_p.get("dados", []))

    return todos


# ── Agregacao ─────────────────────────────────────────────────────────────────

def agregar(docs: list, anos: list) -> tuple:
    """
    Retorna:
    - tabela: {str(ano): {tipos_ordenados, meses, subtotal_mes, total_ano}}
    - ranking: lista dos 50 maiores fornecedores (total geral, todos os anos)
    """
    # tabela[ano][tipo][mes] = soma valorLiquido
    tabela_raw = defaultdict(lambda: defaultdict(lambda: defaultdict(float)))
    forn: dict = {}

    for d in docs:
        ano  = int(d.get("ano") or 0)
        mes  = int(d.get("mes") or 0)
        tipo = (d.get("tipoDespesa") or "").strip()
        vliq = float(d.get("valorLiquido") or 0)
        if not (ano and mes and tipo):
            continue

        tabela_raw[ano][tipo][mes] += vliq

        cnpj  = (d.get("cnpjCpfFornecedor") or "").strip()
        nome  = (d.get("nomeFornecedor") or "").strip()
        chave = cnpj or nome
        if chave:
            if chave not in forn:
                forn[chave] = {
                    "nomeFornecedor":    nome,
                    "cnpjCpfFornecedor": cnpj,
                    "totalLiquido":      0.0,
                    "qtdDocumentos":     0,
                    "tipos":             set(),
                }
            forn[chave]["totalLiquido"]  += vliq
            forn[chave]["qtdDocumentos"] += 1
            if tipo:
                forn[chave]["tipos"].add(tipo)

    # Serializar tabela
    tabela_out = {}
    for ano in sorted(anos):
        tipos_ano = tabela_raw.get(ano, {})
        if not tipos_ano:
            continue
        tipos_ord = sorted(tipos_ano.keys())
        meses_out = {}
        subtotal  = {}
        total_ano = 0.0
        for mes in range(1, 13):
            row = {
                t: round(tipos_ano[t][mes], 2)
                for t in tipos_ord
                if tipos_ano[t].get(mes, 0)
            }
            if row:
                sub = sum(row.values())
                meses_out[str(mes)] = row
                subtotal[str(mes)]  = round(sub, 2)
                total_ano          += sub
        tabela_out[str(ano)] = {
            "tipos_ordenados": tipos_ord,
            "meses":           meses_out,
            "subtotal_mes":    subtotal,
            "total_ano":       round(total_ano, 2),
        }

    # Top-50 fornecedores
    ranking = sorted(forn.values(), key=lambda x: x["totalLiquido"], reverse=True)[:50]
    for r in ranking:
        r["tipos"]        = sorted(r["tipos"])
        r["totalLiquido"] = round(r["totalLiquido"], 2)

    return tabela_out, ranking


# ── Processamento por deputado ────────────────────────────────────────────────

def processar(session: requests.Session, nr_seq: str, id_dep: int,
              anos: list, force: bool) -> None:
    out = PUBLIC_DIR / f"{nr_seq}.json"
    if not force and out.exists():
        print(f"  [{nr_seq}] ja existe - pulando (use --force para reprocessar)")
        return

    nome = buscar_nome(session, id_dep)
    print(f"  [{nr_seq}] {nome or id_dep}")

    todos_docs = []
    for ano in anos:
        print(f"    {ano}...", end=" ", flush=True)
        docs_ano = coletar_ano(session, id_dep, ano)
        for d in docs_ano:
            d["ano"] = ano  # garante que o campo ano esta presente
        todos_docs.extend(docs_ano)
        print(f"{len(docs_ano)} registros")

    # Normalizar e selecionar campos
    docs_limpos = []
    for d in todos_docs:
        docs_limpos.append({
            "ano":               int(d.get("ano") or 0),
            "mes":               int(d.get("mes") or 0),
            "tipoDespesa":       (d.get("tipoDespesa") or "").strip(),
            "dataDocumento":     d.get("dataDocumento") or "",
            "numDocumento":      str(d.get("numDocumento") or ""),
            "valorDocumento":    round(float(d.get("valorDocumento") or 0), 2),
            "valorLiquido":      round(float(d.get("valorLiquido") or 0), 2),
            "valorGlosa":        round(float(d.get("valorGlosa") or 0), 2),
            "nomeFornecedor":    (d.get("nomeFornecedor") or "").strip(),
            "cnpjCpfFornecedor": (d.get("cnpjCpfFornecedor") or "").strip(),
            "urlDocumento":      d.get("urlDocumento") or "",
        })

    tabela, ranking = agregar(docs_limpos, anos)

    payload = {
        "id_parlamentar":       id_dep,
        "nome":                 nome,
        "anos_coletados":       anos,
        "tabela":               tabela,
        "documentos":           docs_limpos,
        "ranking_fornecedores": ranking,
        "data_referencia":      date.today().isoformat(),
    }

    PUBLIC_DIR.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    kb = out.stat().st_size // 1024
    print(f"    -> {out.relative_to(ROOT)} ({len(docs_limpos)} docs, {kb} KB)")


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Ingestao de despesas CEAP de deputados federais")
    parser.add_argument("--id",    type=int,        help="ID do deputado na API da Camara")
    parser.add_argument("--ano",   type=int,        help="Ano de referencia (padrao: 4 anos completos)")
    parser.add_argument("--force", action="store_true", help="Re-baixa mesmo que o arquivo ja exista")
    args = parser.parse_args()

    anos = [args.ano] if args.ano else ANOS_PADRAO

    session = requests.Session()
    session.headers.update({"Accept": "application/json"})

    if args.id:
        processar(session, f"dep_{args.id}", args.id, anos, args.force)
        return

    if not LEGISLATIVO.exists():
        print("ERRO: public/legislativo/legislativo.json nao encontrado.")
        print("Execute primeiro: python ingestao_legislativa.py && python adicionar_novos_matches.py")
        return

    leg = json.loads(LEGISLATIVO.read_text(encoding="utf-8"))
    deputados = [
        (nr_seq, int(v["id_parlamentar"]))
        for nr_seq, v in leg.items()
        if v.get("casa") == "camara" and v.get("id_parlamentar")
    ]
    print(f"Deputados a processar: {len(deputados)}  |  Anos: {anos}")
    print("Estimativa: ~{:.0f} min na primeira execucao com cache vazio\n".format(
        len(deputados) * len(anos) * 2 / 60
    ))

    erros = 0
    for i, (nr_seq, id_dep) in enumerate(deputados, 1):
        print(f"\n[{i}/{len(deputados)}]", end=" ")
        try:
            processar(session, nr_seq, id_dep, anos, args.force)
        except Exception as e:
            print(f"    ERRO: {e}")
            erros += 1

    print(f"\nConcluido. Erros: {erros}/{len(deputados)}")


if __name__ == "__main__":
    main()

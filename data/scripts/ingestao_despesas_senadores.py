"""
Ingestao de despesas CEAP de senadores candidatos a reeleicao
Fonte: GET https://adm.senado.gov.br/adm-dadosabertos/api/v1/senadores/despesas_ceaps/{ano}

A API retorna todos os senadores do ano em uma unica chamada.
O script baixa o ano completo, cacheia em disco e filtra localmente por senador.

Pre-requisito: public/legislativo/legislativo.json (gerado por ingestao_legislativa.py
               + ingestao_senadores.py)

Uso:
    python ingestao_despesas_senadores.py                                # todos em legislativo.json (4 anos)
    python ingestao_despesas_senadores.py --cod 5529 --anos 2024 2025   # por codigo do senador
    python ingestao_despesas_senadores.py --nome "PACHECO" --anos 2025  # por nome (busca parcial)
    python ingestao_despesas_senadores.py --force                        # re-baixa ignorando cache
    python ingestao_despesas_senadores.py --top 20                       # top-20 fornecedores no ranking

Saida: public/despesas/{nr_sequencial}.json (mesmo formato dos deputados)
"""

import argparse
import json
import time
import unicodedata
from collections import defaultdict
from datetime import date
from pathlib import Path

import requests

ROOT        = Path(__file__).parent.parent.parent
CACHE_DIR   = ROOT / "data" / ".cache" / "despesas"
PUBLIC_DIR  = ROOT / "public" / "despesas"
LEGISLATIVO = ROOT / "public" / "legislativo" / "legislativo.json"

SENADO_BASE  = "https://adm.senado.gov.br/adm-dadosabertos/api/v1/senadores"
RATE_LIMIT_S = 0.30
ANOS_PADRAO  = list(range(date.today().year - 4, date.today().year))

NAO_ESP = "Nao especificado"


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

def fetch_ano(session: requests.Session, ano: int, force: bool = False) -> list:
    """
    Baixa todos os registros de despesas do Senado para um ano.
    A API retorna um array JSON com todos os senadores — filtragem e feita localmente.
    Cache: data/.cache/despesas/senado_ceaps_{ano}.json
    """
    cache_key = f"senado_ceaps_{ano}"
    if not force:
        hit = cache_get(cache_key)
        if hit is not None:
            print(f"  {ano}: {len(hit)} registros (cache)")
            return hit

    url = f"{SENADO_BASE}/despesas_ceaps/{ano}"
    for tentativa in range(4):
        time.sleep(RATE_LIMIT_S + tentativa * 2)
        try:
            r = session.get(url, timeout=60)
            if r.status_code in (429, 502, 503, 504) and tentativa < 3:
                espera = 4 ** tentativa
                print(f"    [HTTP {r.status_code}] aguardando {espera}s...")
                time.sleep(espera)
                continue
            r.raise_for_status()
            data = r.json()
            # A API pode retornar lista direta ou objeto com campo de lista
            registros = data if isinstance(data, list) else []
            if not registros and isinstance(data, dict):
                for v in data.values():
                    if isinstance(v, list):
                        registros = v
                        break
            print(f"  {ano}: {len(registros)} registros (API)")
            cache_set(cache_key, registros)
            return registros
        except requests.exceptions.Timeout:
            if tentativa < 3:
                print(f"    [Timeout] tentativa {tentativa + 1}/4...")
                continue
            raise
        except requests.exceptions.HTTPError as e:
            if tentativa < 3:
                print(f"    [HTTPError {e}] tentativa {tentativa + 1}/4...")
                continue
            raise
    raise RuntimeError(f"Falha apos 4 tentativas: {url}")


# ── Matching e filtragem ──────────────────────────────────────────────────────

def _normalizar(s: str) -> str:
    """Remove acentos e converte para maiusculo para comparacao."""
    return unicodedata.normalize("NFD", s).encode("ascii", "ignore").decode().upper()

def filtrar_senador(registros: list, cod: int | None, nome: str | None) -> list:
    """Filtra registros pelo codigo ou nome (busca parcial normalizada) do senador."""
    if cod is not None:
        return [r for r in registros if str(r.get("codSenador") or "").strip() == str(cod)]
    if nome:
        nome_norm = _normalizar(nome)
        return [r for r in registros if nome_norm in _normalizar(str(r.get("nomeSenador") or ""))]
    return registros


# ── Normalizacao de campos ────────────────────────────────────────────────────

def _str(v) -> str:
    return str(v).strip() if v is not None else ""

def _float(v) -> float:
    if v is None:
        return 0.0
    try:
        return round(float(str(v).replace(",", ".")), 2)
    except (ValueError, TypeError):
        return 0.0

def _int(v) -> int:
    if v is None:
        return 0
    try:
        return int(v)
    except (ValueError, TypeError):
        return 0

def normalizar_registro(r: dict, ano: int) -> dict:
    """
    Mapeia campos da API do Senado para o formato DespesaDoc usado no front-end.
    valorReembolsado -> valorLiquido (unico valor disponivel; sem glosa separado).
    """
    tipo  = _str(r.get("tipoDespesa"))  or NAO_ESP
    forn  = _str(r.get("fornecedor"))   or NAO_ESP
    cnpj  = _str(r.get("cpfCnpj"))      or NAO_ESP
    valor = _float(r.get("valorReembolsado"))
    return {
        "ano":               ano,
        "mes":               _int(r.get("mes")),
        "tipoDespesa":       tipo,
        "dataDocumento":     _str(r.get("data")),
        "numDocumento":      _str(r.get("documento")),
        "valorDocumento":    valor,   # API nao distingue valor do doc do reembolso
        "valorLiquido":      valor,
        "valorGlosa":        0.0,     # nao disponivel nesta API
        "nomeFornecedor":    forn,
        "cnpjCpfFornecedor": cnpj,
        "urlDocumento":      "",      # nao disponivel nesta API
        "detalhamento":      _str(r.get("detalhamento")),
    }


# ── Agregacao ─────────────────────────────────────────────────────────────────

def agregar(docs: list, anos: list, top_n: int) -> tuple:
    """
    Retorna (tabela, ranking_fornecedores).
    Equivalente ao agregar() de ingestao_despesas.py, adaptado para campos do Senado.
    """
    tabela_raw = defaultdict(lambda: defaultdict(lambda: defaultdict(float)))
    forn: dict = {}
    forn_datas: dict = {}

    for d in docs:
        ano  = d["ano"]
        mes  = d["mes"]
        tipo = d["tipoDespesa"]
        vliq = d["valorLiquido"]
        if not (ano and mes and tipo):
            continue

        tabela_raw[ano][tipo][mes] += vliq

        cnpj  = d["cnpjCpfFornecedor"]
        nome  = d["nomeFornecedor"]
        chave = cnpj if cnpj != NAO_ESP else nome
        if chave:
            if chave not in forn:
                forn[chave] = {
                    "nomeFornecedor":    nome,
                    "cnpjCpfFornecedor": cnpj,
                    "totalLiquido":      0.0,
                    "qtdDocumentos":     0,
                    "tipos":             set(),
                }
                forn_datas[chave] = []
            forn[chave]["totalLiquido"]  += vliq
            forn[chave]["qtdDocumentos"] += 1
            if tipo != NAO_ESP:
                forn[chave]["tipos"].add(tipo)
            if d["dataDocumento"]:
                forn_datas[chave].append(d["dataDocumento"])

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

    # Ranking de fornecedores (top_n)
    ranking = sorted(forn.values(), key=lambda x: x["totalLiquido"], reverse=True)[:top_n]
    for i, r in enumerate(ranking):
        chave = r["cnpjCpfFornecedor"] if r["cnpjCpfFornecedor"] != NAO_ESP else r["nomeFornecedor"]
        datas = sorted(forn_datas.get(chave, []))
        r["tipos"]        = sorted(r["tipos"])
        r["totalLiquido"] = round(r["totalLiquido"], 2)
        r["primeiraData"] = datas[0] if datas else ""
        r["ultimaData"]   = datas[-1] if datas else ""

    return tabela_out, ranking


# ── Processamento por senador ─────────────────────────────────────────────────

def processar(
    todos_por_ano: dict,
    nr_seq: str,
    cod: int | None,
    nome_ref: str,
    anos: list,
    force: bool,
    top_n: int,
) -> None:
    out = PUBLIC_DIR / f"{nr_seq}.json"
    if not force and out.exists():
        print(f"  [{nr_seq}] ja existe - pulando (use --force para reprocessar)")
        return

    docs_limpos = []
    for ano in anos:
        registros_ano = todos_por_ano.get(ano, [])
        filtrados = filtrar_senador(registros_ano, cod, None)
        for r in filtrados:
            docs_limpos.append(normalizar_registro(r, ano))

    # Inferir nome do senador a partir dos registros
    nome = nome_ref
    for d in docs_limpos:
        break  # nome_ref ja e suficiente; podemos pegar do registro se necessario

    total = sum(d["valorLiquido"] for d in docs_limpos)
    print(f"  [{nr_seq}] {nome_ref}  |  {len(docs_limpos)} registros  |  total: R$ {total:,.2f}")

    tabela, ranking = agregar(docs_limpos, anos, top_n)

    payload = {
        "id_parlamentar":       cod,
        "nome":                 nome_ref,
        "anos_coletados":       anos,
        "tabela":               tabela,
        "documentos":           docs_limpos,
        "ranking_fornecedores": ranking,
        "data_referencia":      date.today().isoformat(),
    }

    PUBLIC_DIR.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    kb = out.stat().st_size // 1024
    print(f"    -> {out.relative_to(ROOT)} ({kb} KB)")


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Ingestao de despesas CEAP de senadores"
    )
    parser.add_argument("--cod",   type=int,         help="Codigo do senador (codSenador)")
    parser.add_argument("--nome",  type=str,         help="Nome parcial do senador (busca case-insensitive)")
    parser.add_argument("--anos",  type=int, nargs="+", help="Anos a consultar (ex: 2023 2024 2025)")
    parser.add_argument("--top",   type=int, default=10, help="Numero de fornecedores no ranking (padrao: 10)")
    parser.add_argument("--force", action="store_true",  help="Re-baixa mesmo que o arquivo ja exista")
    args = parser.parse_args()

    anos   = args.anos or ANOS_PADRAO
    top_n  = args.top
    force  = args.force

    session = requests.Session()
    session.headers.update({"Accept": "application/json"})

    # Baixar e cachear cada ano uma unica vez (API retorna todos os senadores)
    print(f"Anos: {anos}  |  Top fornecedores: {top_n}")
    print("Baixando dados anuais...")
    todos_por_ano = {}
    for ano in anos:
        todos_por_ano[ano] = fetch_ano(session, ano, force=force)

    # ── Modo senador unico (--cod ou --nome) ──────────────────────────────────
    if args.cod or args.nome:
        nr_seq    = f"sen_{args.cod}" if args.cod else f"sen_{_normalizar(args.nome or '')}"
        nome_ref  = args.nome or str(args.cod)
        # Tentar inferir nome real dos registros
        for ano in anos:
            for r in todos_por_ano[ano]:
                if args.cod and str(r.get("codSenador") or "") == str(args.cod):
                    nome_ref = _str(r.get("nomeSenador")) or nome_ref
                    break
                if args.nome and _normalizar(args.nome) in _normalizar(str(r.get("nomeSenador") or "")):
                    nome_ref = _str(r.get("nomeSenador")) or nome_ref
                    break
        print(f"\nProcessando: {nome_ref}")
        processar(todos_por_ano, nr_seq, args.cod, nome_ref, anos, force, top_n)
        return

    # ── Modo batch: lê legislativo.json e processa todos os senadores ─────────
    if not LEGISLATIVO.exists():
        print("ERRO: public/legislativo/legislativo.json nao encontrado.")
        print("Execute primeiro: python ingestao_legislativa.py && python ingestao_senadores.py")
        return

    leg = json.loads(LEGISLATIVO.read_text(encoding="utf-8"))
    senadores = [
        (nr_seq, int(v["id_parlamentar"]), v.get("nome_urna", nr_seq))
        for nr_seq, v in leg.items()
        if v.get("casa") == "senado" and v.get("id_parlamentar")
    ]

    if not senadores:
        print("Nenhum senador encontrado em legislativo.json.")
        print("Verifique se ingestao_senadores.py foi executado.")
        return

    print(f"\nSenadores a processar: {len(senadores)}")
    erros = 0
    for i, (nr_seq, cod, nome) in enumerate(senadores, 1):
        print(f"\n[{i}/{len(senadores)}]", end=" ")
        try:
            processar(todos_por_ano, nr_seq, cod, nome, anos, force, top_n)
        except Exception as e:
            print(f"    ERRO: {e}")
            erros += 1

    print(f"\nConcluido. Erros: {erros}/{len(senadores)}")


if __name__ == "__main__":
    main()

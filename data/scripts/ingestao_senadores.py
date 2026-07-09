"""
ingestao_senadores.py

Coleta dados de autorias de senadores candidatos à reeleição via API pública do Senado.

Endpoints utilizados:
  GET /senador/{codigo}/autorias         → PEC e PL com IndicadorAutorPrincipal (XML)
  GET /senador/{codigo}/mandatos         → data de início do mandato (XML)
  GET /processo/emenda?codigoParlamentarAutor={codigo}&dataInicio={data_inicio}
                                         → emendas do período de senador (JSON)

Métricas coletadas (6/6):
  1. PEC: total de autoria (autor ou coautor)
  2. PEC: como autor principal (IndicadorAutorPrincipal=Sim)
  3. PL (PLS pré-2019 + PL pós-2019): total de autoria
  4. PL: como autor principal
  5. Emendas a MPV: total filtrado por regex no campo identificacao
  6. Emendas a MPV: como autor único (campo autoria sem ponto e vírgula)

Nota: MPVs são de iniciativa exclusiva da Presidência da República; senadores
apenas propõem emendas a elas, nunca figuram como autores de MPVs.

Limitação: o endpoint /processo/emenda não filtra por tipo de processo.
A solução é filtrar client-side e usar dataInicio = início do mandato de
senador (não 1990), excluindo automaticamente o período como deputado.
"""

import json
import re
import time
import xml.etree.ElementTree as ET
from datetime import date
from pathlib import Path

import requests

# ── Paths ─────────────────────────────────────────────────────────────────────
ROOT       = Path(__file__).parent.parent.parent
CACHE_DIR  = ROOT / "data" / ".cache" / "legislativo"
OUTPUT_DIR = ROOT / "data" / "output" / "legislativo"
PUBLIC_DIR = ROOT / "public" / "legislativo"

SENADO_BASE  = "https://legis.senado.leg.br/dadosabertos"
RATE_LIMIT_S = 0.13   # ~7 req/s — abaixo do limite de 10/s
MAX_RETRIES  = 4

SIGLAS_PL  = {"PLS", "PL"}   # PLS = pré-2019; PL = pós-2019
SIGLAS_PEC = {"PEC"}

# Regex para identificar emendas a MPV no campo identificacao
# Exemplos reais: "EMENDA 59 - MPV 696/2015", "EME MPV 1.090/2021"
RE_MPV = re.compile(r"\bMPV\b", re.IGNORECASE)


# ── Cache em disco ─────────────────────────────────────────────────────────────

def _cache_xml(key: str) -> Path:
    return CACHE_DIR / f"{key}.xml"

def _cache_json(key: str) -> Path:
    return CACHE_DIR / f"{key}.json"


def cache_get_xml(key: str) -> ET.Element | None:
    p = _cache_xml(key)
    if p.exists():
        try:
            return ET.fromstring(p.read_text(encoding="utf-8"))
        except ET.ParseError:
            p.unlink()
    return None

def cache_set_xml(key: str, text: str) -> None:
    _cache_xml(key).write_text(text, encoding="utf-8")


def cache_get_json(key: str) -> list | dict | None:
    p = _cache_json(key)
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            p.unlink()
    return None

def cache_set_json(key: str, data: list | dict) -> None:
    _cache_json(key).write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


# ── HTTP com retry/backoff ─────────────────────────────────────────────────────

def _retry_get(session: requests.Session, url: str, params: dict | None = None,
               accept: str = "application/xml", timeout: int = 60) -> requests.Response:
    for attempt in range(MAX_RETRIES):
        try:
            resp = session.get(url, params=params, timeout=timeout,
                               headers={"Accept": accept})
            if resp.status_code in (429, 503):
                wait = 2 ** attempt * 2
                print(f"    [HTTP {resp.status_code}] aguardando {wait}s...", flush=True)
                time.sleep(wait)
                continue
            resp.raise_for_status()
            time.sleep(RATE_LIMIT_S)
            return resp
        except requests.RequestException as exc:
            if attempt == MAX_RETRIES - 1:
                raise
            wait = 2 ** attempt
            print(f"    [tentativa {attempt + 1}] {exc} — aguardando {wait}s...", flush=True)
            time.sleep(wait)
    raise RuntimeError(f"Falha ao buscar {url} apos {MAX_RETRIES} tentativas")


def fetch_xml(session: requests.Session, url: str, cache_key: str,
              params: dict | None = None) -> ET.Element:
    cached = cache_get_xml(cache_key)
    if cached is not None:
        return cached
    resp = _retry_get(session, url, params=params, accept="application/xml")
    cache_set_xml(cache_key, resp.text)
    return ET.fromstring(resp.text)


def fetch_json_list(session: requests.Session, url: str, cache_key: str,
                    params: dict | None = None) -> list:
    cached = cache_get_json(cache_key)
    if cached is not None:
        return cached if isinstance(cached, list) else []
    resp = _retry_get(session, url, params=params, accept="application/json", timeout=90)
    data = resp.json()
    result = data if isinstance(data, list) else []
    cache_set_json(cache_key, result)
    return result


# ── Etapa 1: data de início do mandato de senador ─────────────────────────────

def buscar_data_inicio_mandato(session: requests.Session, codigo: int) -> str:
    """
    Retorna a data ISO da primeira DataInicio entre todos os mandatos do senador.
    Usar o mandato mais antigo garante cobertura total e exclui período como deputado.
    """
    url = f"{SENADO_BASE}/senador/{codigo}/mandatos"
    root = fetch_xml(session, url, f"senado_mandatos_{codigo}")

    datas: list[str] = []
    for elem in root.iter("DataInicio"):
        d = (elem.text or "").strip()
        if re.match(r"\d{4}-\d{2}-\d{2}", d):
            datas.append(d)
    if not datas:
        # Fallback: início da 55ª legislatura (2015-02-01) cobre todos os 5 senadores
        return "2015-02-01"
    return min(datas)


# ── Etapa 2: autorias de PEC e PL ─────────────────────────────────────────────

def url_materia(codigo: str) -> str:
    return f"https://www25.senado.leg.br/web/atividade/materias/-/materia/{codigo}"


def extrair_proposicoes(root: ET.Element, siglas_alvo: set[str]) -> list[dict]:
    resultado = []
    for autoria in root.iter("Autoria"):
        materia = autoria.find("Materia")
        if materia is None:
            continue
        sigla = (materia.findtext("Sigla") or "").strip()
        if sigla not in siglas_alvo:
            continue

        indicador = (autoria.findtext("IndicadorAutorPrincipal") or "").strip()
        codigo    = (materia.findtext("Codigo") or "").strip()
        ementa    = (materia.findtext("Ementa") or "").strip()
        descricao = (materia.findtext("DescricaoIdentificacao") or "").strip()
        numero    = materia.findtext("Numero")
        ano_raw   = (materia.findtext("Ano") or "").strip()
        data_str  = (materia.findtext("Data") or "")[:10]

        resultado.append({
            "sigla":           "PL" if sigla == "PLS" else sigla,
            "numero":          numero,
            "ano":             int(ano_raw) if ano_raw.isdigit() else None,
            "ementa":          (ementa or descricao)[:220],
            "url":             url_materia(codigo) if codigo else "",
            "data":            data_str,
            "autor_principal": indicador == "Sim",
        })
    return resultado


# ── Etapa 4+5: emendas a MPV ──────────────────────────────────────────────────

def buscar_emendas_mpv(session: requests.Session, codigo: int,
                       data_inicio: str) -> list[dict]:
    """
    Busca emendas do senador desde data_inicio (início do mandato) e filtra
    apenas as relativas a MPVs via regex no campo identificacao.

    Não há parâmetro sigla neste endpoint; o filtro é feito client-side.
    dataInicio = início do mandato exclui automaticamente o período como deputado.
    """
    url        = f"{SENADO_BASE}/processo/emenda"
    cache_key  = f"senado_emendas_{codigo}_{data_inicio}"
    params     = {"codigoParlamentarAutor": codigo, "dataInicio": data_inicio}

    print(f"    buscando emendas desde {data_inicio}...", flush=True)
    try:
        todas = fetch_json_list(session, url, cache_key, params=params)
    except Exception as exc:
        print(f"    [aviso] emendas indisponíveis: {exc}")
        return []

    # Filtra somente emendas a MPV
    mpv = [e for e in todas if RE_MPV.search(e.get("identificacao") or "")]
    print(f"    {len(todas)} emendas totais → {len(mpv)} a MPV", flush=True)
    return mpv


def _autor_unico(autoria_str: str) -> bool:
    """
    Retorna True se a emenda tem apenas um autor.
    Múltiplos autores são separados por ';' ou ' e ' na string de autoria.
    """
    if not autoria_str:
        return True
    return ";" not in autoria_str and " e " not in autoria_str.lower()


def processar_emendas_mpv(emendas: list[dict]) -> tuple[int, int, list[dict]]:
    """Retorna (total, autor_unico_count, lista_para_json)."""
    autor_unico_count = 0
    lista = []
    for e in emendas:
        autoria  = e.get("autoria", "")
        unico    = _autor_unico(autoria)
        if unico:
            autor_unico_count += 1

        lista.append({
            "identificacao": (e.get("identificacao") or "")[:200],
            "ementa":        (e.get("ementa") or e.get("identificacao") or "")[:220],
            "url":           e.get("urlDocumentoEmenda") or "",
            "data":          (e.get("dataApresentacao") or "")[:10],
            "autor_unico":   unico,
        })
    return len(emendas), autor_unico_count, lista


# ── Agregação final ────────────────────────────────────────────────────────────

def agregar_senador(autorias_xml: ET.Element, emendas_mpv: list[dict]) -> dict:
    pec_lista = extrair_proposicoes(autorias_xml, SIGLAS_PEC)
    pl_lista  = extrair_proposicoes(autorias_xml, SIGLAS_PL)

    # Série temporal: PEC + PL combinados
    por_ano: dict[str, int] = {}
    for item in pec_lista + pl_lista:
        ano = str(item["ano"]) if item["ano"] else ""
        if ano.isdigit() and int(ano) > 2000:
            por_ano[ano] = por_ano.get(ano, 0) + 1
    por_ano = dict(sorted(por_ano.items()))

    por_tipo = {"PEC": len(pec_lista), "PL": len(pl_lista)}

    todos = sorted(pec_lista + pl_lista, key=lambda x: x.get("ano") or 0, reverse=True)
    exemplos = [
        {"sigla": p["sigla"], "numero": p["numero"], "ano": p["ano"],
         "ementa": p["ementa"], "url": p["url"]}
        for p in todos[:5]
    ]

    def to_item(p: dict) -> dict:
        return {"sigla": p["sigla"], "numero": p["numero"], "ano": p["ano"],
                "ementa": p["ementa"], "url": p["url"], "data": p["data"]}

    mpv_total, mpv_autor_unico, mpv_lista = processar_emendas_mpv(emendas_mpv)

    return {
        "total_apresentadas":       len(pec_lista) + len(pl_lista),
        "total_aprovadas":          0,
        "por_tipo":                 por_tipo,
        "por_ano":                  por_ano,
        "exemplos":                 exemplos,
        "pec_total":                len(pec_lista),
        "pec_autor_principal":      sum(1 for p in pec_lista if p["autor_principal"]),
        "pl_total":                 len(pl_lista),
        "pl_autor_principal":       sum(1 for p in pl_lista if p["autor_principal"]),
        "emendas_mpv_total":        mpv_total,
        "emendas_mpv_autor_unico":  mpv_autor_unico,
        "pec_lista":                [to_item(p) for p in pec_lista],
        "pl_lista":                 [to_item(p) for p in pl_lista],
        "emendas_mpv_lista":        mpv_lista,
    }


# ── Pipeline principal ─────────────────────────────────────────────────────────

def main() -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    leg_json_pub = PUBLIC_DIR / "legislativo.json"
    leg_json_out = OUTPUT_DIR / "legislativo.json"

    with open(leg_json_pub, encoding="utf-8") as f:
        legislativo: dict = json.load(f)

    senadores = {sq: d for sq, d in legislativo.items() if d.get("casa") == "senado"}
    print(f"Senadores a processar: {len(senadores)}")

    session = requests.Session()

    for i, (sq, dados) in enumerate(senadores.items(), 1):
        nome    = dados.get("nome_urna", sq)
        id_parl = dados.get("id_parlamentar")
        print(f"\n[{i}/{len(senadores)}] {nome} (id={id_parl})")

        try:
            # Etapa 1: data de início do mandato
            data_inicio = buscar_data_inicio_mandato(session, id_parl)
            print(f"    mandato desde: {data_inicio}")

            # Etapa 2: autorias (PEC + PL)
            autorias_xml = fetch_xml(
                session,
                f"{SENADO_BASE}/senador/{id_parl}/autorias",
                f"senado_autorias_{id_parl}",
            )

            # Etapas 4+5: emendas a MPV
            emendas_mpv = buscar_emendas_mpv(session, id_parl, data_inicio)

            # Agregação
            agg = agregar_senador(autorias_xml, emendas_mpv)

        except Exception as exc:
            print(f"  [erro] {exc} — pulando")
            continue

        print(f"  PEC        : {agg['pec_total']:>3} total | {agg['pec_autor_principal']:>3} autor principal")
        print(f"  PL         : {agg['pl_total']:>3} total | {agg['pl_autor_principal']:>3} autor principal")
        print(f"  Emendas MPV: {agg['emendas_mpv_total']:>3} total | {agg['emendas_mpv_autor_unico']:>3} autor único")

        legislativo[sq] = {
            **dados,
            **agg,
            "data_referencia": date.today().isoformat(),
        }

    texto = json.dumps(legislativo, ensure_ascii=False, indent=2)
    leg_json_pub.write_text(texto, encoding="utf-8")
    leg_json_out.write_text(texto, encoding="utf-8")

    print(f"\nlegislativo.json atualizado: {len(legislativo)} registros totais")
    print(f"  public -> {leg_json_pub}")
    print(f"  output -> {leg_json_out}")
    print("\nConcluido.")


if __name__ == "__main__":
    main()

"""
Ingestão legislativa — Protótipo 2022, âmbito federal
Fonte: API da Câmara v2 e API do Senado (dadosabertos)

Requer: data/output/candidatos.json (gerado por ingesta_tse.py --dry-run)

Uso:
    python ingestao_legislativa.py [--dry-run]

--dry-run: só faz o match e salva depara.csv, sem coletar proposições.
"""

import argparse
import json
import re
import threading
import time
import unicodedata
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from difflib import SequenceMatcher
from pathlib import Path

import pandas as pd
import requests

# ── Paths ─────────────────────────────────────────────────────────────────────
ROOT       = Path(__file__).parent.parent.parent
CACHE_DIR  = ROOT / "data" / ".cache" / "legislativo"
OUTPUT_DIR = ROOT / "data" / "output" / "legislativo"
PUBLIC_DIR = ROOT / "public" / "legislativo"
CAND_JSON  = ROOT / "data" / "output" / "candidatos.json"

# ── Endpoints ─────────────────────────────────────────────────────────────────
CAMARA_BASE = "https://dadosabertos.camara.leg.br/api/v2"
SENADO_BASE = "https://legis.senado.leg.br/dadosabertos"

CAMARA_LEGISLATURA   = 56          # 2019-2023 (eleitos em 2018)
SENADO_LEGISLATURAS  = [55, 56]    # 55 = eleitos 2014 (mandato até 2023), 56 = eleitos 2018

TIPOS_CAMARA = ["PL", "PLP", "PEC", "PDL"]
TIPOS_SENADO = [
    "Projeto de Lei",
    "Projeto de Lei Complementar",
    "Proposta de Emenda à Constituição",
    "Projeto de Decreto Legislativo",
]
SIGLA_SENADO = {
    "Projeto de Lei":                         "PL",
    "Projeto de Lei Complementar":            "PLP",
    "Proposta de Emenda à Constituição":      "PEC",
    "Projeto de Decreto Legislativo":         "PDL",
}
CODS_APROVADA  = {1140}                          # Transformado em Norma Jurídica
CODS_ARQUIVADA = {923, 930, 931, 941, 950, 1285, 1292}  # Arquivada / Retirada / Perdeu eficácia / etc.

DETAIL_WORKERS = 5     # threads paralelas para buscar detalhes de proposições
DETAIL_RATE_S  = 0.10  # pausa por thread (s)

OCUP_DEP_PATTERN = r"\bDEPUTADO\b"    # TSE usa "DEPUTADO" (sem Federal/Distrital) para deputados em exercício
OCUP_SEN_PATTERN = r"\bSENADOR\b"

THRESHOLD_MATCH     = 0.70  # mínimo para incluir no de-para via nome (fallback quando CPF falha)
THRESHOLD_CONFIANTE = 0.85  # confiança alta
RATE_LIMIT_S        = 0.40

# ── Cache em disco ─────────────────────────────────────────────────────────────

def _cache_path(key: str) -> Path:
    return CACHE_DIR / f"{key}.json"


def cache_get(key: str):
    p = _cache_path(key)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def cache_set(key: str, data) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    _cache_path(key).write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


# ── HTTP helpers ───────────────────────────────────────────────────────────────

def fetch_json(session: requests.Session, url: str, params: dict = None,
               cache_key: str = None, rate_s: float | None = None):
    if cache_key:
        hit = cache_get(cache_key)
        if hit is not None:
            return hit
    _rate = rate_s if rate_s is not None else RATE_LIMIT_S
    for tentativa in range(4):
        time.sleep(_rate + tentativa * 2)
        try:
            r = session.get(url, params=params, timeout=45)
            if r.status_code in (429, 502, 503, 504) and tentativa < 3:
                print(f"    [HTTP {r.status_code}] aguardando {4 ** tentativa}s e tentando novamente…")
                time.sleep(4 ** tentativa)
                continue
            r.raise_for_status()
            data = r.json()
            if cache_key:
                cache_set(cache_key, data)
            return data
        except requests.exceptions.Timeout:
            if tentativa < 3:
                print(f"    [Timeout] tentativa {tentativa + 1}/4…")
                continue
            raise
    raise RuntimeError(f"Falha após 4 tentativas: {url}")


def fetch_xml_root(url: str, cache_key: str = None) -> ET.Element:
    if cache_key:
        hit = cache_get(cache_key)
        if hit is not None:
            return ET.fromstring(hit["xml"])
    for tentativa in range(4):
        time.sleep(RATE_LIMIT_S + tentativa * 2)
        try:
            r = requests.get(url, timeout=45)
            if r.status_code in (429, 502, 503, 504) and tentativa < 3:
                print(f"    [HTTP {r.status_code}] aguardando {4 ** tentativa}s e tentando novamente…")
                time.sleep(4 ** tentativa)
                continue
            r.raise_for_status()
            if cache_key:
                cache_set(cache_key, {"xml": r.text})
            return ET.fromstring(r.text)
        except requests.exceptions.Timeout:
            if tentativa < 3:
                print(f"    [Timeout] tentativa {tentativa + 1}/4…")
                continue
            raise
    raise RuntimeError(f"Falha após 4 tentativas: {url}")


# ── Sessions por thread + classificação de situação ───────────────────────────

_tls = threading.local()


def _session() -> requests.Session:
    """Retorna uma requests.Session exclusiva da thread atual."""
    if not hasattr(_tls, "session"):
        s = requests.Session()
        s.headers.update({"Accept": "application/json"})
        _tls.session = s
    return _tls.session


def classificar_situacao(cod) -> str:
    """Classifica codSituacao em 'aprovadas', 'arquivadas' ou 'em_tramitacao'."""
    if cod is None:
        return "em_tramitacao"
    cod = int(cod)
    if cod in CODS_APROVADA:
        return "aprovadas"
    if cod in CODS_ARQUIVADA:
        return "arquivadas"
    return "em_tramitacao"


def buscar_detalhe_proposicao(id_prop: int) -> dict:
    """
    Busca o detalhe de uma proposição via GET /proposicoes/{id}.
    Retorna apenas o objeto 'dados' (inclui statusProposicao.codSituacao).
    Seguro para uso em threads paralelas — usa session por thread e cache em disco.
    """
    key = f"camara_prop_detalhe_{id_prop}"
    cached = cache_get(key)
    if cached is not None:
        return cached
    try:
        resp = fetch_json(_session(), f"{CAMARA_BASE}/proposicoes/{id_prop}",
                          cache_key=key, rate_s=DETAIL_RATE_S)
        dados = resp.get("dados", {}) if isinstance(resp, dict) else {}
        cache_set(key, dados)   # sobrescreve o cache com só o 'dados' (menor)
        return dados
    except Exception as exc:
        print(f"\n    [aviso] detalhe prop {id_prop}: {exc}")
        return {}


def buscar_detalhes_paralelo(ids: list[int]) -> dict[int, dict]:
    """
    Busca detalhes de múltiplas proposições em paralelo via ThreadPoolExecutor.
    Retorna dict {id_prop: dados}.
    """
    if not ids:
        return {}

    cache_misses = sum(
        1 for i in ids if cache_get(f"camara_prop_detalhe_{i}") is None
    )
    print(f"      {len(ids)} proposicoes — {cache_misses} novas chamadas, "
          f"{len(ids) - cache_misses} em cache", flush=True)

    resultados: dict[int, dict] = {}
    concluidos = 0

    with ThreadPoolExecutor(max_workers=DETAIL_WORKERS) as executor:
        futures = {executor.submit(buscar_detalhe_proposicao, i): i for i in ids}
        for future in as_completed(futures):
            id_prop = futures[future]
            concluidos += 1
            try:
                resultados[id_prop] = future.result()
            except Exception as exc:
                resultados[id_prop] = {}
            if cache_misses > 0 and (concluidos % 100 == 0 or concluidos == len(ids)):
                print(f"      {concluidos}/{len(ids)}...", end="\r", flush=True)

    if cache_misses > 0:
        print()
    return resultados


# ── Normalização de nomes ──────────────────────────────────────────────────────

# Prefixos de cargo/título que o TSE inclui no nome de urna mas a API da Câmara/Senado não usa
_TITULOS = {
    'DELEGADO', 'DELEGADA', 'CORONEL', 'CORONELA', 'CEL',
    'CAPITAO', 'CAPITA', 'CAP', 'CABO', 'SOLDADO',
    'TENENTE', 'TEN', 'MAJOR', 'SARGENTO',
    'PROFESSOR', 'PROFESSORA', 'PROF',
    'DOUTOR', 'DOUTORA', 'DR', 'DRA',
    'MEDICO', 'MEDICA', 'ENFERMEIRO', 'ENFERMEIRA',
    'VEREADOR', 'VEREADORA', 'DEPUTADO', 'DEPUTADA',
    'SENADOR', 'SENADORA', 'PREFEITO', 'PREFEITA',
    'PADRE', 'PASTOR', 'PASTORA',
}

# Sufixos de partido que candidatos incluem no nome de urna ("GUIMARÃES DO PT")
_SUFIXOS_PARTIDO = re.compile(
    r'\s+D[OA]S?\s+(?:PT|PL|PP|MDB|PSD|PSDB|PDT|PSB|PODE|REPUBLICANOS|UNIAO|AVANTE|SOLIDARIEDADE|'
    r'PROS|PMB|PRTB|DC|PC\s*DO\s*B|PSOL|NOVO|PATRIOTA|CIDADANIA|PV|PTB|AGIR)$'
)


def norm(s: str) -> str:
    if not s:
        return ""
    s = unicodedata.normalize("NFD", s.upper().strip())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return " ".join(s.split())


def strip_titulo(nome_norm: str) -> str:
    """Remove prefixo de título/cargo e sufixo de partido do nome já normalizado."""
    # Remove sufixo de partido ("DO PT", "DA UNIAO" etc.)
    nome_norm = _SUFIXOS_PARTIDO.sub('', nome_norm).strip()
    # Remove prefixos de título enquanto restar pelo menos 1 palavra
    palavras = nome_norm.split()
    while len(palavras) > 1 and palavras[0] in _TITULOS:
        palavras = palavras[1:]
    return ' '.join(palavras)


def similaridade(a: str, b: str) -> float:
    return SequenceMatcher(None, norm(a), norm(b)).ratio()


def palavras_contidas(curto: str, longo: str) -> bool:
    """Verdadeiro se todas as palavras de `curto` aparecem em `longo`."""
    palavras = set(norm(curto).split())
    alvo = set(norm(longo).split())
    return bool(palavras) and palavras.issubset(alvo)


def sim_nome(nome_tse: str, nome_parl: str) -> float:
    """
    Combina SequenceMatcher com verificação de contenção de palavras.
    Tenta também o nome sem título/prefixo (DELEGADO X → X) e sem sufixo de partido.
    """
    n_tse  = norm(nome_tse)
    n_parl = norm(nome_parl)
    base   = SequenceMatcher(None, n_tse, n_parl).ratio()

    # Tenta com título removido
    n_tse_s = strip_titulo(n_tse)
    if n_tse_s != n_tse:
        base = max(base, SequenceMatcher(None, n_tse_s, n_parl).ratio())

    # Boost por contenção de palavras (nome original)
    for tse_cand in {n_tse, n_tse_s}:
        if palavras_contidas(tse_cand, n_parl) or palavras_contidas(n_parl, tse_cand):
            n_palavras = len(tse_cand.split())
            boost = 0.85 if n_palavras >= 2 else 0.78
            base = max(base, boost)

    return base


# ── Câmara — lista de deputados ────────────────────────────────────────────────

def buscar_todos_deputados(session: requests.Session) -> list[dict]:
    """Carrega todos os deputados da legislatura de uma vez (evita 27 chamadas por UF)."""
    key = f"camara_deps_todos_{CAMARA_LEGISLATURA}"
    cached = cache_get(key)
    if cached is not None:
        return cached

    todos: list[dict] = []
    pagina = 1
    while True:
        params = {
            "idLegislatura": CAMARA_LEGISLATURA,
            "pagina": pagina,
            "itens": 100,
            "ordem": "ASC",
            "ordenarPor": "nome",
        }
        dados = fetch_json(session, f"{CAMARA_BASE}/deputados", params=params).get("dados", [])
        todos.extend(dados)
        print(f"    carregando deputados: {len(todos)}…", end="\r", flush=True)
        if len(dados) < 100:
            break
        pagina += 1
    print()

    cache_set(key, todos)
    return todos


def _norm_cpf(cpf: str | None) -> str:
    """Normaliza CPF para 11 dígitos sem pontuação. Retorna '' se inválido."""
    if not cpf:
        return ""
    digits = re.sub(r"\D", "", str(cpf))
    return digits if len(digits) == 11 else ""


def buscar_indice_cpf_camara(session: requests.Session, todos_deps: list[dict]) -> dict[str, dict]:
    """
    Busca o detalhe de cada deputado para obter o CPF (não disponível no endpoint de lista).
    Resultados são cacheados individualmente para evitar re-downloads.
    Retorna dict {cpf_11_digitos: dados_deputado_lista}.
    """
    key_idx = f"camara_cpf_index_{CAMARA_LEGISLATURA}"
    cached = cache_get(key_idx)
    if cached is not None:
        return cached

    indice: dict[str, dict] = {}
    total = len(todos_deps)
    for i, dep in enumerate(todos_deps, 1):
        dep_id = dep["id"]
        cache_key = f"camara_dep_detalhe_{dep_id}"
        detalhe = cache_get(cache_key)
        if detalhe is None:
            print(f"    buscando CPF dos deputados: {i}/{total}…", end="\r", flush=True)
            try:
                resp = fetch_json(session, f"{CAMARA_BASE}/deputados/{dep_id}", cache_key=cache_key)
                detalhe = resp.get("dados", {})
            except Exception as exc:
                print(f"\n    [aviso] falha ao buscar detalhe do deputado {dep_id}: {exc}")
                detalhe = {}
            cache_set(cache_key, detalhe)

        cpf = _norm_cpf(detalhe.get("cpf"))
        if cpf:
            indice[cpf] = dep  # aponta para o registro da lista (tem siglaUf, siglaPartido, id, nome)

    print()
    cache_set(key_idx, indice)
    print(f"  Índice CPF/Câmara: {len(indice)} deputados mapeados de {total}")
    return indice


def match_deputado(
    nome_tse: str,
    uf_tse: str,
    partido_tse: str,
    todos_deps: list[dict],
    cpf_tse: str = "",
    indice_cpf: dict[str, dict] | None = None,
) -> tuple[dict | None, float, str]:
    """
    Tenta matching por CPF primeiro (confiança 1.0); fallback para nome fuzzy.
    Retorna (deputado, confiança, método) onde método é 'cpf' ou 'nome'.
    """
    # 1. Tentativa por CPF
    cpf_norm = _norm_cpf(cpf_tse)
    if cpf_norm and indice_cpf and cpf_norm in indice_cpf:
        return (indice_cpf[cpf_norm], 1.0, "cpf")

    # 2. Fallback: matching por nome fuzzy filtrado por UF
    melhor, melhor_score = None, 0.0
    for d in todos_deps:
        if norm(d.get("siglaUf", "")) != norm(uf_tse):
            continue
        score = sim_nome(nome_tse, d.get("nome", ""))
        if norm(partido_tse) == norm(d.get("siglaPartido", "")):
            score = min(1.0, score + 0.05)
        if score > melhor_score:
            melhor_score, melhor = score, d
    if melhor and melhor_score >= THRESHOLD_MATCH:
        return (melhor, melhor_score, "nome")
    return (None, melhor_score, "nome")


# ── Câmara — proposições ───────────────────────────────────────────────────────

def _paginado_camara(session: requests.Session, params_base: dict, cache_prefix: str) -> list[dict]:
    todos: list[dict] = []
    pagina = 1
    while True:
        key = f"{cache_prefix}_p{pagina}"
        params = {**params_base, "pagina": pagina, "itens": 100}
        dados = fetch_json(session, f"{CAMARA_BASE}/proposicoes", params=params, cache_key=key).get("dados", [])
        todos.extend(dados)
        if len(dados) < 100:
            break
        pagina += 1
    return todos


def buscar_proposicoes_camara(session: requests.Session, id_dep: int) -> list[dict]:
    todas: list[dict] = []
    for tipo in TIPOS_CAMARA:
        params = {
            "idDeputadoAutor": id_dep,
            "siglaTipo": tipo,
            "ordem": "DESC",
            "ordenarPor": "ano",
        }
        todas.extend(_paginado_camara(session, params, f"camara_prop_{id_dep}_{tipo}"))
    return todas


def agregar_camara(props: list[dict], detalhes: dict[int, dict]) -> dict:
    """
    Agrega proposições em KPIs.
    detalhes: dict {id_prop: dados_detalhe} com statusProposicao.codSituacao.
    """
    por_tipo: dict[str, int] = {}
    por_ano:  dict[str, int] = {}
    funil = {"aprovadas": 0, "arquivadas": 0, "em_tramitacao": 0}

    for p in props:
        t = p.get("siglaTipo", "outro")
        por_tipo[t] = por_tipo.get(t, 0) + 1

        ano = str(p.get("ano", ""))
        if ano.isdigit() and int(ano) > 2000:
            por_ano[ano] = por_ano.get(ano, 0) + 1

        cod = (detalhes.get(p["id"]) or {}).get("statusProposicao", {}).get("codSituacao")
        funil[classificar_situacao(cod)] += 1

    por_ano = dict(sorted(por_ano.items()))

    exemplos = []
    for p in props:
        ementa = (p.get("ementa") or "").strip()
        if not ementa:
            continue
        exemplos.append({
            "sigla": p.get("siglaTipo", ""),
            "numero": p.get("numero"),
            "ano": p.get("ano"),
            "ementa": ementa[:220],
            "url": f"https://www.camara.leg.br/proposicoesWeb/fichadetramitacao?idProposicao={p['id']}",
        })
        if len(exemplos) == 5:
            break

    return {
        "total_apresentadas": len(props),
        "total_aprovadas":    funil["aprovadas"],
        "funil":              funil,
        "por_tipo":           por_tipo,
        "por_ano":            por_ano,
        "exemplos":           exemplos,
    }


# ── Senado — lista de senadores ────────────────────────────────────────────────

def buscar_senadores() -> list[dict]:
    key = f"senado_senadores_{'_'.join(str(l) for l in SENADO_LEGISLATURAS)}"
    cached = cache_get(key)
    if cached is not None:
        return cached

    # Consulta cada legislatura e deduplica pelo código do parlamentar.
    # Legislatura 55 = eleitos em 2014 (mandato até 2023, candidatos à reeleição em 2022)
    # Legislatura 56 = eleitos em 2018 (mandato até 2027, não candidatos à reeleição do Senado em 2022)
    por_codigo: dict[str, dict] = {}
    for leg in SENADO_LEGISLATURAS:
        url = f"{SENADO_BASE}/senador/lista/legislatura/{leg}"
        root = fetch_xml_root(url, cache_key=f"senado_senadores_leg{leg}_xml")
        for parl in root.iter("Parlamentar"):
            ident = parl.find("IdentificacaoParlamentar")
            if ident is None:
                continue
            codigo = ident.findtext("CodigoParlamentar", "")
            if codigo and codigo not in por_codigo:
                por_codigo[codigo] = {
                    "codigo":        codigo,
                    "nome":          ident.findtext("NomeParlamentar", ""),
                    "nome_completo": ident.findtext("NomeCompletoParlamentar", ""),
                    "partido":       ident.findtext("SiglaPartidoParlamentar", ""),
                    "uf":            ident.findtext("UfParlamentar", ""),
                }

    result = list(por_codigo.values())
    cache_set(key, result)
    return result


def buscar_indice_nasc_senado(senadores: list[dict]) -> dict[tuple, dict]:
    """
    Busca o detalhe de cada senador para obter DataNascimento (não disponível na lista).
    Retorna dict {(uf, data_nascimento_iso): senador}.
    A API do Senado não expõe CPF publicamente; data de nascimento + UF é suficientemente
    único para o universo de ~160 senadores das legislaturas 55/56.
    """
    key_idx = "senado_nasc_index"
    cached = cache_get(key_idx)
    if cached is not None:
        # JSON serializa tuples como listas; re-converte as chaves
        return {(k[0], k[1]): v for k, v in (item for item in cached)}

    indice: dict[tuple, dict] = {}
    total = len(senadores)
    for i, sen in enumerate(senadores, 1):
        codigo = sen["codigo"]
        cache_key = f"senado_dep_detalhe_{codigo}"
        detalhe_raw = cache_get(cache_key)
        if detalhe_raw is None:
            print(f"    buscando nascimento dos senadores: {i}/{total}…", end="\r", flush=True)
            try:
                root = fetch_xml_root(
                    f"{SENADO_BASE}/senador/{codigo}",
                    cache_key=cache_key,
                )
                dados = root.find(".//DadosBasicosParlamentar")
                data_nasc = dados.findtext("DataNascimento", "") if dados is not None else ""
            except Exception as exc:
                print(f"\n    [aviso] falha ao buscar detalhe do senador {codigo}: {exc}")
                data_nasc = ""
            cache_set(cache_key, {"data_nascimento": data_nasc})
        else:
            data_nasc = detalhe_raw.get("data_nascimento", "")

        if data_nasc:
            chave = (norm(sen["uf"]), data_nasc)
            indice[chave] = sen

    print()
    # Serializa como lista de pares para o cache JSON (JSON não suporta tuple como chave)
    cache_set(key_idx, [[(k[0], k[1]), v] for k, v in indice.items()])
    print(f"  Índice nascimento/Senado: {len(indice)} senadores mapeados de {total}")
    return indice


def match_senador(
    nome_tse: str,
    uf_tse: str,
    partido_tse: str,
    senadores: list[dict],
    data_nasc_tse: str = "",
    indice_nasc: dict[tuple, dict] | None = None,
) -> tuple[dict | None, float, str]:
    """
    Tenta matching por data de nascimento + UF primeiro (confiança 1.0);
    fallback para nome fuzzy. Retorna (senador, confiança, método).
    A API do Senado não expõe CPF; data_nascimento+UF é o identificador mais confiável disponível.
    """
    # 1. Tentativa por data de nascimento + UF
    if data_nasc_tse and indice_nasc:
        chave = (norm(uf_tse), data_nasc_tse)
        if chave in indice_nasc:
            return (indice_nasc[chave], 1.0, "nascimento")

    # 2. Fallback: matching por nome fuzzy filtrado por UF
    melhor, melhor_score = None, 0.0
    for s in senadores:
        if norm(s.get("uf", "")) != norm(uf_tse):
            continue
        score = max(
            sim_nome(nome_tse, s.get("nome", "")),
            sim_nome(nome_tse, s.get("nome_completo", "")),
        )
        if norm(partido_tse) == norm(s.get("partido", "")):
            score = min(1.0, score + 0.05)
        if score > melhor_score:
            melhor_score, melhor = score, s
    if melhor and melhor_score >= THRESHOLD_MATCH:
        return (melhor, melhor_score, "nome")
    return (None, melhor_score, "nome")


# ── Senado — matérias ──────────────────────────────────────────────────────────

def buscar_materias_senado(session: requests.Session, nome: str, codigo: str) -> list[dict]:
    todas: list[dict] = []
    nome_norm = norm(nome).replace(" ", "_")
    for tipo in TIPOS_SENADO:
        key = f"senado_proc_{codigo}_{norm(tipo).replace(' ', '_')}"
        cached = cache_get(key)
        if cached is not None:
            dados = cached
        else:
            try:
                params = {"autoria": nome, "tipoDocumento": tipo}
                resp = fetch_json(session, f"{SENADO_BASE}/processo", params=params)
                if isinstance(resp, list):
                    dados = resp
                elif isinstance(resp, dict):
                    dados = next(
                        (v for v in resp.values() if isinstance(v, list)), []
                    )
                else:
                    dados = []
            except Exception as exc:
                print(f"    [Senado API] {tipo}: {exc}")
                dados = []
            cache_set(key, dados)
        for item in dados:
            item["_tipo_doc"] = tipo
        todas.extend(dados)
    return todas


def agregar_senado(materias: list[dict]) -> dict:
    por_tipo: dict[str, int] = {}
    total_aprovadas = 0
    exemplos: list[dict] = []

    for m in materias:
        tipo_doc = m.get("_tipo_doc", "")
        sigla = SIGLA_SENADO.get(tipo_doc, tipo_doc[:3])
        por_tipo[sigla] = por_tipo.get(sigla, 0) + 1

        if (m.get("normaGerada") or "").strip():
            total_aprovadas += 1

        if len(exemplos) < 5:
            ementa = (m.get("ementa") or "").strip()
            if ementa:
                ano_raw = (m.get("dataApresentacao") or "")[:4]
                exemplos.append({
                    "sigla":  sigla,
                    "numero": m.get("numero") or m.get("identificacao") or m.get("codigoMateria"),
                    "ano":    int(ano_raw) if ano_raw.isdigit() else None,
                    "ementa": ementa[:220],
                    "url":    m.get("urlDocumento") or "",
                })

    return {
        "total_apresentadas": len(materias),
        "total_aprovadas":    total_aprovadas,
        "por_tipo":           por_tipo,
        "exemplos":           exemplos,
    }


# ── Carga de candidatos ────────────────────────────────────────────────────────

def carregar_reeleicao() -> pd.DataFrame:
    if not CAND_JSON.exists():
        raise FileNotFoundError(
            f"{CAND_JSON} não encontrado. "
            "Execute: python ingesta_tse.py --dry-run"
        )
    df = pd.read_json(CAND_JSON, dtype={"nr_sequencial": str, "numero_eleitoral": int,
                                         "NR_CPF_CANDIDATO": str})
    ocup = df["ocupacao"].fillna("").str.upper().str.strip()

    # Diagnóstico: mostra as ocupações mais comuns nos cargos alvo
    for c in ["deputado-federal", "senador"]:
        top = df.loc[df["cargo"] == c, "ocupacao"].value_counts().head(5)
        if not top.empty:
            print(f"Top ocupações ({c}): {dict(top)}")

    mask = (
        (df["cargo"] == "deputado-federal") &
        ocup.str.contains(OCUP_DEP_PATTERN, regex=True, na=False)
    ) | (
        (df["cargo"] == "senador") &
        ocup.str.contains(OCUP_SEN_PATTERN, regex=True, na=False)
    )
    df = df[mask].copy().reset_index(drop=True)

    # Normaliza CPF para 11 dígitos (campo bruto do TSE pode ter zeros à esquerda truncados)
    df["cpf"] = df["NR_CPF_CANDIDATO"].fillna("").apply(
        lambda v: str(v).zfill(11) if re.fullmatch(r"\d{1,11}", str(v)) else re.sub(r"\D", "", str(v))
    )
    return df


# ── Pipeline principal ─────────────────────────────────────────────────────────

def processar(dry_run: bool = False) -> None:
    print("=== Ingestão legislativa (protótipo 2022) ===\n")

    df = carregar_reeleicao()
    n_dep = (df["cargo"] == "deputado-federal").sum()
    n_sen = (df["cargo"] == "senador").sum()
    print(f"Candidatos à reeleição federal: {len(df)}  ({n_dep} deputados, {n_sen} senadores)\n")

    session = requests.Session()
    session.headers.update({"Accept": "application/json"})

    print("Carregando lista de senadores (55ª e 56ª legislaturas)...")
    todos_senadores = buscar_senadores()
    print(f"  {len(todos_senadores)} senadores carregados")

    print("Construindo índice nascimento/Senado (busca detalhe de cada senador, usa cache)...")
    indice_nasc_senado = buscar_indice_nasc_senado(todos_senadores)

    print("Carregando lista de deputados (56ª legislatura)...")
    todos_deps = buscar_todos_deputados(session)
    print(f"  {len(todos_deps)} deputados carregados")

    print("Construindo índice CPF/Câmara (busca detalhe de cada deputado, usa cache)...")
    indice_cpf = buscar_indice_cpf_camara(session, todos_deps)
    print()

    registros: dict[str, dict] = {}
    depara: list[dict] = []

    for _, row in df.iterrows():
        sq        = str(row["nr_sequencial"])
        nome      = str(row["nome_urna"])
        uf        = str(row["uf"])
        partido   = str(row["partido"])
        cargo     = str(row["cargo"])
        cpf       = str(row.get("cpf", ""))
        data_nasc = str(row.get("data_nascimento", ""))

        print(f"  {nome:<40} {cargo:<20} {uf}/{partido}")

        base_depara = {
            "sq_candidato": sq, "nome_tse": nome,
            "uf": uf, "partido": partido, "cargo": cargo,
            "cpf_tse": cpf, "data_nasc_tse": data_nasc,
        }

        # ─── Deputado federal ──────────────────────────────────────────────
        if cargo == "deputado-federal":
            dep, conf, metodo = match_deputado(nome, uf, partido, todos_deps,
                                               cpf_tse=cpf, indice_cpf=indice_cpf)

            if dep is None:
                print(f"    -> SEM MATCH (conf={conf:.2f})")
                depara.append({**base_depara, "id_parlamentar": "", "nome_parlamentar": "",
                               "confianca": round(conf, 3), "status": "sem_match", "metodo": metodo})
                continue

            status = "cpf_ok" if metodo == "cpf" else ("ok" if conf >= THRESHOLD_CONFIANTE else "revisar")
            print(f"    -> {dep['nome']} (id={dep['id']}, conf={conf:.2f}, {status}, via {metodo})")
            depara.append({**base_depara, "id_parlamentar": dep["id"],
                           "nome_parlamentar": dep["nome"],
                           "confianca": round(conf, 3), "status": status, "metodo": metodo})

            if dry_run:
                continue

            props    = buscar_proposicoes_camara(session, dep["id"])
            detalhes = buscar_detalhes_paralelo([p["id"] for p in props])
            agg      = agregar_camara(props, detalhes)

            registros[sq] = {
                "sq_candidato": sq, "nome_urna": nome,
                "cargo_pretendido": cargo, "uf": uf, "partido": partido,
                "casa": "camara", "id_parlamentar": dep["id"],
                "confianca_match": round(conf, 3),
                **agg,
                "data_referencia": date.today().isoformat(),
            }

        # ─── Senador ───────────────────────────────────────────────────────
        elif cargo == "senador":
            sen, conf, metodo = match_senador(nome, uf, partido, todos_senadores,
                                              data_nasc_tse=data_nasc,
                                              indice_nasc=indice_nasc_senado)

            if sen is None:
                print(f"    -> SEM MATCH (conf={conf:.2f})")
                depara.append({**base_depara, "id_parlamentar": "", "nome_parlamentar": "",
                               "confianca": round(conf, 3), "status": "sem_match", "metodo": metodo})
                continue

            status = "nasc_ok" if metodo == "nascimento" else ("ok" if conf >= THRESHOLD_CONFIANTE else "revisar")
            print(f"    -> {sen['nome']} (cod={sen['codigo']}, conf={conf:.2f}, {status}, via {metodo})")
            depara.append({**base_depara, "id_parlamentar": sen["codigo"],
                           "nome_parlamentar": sen["nome"],
                           "confianca": round(conf, 3), "status": status, "metodo": metodo})

            if dry_run:
                continue

            materias = buscar_materias_senado(session, sen["nome"], sen["codigo"])
            agg      = agregar_senado(materias)

            registros[sq] = {
                "sq_candidato": sq, "nome_urna": nome,
                "cargo_pretendido": cargo, "uf": uf, "partido": partido,
                "casa": "senado", "id_parlamentar": sen["codigo"],
                "confianca_match": round(conf, 3),
                **agg,
                "data_referencia": date.today().isoformat(),
            }

    # ── Salva de-para ──────────────────────────────────────────────────────
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    df_depara = pd.DataFrame(depara)
    depara_path = OUTPUT_DIR / "depara.csv"
    df_depara.to_csv(depara_path, index=False, encoding="utf-8")

    cpf_ok    = (df_depara["status"] == "cpf_ok").sum()
    nasc_ok   = (df_depara["status"] == "nasc_ok").sum()
    ok        = (df_depara["status"] == "ok").sum()
    revisar   = (df_depara["status"] == "revisar").sum()
    sem_match = (df_depara["status"] == "sem_match").sum()
    total_ok  = cpf_ok + nasc_ok + ok
    print(f"\nDe-para -> {depara_path}")
    print(f"  matched={total_ok} (cpf_ok={cpf_ok}, nasc_ok={nasc_ok}, nome_ok={ok})")
    print(f"  revisar={revisar}  sem_match={sem_match}")

    if dry_run:
        print("\n[DRY RUN] Proposições não coletadas.")
        return

    # ── Salva JSON ─────────────────────────────────────────────────────────
    texto = json.dumps(registros, ensure_ascii=False, indent=2)
    out_path = OUTPUT_DIR / "legislativo.json"
    out_path.write_text(texto, encoding="utf-8")
    print(f"\nJSON → {out_path}  ({len(registros)} registros)")

    PUBLIC_DIR.mkdir(parents=True, exist_ok=True)
    pub_path = PUBLIC_DIR / "legislativo.json"
    pub_path.write_text(texto, encoding="utf-8")
    print(f"Copiado → {pub_path}")
    print("\nConcluído.")


# ── Entrypoint ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingestão legislativa 2022 (federal)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Apenas matching, sem coletar proposições")
    args = parser.parse_args()
    processar(dry_run=args.dry_run)

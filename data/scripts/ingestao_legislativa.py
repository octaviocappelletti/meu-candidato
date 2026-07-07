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
import time
import unicodedata
import xml.etree.ElementTree as ET
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
CAMARA_COD_APROVADA = 1140  # "Transformado em Norma Jurídica"

OCUP_DEP_PATTERN = r"\bDEPUTADO\b"    # TSE usa "DEPUTADO" (sem Federal/Distrital) para deputados em exercício
OCUP_SEN_PATTERN = r"\bSENADOR\b"

THRESHOLD_MATCH     = 0.70  # mínimo para incluir no de-para
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

def fetch_json(session: requests.Session, url: str, params: dict = None, cache_key: str = None):
    if cache_key:
        hit = cache_get(cache_key)
        if hit is not None:
            return hit
    for tentativa in range(4):
        time.sleep(RATE_LIMIT_S + tentativa * 2)
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


# ── Normalização de nomes ──────────────────────────────────────────────────────

def norm(s: str) -> str:
    if not s:
        return ""
    s = unicodedata.normalize("NFD", s.upper().strip())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return " ".join(s.split())


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
    Nomes de urna curtos ("DAVI", "KATIA") são subconjuntos do nome completo;
    SequenceMatcher puro penaliza isso injustamente.
    """
    base = similaridade(nome_tse, nome_parl)
    if palavras_contidas(nome_tse, nome_parl) or palavras_contidas(nome_parl, nome_tse):
        n_palavras = len(norm(nome_tse).split())
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


def match_deputado(
    nome_tse: str, uf_tse: str, partido_tse: str, todos_deps: list[dict]
) -> tuple[dict | None, float]:
    melhor, melhor_score = None, 0.0
    for d in todos_deps:
        if norm(d.get("siglaUf", "")) != norm(uf_tse):
            continue
        score = sim_nome(nome_tse, d.get("nome", ""))
        if norm(partido_tse) == norm(d.get("siglaPartido", "")):
            score = min(1.0, score + 0.05)
        if score > melhor_score:
            melhor_score, melhor = score, d
    return (melhor, melhor_score) if melhor_score >= THRESHOLD_MATCH else (None, melhor_score)


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


def buscar_aprovadas_camara(session: requests.Session, id_dep: int) -> list[dict]:
    params = {"idDeputadoAutor": id_dep, "codSituacao": CAMARA_COD_APROVADA}
    todas = _paginado_camara(session, params, f"camara_aprov_{id_dep}")
    return [p for p in todas if p.get("siglaTipo") in TIPOS_CAMARA]


def agregar_camara(props: list[dict], aprovadas: list[dict]) -> dict:
    por_tipo: dict[str, int] = {}
    for p in props:
        t = p.get("siglaTipo", "outro")
        por_tipo[t] = por_tipo.get(t, 0) + 1

    ids_aprov = {p["id"] for p in aprovadas}

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
        "total_aprovadas": len(ids_aprov),
        "por_tipo": por_tipo,
        "exemplos": exemplos,
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


def match_senador(
    nome_tse: str, uf_tse: str, partido_tse: str, senadores: list[dict]
) -> tuple[dict | None, float]:
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
    return (melhor, melhor_score) if melhor_score >= THRESHOLD_MATCH else (None, melhor_score)


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
    df = pd.read_json(CAND_JSON, dtype={"nr_sequencial": str, "numero_eleitoral": int})
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
    return df[mask].copy().reset_index(drop=True)


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

    print("Carregando lista de deputados (56ª legislatura)...")
    todos_deps = buscar_todos_deputados(session)
    print(f"  {len(todos_deps)} deputados carregados\n")

    registros: dict[str, dict] = {}
    depara: list[dict] = []

    for _, row in df.iterrows():
        sq      = str(row["nr_sequencial"])
        nome    = str(row["nome_urna"])
        uf      = str(row["uf"])
        partido = str(row["partido"])
        cargo   = str(row["cargo"])

        print(f"  {nome:<40} {cargo:<20} {uf}/{partido}")

        base_depara = {
            "sq_candidato": sq, "nome_tse": nome,
            "uf": uf, "partido": partido, "cargo": cargo,
        }

        # ─── Deputado federal ──────────────────────────────────────────────
        if cargo == "deputado-federal":
            dep, conf = match_deputado(nome, uf, partido, todos_deps)

            if dep is None:
                print(f"    -> SEM MATCH (conf={conf:.2f})")
                depara.append({**base_depara, "id_parlamentar": "", "nome_parlamentar": "",
                               "confianca": round(conf, 3), "status": "sem_match"})
                continue

            status = "ok" if conf >= THRESHOLD_CONFIANTE else "revisar"
            print(f"    -> {dep['nome']} (id={dep['id']}, conf={conf:.2f}, {status})")
            depara.append({**base_depara, "id_parlamentar": dep["id"],
                           "nome_parlamentar": dep["nome"],
                           "confianca": round(conf, 3), "status": status})

            if dry_run:
                continue

            props    = buscar_proposicoes_camara(session, dep["id"])
            aprovadas = buscar_aprovadas_camara(session, dep["id"])
            agg      = agregar_camara(props, aprovadas)

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
            sen, conf = match_senador(nome, uf, partido, todos_senadores)

            if sen is None:
                print(f"    -> SEM MATCH (conf={conf:.2f})")
                depara.append({**base_depara, "id_parlamentar": "", "nome_parlamentar": "",
                               "confianca": round(conf, 3), "status": "sem_match"})
                continue

            status = "ok" if conf >= THRESHOLD_CONFIANTE else "revisar"
            print(f"    -> {sen['nome']} (cod={sen['codigo']}, conf={conf:.2f}, {status})")
            depara.append({**base_depara, "id_parlamentar": sen["codigo"],
                           "nome_parlamentar": sen["nome"],
                           "confianca": round(conf, 3), "status": status})

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

    ok       = (df_depara["status"] == "ok").sum()
    revisar  = (df_depara["status"] == "revisar").sum()
    sem_match = (df_depara["status"] == "sem_match").sum()
    print(f"\nDe-para → {depara_path}")
    print(f"  ok={ok}  revisar={revisar}  sem_match={sem_match}")

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

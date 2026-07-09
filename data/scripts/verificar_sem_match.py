"""
Verifica os deputados federais sem correspondência no depara.csv
usando GET /api/v2/deputados?nome={query}.

Para cada candidato sem match, tenta até 3 variações de query e
exibe os resultados da API para revisão manual.

Saída:
  data/output/legislativo/sem_match_candidatos.csv   — um candidato por linha, sem resultados
  data/output/legislativo/sem_match_resultados.csv   — um resultado de API por linha (para revisão)

Uso:
    python verificar_sem_match.py
"""

import csv
import json
import re
import time
import unicodedata
from pathlib import Path

import requests

# ── Paths ─────────────────────────────────────────────────────────────────────
ROOT       = Path(__file__).parent.parent.parent
CACHE_DIR  = ROOT / "data" / ".cache" / "legislativo"
OUTPUT_DIR = ROOT / "data" / "output" / "legislativo"
DEPARA_CSV = OUTPUT_DIR / "depara.csv"
CAMARA_BASE = "https://dadosabertos.camara.leg.br/api/v2"

RATE_LIMIT_S = 0.35

# ── Prefixos de título a remover ───────────────────────────────────────────────
_TITULOS = {
    'DELEGADO', 'DELEGADA', 'CORONEL', 'CORONELA', 'CEL',
    'CAPITAO', 'CAPITA', 'CAP', 'CABO', 'SOLDADO',
    'TENENTE', 'TEN', 'MAJOR', 'SARGENTO',
    'PROFESSOR', 'PROFESSORA', 'PROF',
    'DOUTOR', 'DOUTORA', 'DR', 'DRA',
    'MEDICO', 'MEDICA', 'ENFERMEIRO', 'ENFERMEIRA',
    'VEREADOR', 'VEREADORA', 'DEPUTADO', 'DEPUTADA',
    'SENADOR', 'SENADORA', 'PREFEITO', 'PREFEITA',
    'PADRE', 'PASTOR', 'PASTORA', 'CABO',
}

# Sufixos do tipo " - NOSSA VOZ", " - POVO" etc.
_RE_SUFIXO_APELIDO = re.compile(r'\s*[-–]\s*.+$')

# Sufixos de partido ("DO PT", "DA UNIAO", etc.)
_RE_SUFIXO_PARTIDO = re.compile(
    r'\s+D[OA]S?\s+(?:PT|PL|PP|MDB|PSD|PSDB|PDT|PSB|PODE|REPUBLICANOS|UNIAO|AVANTE|'
    r'SOLIDARIEDADE|PROS|PMB|PRTB|DC|PC\s*DO\s*B|PSOL|NOVO|PATRIOTA|CIDADANIA|PV|PTB|AGIR)$'
)


# ── Normalização ───────────────────────────────────────────────────────────────

def norm(s: str) -> str:
    if not s:
        return ""
    s = unicodedata.normalize("NFD", s.upper().strip())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return " ".join(s.split())


def preparar_queries(nome_tse: str) -> list[str]:
    """
    Gera até 3 variações de query a partir do nome de urna do TSE:
      1. Nome limpo (sem sufixo de apelido e partido)
      2. Sem prefixo de título
      3. Palavra mais longa (fallback para nomes de uma palavra ou muito curtos)
    Retorna lista deduplicada mantendo a ordem.
    """
    n = nome_tse.strip()

    # Remove sufixo "- ALGO" (apelidos compostos como "CRISTINA ALMEIDA - NOSSA VOZ")
    n = _RE_SUFIXO_APELIDO.sub('', n).strip()
    # Remove sufixo de partido
    n = _RE_SUFIXO_PARTIDO.sub('', n).strip()
    # Remove vírgula e tudo após (ex: "PROFESSOR HOC, HENI OZI CUKIER")
    if ',' in n:
        n = n[:n.index(',')].strip()

    variacao1 = n  # nome já limpo

    # Sem título
    palavras = norm(n).split()
    while len(palavras) > 1 and palavras[0] in _TITULOS:
        palavras = palavras[1:]
    variacao2 = ' '.join(palavras)

    # Palavra mais longa (útil para nomes-apelido como "COBALCHINI", "VIGNATTI")
    todas_palavras = norm(n).split()
    variacao3 = max(todas_palavras, key=len) if todas_palavras else n

    vistas: list[str] = []
    for v in [variacao1, variacao2, variacao3]:
        v_clean = v.strip()
        if v_clean and norm(v_clean) not in [norm(x) for x in vistas]:
            vistas.append(v_clean)
    return vistas


# ── Cache ──────────────────────────────────────────────────────────────────────

def cache_get(key: str):
    p = CACHE_DIR / f"{key}.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def cache_set(key: str, data) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    (CACHE_DIR / f"{key}.json").write_text(
        json.dumps(data, ensure_ascii=False), encoding="utf-8"
    )


# ── API ────────────────────────────────────────────────────────────────────────

def buscar_por_nome(session: requests.Session, query: str) -> list[dict]:
    key = f"camara_busca_nome_{norm(query).replace(' ', '_')}"
    cached = cache_get(key)
    if cached is not None:
        return cached

    time.sleep(RATE_LIMIT_S)
    try:
        r = session.get(
            f"{CAMARA_BASE}/deputados",
            params={"nome": query, "itens": 20, "ordem": "ASC", "ordenarPor": "nome"},
            timeout=30,
        )
        r.raise_for_status()
        dados = r.json().get("dados", [])
        cache_set(key, dados)
        return dados
    except Exception as exc:
        print(f"    [erro] query '{query}': {exc}")
        return []


# ── Pontuação de afinidade ─────────────────────────────────────────────────────

def pontuar_resultado(res: dict, uf_tse: str, partido_tse: str) -> int:
    """Pontua um resultado da API: +2 mesma UF, +1 mesmo partido."""
    score = 0
    if norm(res.get("siglaUf", "")) == norm(uf_tse):
        score += 2
    if norm(res.get("siglaPartido", "")) == norm(partido_tse):
        score += 1
    return score


# ── Pipeline ───────────────────────────────────────────────────────────────────

def main() -> None:
    if not DEPARA_CSV.exists():
        raise FileNotFoundError(f"{DEPARA_CSV} nao encontrado. Execute ingestao_legislativa.py primeiro.")

    with open(DEPARA_CSV, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    sem_match = [r for r in rows if r["cargo"] == "deputado-federal" and r["status"] == "sem_match"]
    print(f"Candidatos sem correspondencia: {len(sem_match)}\n")

    session = requests.Session()
    session.headers.update({"Accept": "application/json"})

    linhas_resultados: list[dict] = []
    linhas_sem_resultado: list[dict] = []

    for i, cand in enumerate(sem_match, 1):
        nome_tse = cand["nome_tse"]
        uf       = cand["uf"]
        partido  = cand["partido"]
        sq       = cand["sq_candidato"]

        queries = preparar_queries(nome_tse)
        print(f"[{i:>3}/{len(sem_match)}] {nome_tse:<45} {uf}/{partido}")

        # Tenta cada variação; para quando encontrar resultados
        resultados: list[dict] = []
        query_usada = ""
        for q in queries:
            res = buscar_por_nome(session, q)
            if res:
                resultados = res
                query_usada = q
                break
            print(f"         sem resultado para '{q}'")

        if not resultados:
            print(f"         -> NENHUM RESULTADO em {len(queries)} tentativas")
            linhas_sem_resultado.append({
                "sq_candidato": sq,
                "nome_tse": nome_tse,
                "uf": uf,
                "partido": partido,
                "queries_tentadas": " | ".join(queries),
            })
            continue

        # Pontua e ordena resultados por afinidade UF+partido
        resultados_scored = sorted(
            resultados,
            key=lambda r: pontuar_resultado(r, uf, partido),
            reverse=True,
        )

        melhor = resultados_scored[0]
        score  = pontuar_resultado(melhor, uf, partido)
        flag   = "OK" if score >= 2 else ("REVISAR" if score == 1 else "VERIFICAR")

        print(f"         query='{query_usada}' | {len(resultados)} resultado(s)")
        for r in resultados_scored[:3]:
            sc = pontuar_resultado(r, uf, partido)
            print(f"           id={r['id']} | {r['nome']:<40} {r.get('siglaUf','?')}/{r.get('siglaPartido','?')} [+{sc}]")

        for r in resultados_scored:
            sc = pontuar_resultado(r, uf, partido)
            linhas_resultados.append({
                "sq_candidato":    sq,
                "nome_tse":        nome_tse,
                "uf_tse":          uf,
                "partido_tse":     partido,
                "query_usada":     query_usada,
                "qtd_resultados":  len(resultados),
                "flag":            flag if r == melhor else "",
                "id_api":          r["id"],
                "nome_api":        r["nome"],
                "uf_api":          r.get("siglaUf", ""),
                "partido_api":     r.get("siglaPartido", ""),
                "score_afinidade": sc,
            })

    # ── Salva saídas ───────────────────────────────────────────────────────────
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    path_res = OUTPUT_DIR / "sem_match_resultados.csv"
    if linhas_resultados:
        with open(path_res, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(linhas_resultados[0].keys()))
            w.writeheader()
            w.writerows(linhas_resultados)
        print(f"\nResultados -> {path_res}  ({len(linhas_resultados)} linhas)")

    path_sr = OUTPUT_DIR / "sem_match_sem_resultado.csv"
    if linhas_sem_resultado:
        with open(path_sr, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(linhas_sem_resultado[0].keys()))
            w.writeheader()
            w.writerows(linhas_sem_resultado)
        print(f"Sem resultado -> {path_sr}  ({len(linhas_sem_resultado)} candidatos)")

    # Resumo
    com_resultado = len(sem_match) - len(linhas_sem_resultado)
    ok      = sum(1 for l in linhas_resultados if l["flag"] == "OK")
    revisar = sum(1 for l in linhas_resultados if l["flag"] == "REVISAR")
    verificar = sum(1 for l in linhas_resultados if l["flag"] == "VERIFICAR")
    print(f"\nResumo:")
    print(f"  Com resultado na API : {com_resultado}")
    print(f"  Sem resultado na API : {len(linhas_sem_resultado)}")
    print(f"  Flag OK (UF bate)    : {ok}")
    print(f"  Flag REVISAR         : {revisar}")
    print(f"  Flag VERIFICAR       : {verificar}")


if __name__ == "__main__":
    main()

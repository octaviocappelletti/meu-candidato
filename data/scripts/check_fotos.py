import json
import requests
from pathlib import Path

data = json.loads(Path("../output/candidatos.json").read_text(encoding="utf-8"))
com_foto = [c for c in data if c.get("url_foto")]
sem_foto = [c for c in data if not c.get("url_foto")]
print(f"Total: {len(data)} | Com url_foto: {len(com_foto)} | Sem url_foto: {len(sem_foto)}")
print()

# Mostra as primeiras URLs
for c in com_foto[:5]:
    print(c["nome_urna"])
    print(" ", c["url_foto"])
print()

# Testa se as URLs são acessíveis
print("Testando acesso HTTP das primeiras 3 fotos:")
for c in (com_foto or data)[:3]:
    url = c["url_foto"]
    try:
        r = requests.head(url, timeout=10, allow_redirects=True)
        print(f"  {r.status_code} - {url}")
    except Exception as e:
        print(f"  ERRO - {e} - {url}")

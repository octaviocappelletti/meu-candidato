import io, zipfile, requests

url = "https://cdn.tse.jus.br/estatistica/sead/eleicoes/eleicoes2022/fotos/foto_cand2022_BR_div.zip"
print(f"Baixando {url} ...")
r = requests.get(url, timeout=30)
zf = zipfile.ZipFile(io.BytesIO(r.content))
names = zf.namelist()
print(f"Total de arquivos: {len(names)}")
print("Primeiros 10:")
for n in names[:10]:
    info = zf.getinfo(n)
    print(f"  {n}  ({info.file_size/1024:.1f} KB)")

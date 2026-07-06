Meu Candidato

Plataforma web para conferência de informações básicas de candidatos às eleições
brasileiras de 2026. O usuário escolhe um cargo, (se for cargo estadual) escolhe o
estado, e vê a lista de candidatos com nome, foto e número eleitoral, podendo
favoritar candidatos. É um catálogo somente leitura de dados públicos oficiais.

Princípios do projeto


Neutralidade acima de tudo. A ordem, o destaque e a apresentação dos candidatos
jamais devem favorecer ninguém. Listas sempre em ordem alfabética. Sem posição paga,
sem selo pago, sem ranking. A credibilidade é o único ativo do produto.
Dados oficiais. A única fonte de dados de candidatura é o TSE (Dados Abertos /
DivulgaCand). Nunca inventar, estimar ou completar dados de candidato.
Privacidade primeiro. Não coletamos dado pessoal do usuário. Sem login, sem
rastreamento invasivo. Favoritos ficam só no dispositivo.
Simples e barato. Arquitetura estática sempre que possível, servida por CDN.


Stack e decisões (já definidas — não trocar sem discutir)


Front-end: Next.js (React) + TypeScript.
Estilo: Tailwind CSS.
Ingestão de dados: Python (pandas) para baixar, limpar e normalizar os CSVs do TSE.
Banco de dados: Supabase (Postgres gerenciado).
Hospedagem: Vercel.
Favoritos: localStorage no navegador (sem autenticação).
Versão mobile: PWA (manifest + service worker) ao final do projeto. Sem app nativo.


Fluxo de telas


Tela 1 — Escolha do cargo: presidente/vice, governador/vice, senador,
deputado federal, deputado estadual.
Tela 2 — Escolha do estado: aparece apenas para cargos estaduais
(governador, deputado estadual, senador). Cargos federais (presidente) pulam
esta tela e vão direto para a lista.
Tela 3 — Lista de candidatos:

Cabeçalho com breve descrição das atribuições e responsabilidades do cargo.
Barra de filtros de busca (por nome e número).
Lista de candidatos ordenada alfabeticamente, cada item com: nome, foto,
número eleitoral e um checkbox em formato de coração para favoritar.





Regra cargo federal vs. estadual


Federal (pula tela de estado): Presidente/Vice.
Estadual (exige escolha de estado): Governador/Vice, Senador, Deputado Federal
(eleito por estado), Deputado Estadual.



Observação: apesar do nome, deputado federal e senador são eleitos por estado,
então também exigem a Tela 2. Só a Presidência é nacional. Confirmar essa regra
ao implementar o roteamento.



Estrutura de pastas

meu-candidato/
  data/
    scripts/           # ingestão do TSE (baixar, limpar, normalizar) — Python
    output/            # JSONs/CSVs normalizados por cargo/estado
  src/
    app/
      page.tsx                       # Tela 1: escolha do cargo
      [cargo]/
        page.tsx                     # Tela 2: escolha do estado (só cargos estaduais)
        [estado]/
          page.tsx                   # Tela 3: lista de candidatos
    components/
      CardCandidato.tsx
      BarraDeBusca.tsx
      BotaoFavoritar.tsx             # o coração
      DescricaoCargo.tsx
    lib/
      cargos.ts                      # descrições/atribuições dos cargos
      favoritos.ts                   # wrapper do localStorage
      supabase.ts                    # cliente Supabase (se consultado em runtime)
    styles/
  public/
    manifest.json                    # PWA
    icons/                           # ícones do PWA
    fotos/                           # cache das fotos dos candidatos (opcional)

Pipeline de dados (TSE)


Fonte: https://dadosabertos.tse.jus.br/ (candidaturas em CSV por UF/cargo) e a
API do DivulgaCand para fotos e detalhes.
Processo: script Python baixa → limpa → normaliza → grava no Supabase e/ou
exporta JSON por cargo/estado.
Campos mínimos por candidato: nome de urna, nome completo, número eleitoral,
cargo, UF, partido, situação da candidatura (deferido/indeferido/etc.), URL da foto.
Atualização: as candidaturas mudam durante o período eleitoral (registro,
deferimento, substituição). Reprocessar periodicamente (ex.: job diário) até a
eleição. Sempre exibir apenas candidaturas válidas/aptas conforme a situação do TSE.
Fotos: otimizar/redimensionar antes de servir (a banda de imagens é o maior
custo potencial). Considerar cache/CDN.


Favoritos (localStorage)


Guardar apenas a lista de números eleitorais (identificador estável), ex.:
localStorage.setItem('favoritos', JSON.stringify([12345, 67890])).
Toda a lógica isolada em src/lib/favoritos.ts (funções getFavoritos,
toggleFavorito, isFavorito).
Os dados vivem só no dispositivo/navegador. Não sincronizam entre aparelhos e
isso é aceitável nesta versão.
Não enviar favoritos para servidor nenhum (preferência política é dado
sensível pela LGPD).
Opcional futuro: botão "exportar/importar minha lista" via código/link, para dar
portabilidade sem login.


PWA (versão mobile — etapa final)


Adicionar public/manifest.json (nome, ícones, display: standalone, cores).
Service worker para cache do app shell e funcionamento offline básico.
Site deve ser responsivo desde o início (mobile-first), para o PWA só
"empacotar" o que já existe.
Sem app nativo e sem publicação em lojas nesta versão.


Convenções


TypeScript em todo o front-end; evitar any.
Componentes em português no domínio (Candidato, Cargo, Favorito) para alinhar com
o negócio.
Ordenação alfabética por nome de urna, com localeCompare('pt-BR').
Acessibilidade: o botão de favoritar deve ter aria-label e ser navegável por
teclado.
Textos de atribuições dos cargos centralizados em src/lib/cargos.ts.


Variáveis de ambiente / segredos


NEXT_PUBLIC_SUPABASE_URL, NEXT_PUBLIC_SUPABASE_ANON_KEY para o cliente.
Chave de service role do Supabase apenas nos scripts de ingestão (nunca no
front-end).
Nunca commitar segredos; usar .env.local e variáveis na Vercel.


O que evitar


Qualquer forma de destaque/posicionamento pago de candidatos (risco legal —
propaganda eleitoral paga — e perda de neutralidade).
Coletar, armazenar ou transmitir dados pessoais do usuário.
Exibir candidatos com situação inapta como se fossem válidos.
Trocar decisões de stack já fechadas sem alinhamento.
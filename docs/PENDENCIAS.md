# Pendências e divergências conhecidas

Coisas encontradas durante a automação que **não** foram tratadas, para não
misturar com o trabalho em andamento. Nenhuma delas impede a publicação atual.

---

## 1. Botões faltando em /startups/

A grade de botões de [inova.ufpr.br/startups](https://inova.ufpr.br/startups/)
tem 21 botões, mas nem todas as abas publicáveis aparecem lá.

**Sem botão na página:**

| Aba | Situação |
|---|---|
| `RETAILTECHS` | Página existe e está publicada — o botão sumiu da grade em algum momento |
| `FASHIONTECHS` | Em tratamento |
| `GAMETECHS` | Em tratamento |
| `INSURTECHS` | Em tratamento |
| `TRAVELTECHS` | Em tratamento |

`RETAILTECHS` é o caso mais claro: a página `/retailtechs-2/` está no ar e
mapeada no `config.py`, mas quem entra por `/startups/` não chega nela.

---

## 2. `PET TECHS` vs `PETTECHS`

| Onde | Grafia |
|---|---|
| Botão em /startups/ | `PET TECHS` (com espaço) |
| Aba na planilha | `PETTECHS` |
| Slug da página | `/pet-techs/` |

São a mesma coisa. A comparação normalizada não casa as duas (`PET TECHS` vira
`PET TECHS`, `PETTECHS` vira `PETTECHS`), então qualquer automação que compare
botões com abas vai tratá-las como itens diferentes.

**Mudar só o rótulo do botão** para `PETTECHS` é seguro e resolve a
comparação — não mexe na página nem na URL.

Alinhar também o slug (`/pet-techs/` → `/pettechs/`) é outra história: cai no
item 3 abaixo, com os riscos descritos lá.

---

## 3. Padronizar as URLs dos botões

**Levantamento feito em 30/07/2026: 11 dos 25 botões não seguem o padrão**
`https://inova.ufpr.br/<nome-em-minúsculo>/`.

São dois casos bem diferentes, e a distinção importa:

### Caso A — a página já está no lugar certo; só o botão aponta para o antigo

Verificado na API: essas páginas **já existem na raiz**. O botão é que aponta
para um endereço antigo (provavelmente com redirecionamento).

| Botão | Link atual | Página real (confirmada) |
|---|---|---|
| AGTECHS | `/home/agtechs/` | `/agtechs/` (id 4813) |
| CONSTRUTECHS E PROPTECHS | `/home/construtechs-e-proptechs/` | `/construtechs-e-proptechs/` (id 5200) |
| EDTECHS | `/home/edtechs/` | `/edtechs/` (id 4864) |
| FINTECHS | `/home/fintechs/` | `/fintechs/` (id 4943) |
| LAWTECHS E LEGALTECHS | `/home/lawtechs-e-legaltechs/` | `/lawtechs-e-legaltechs/` (id 5205) |
| LOGTECHS | `/home/logtechs/` | `/logtechs/` (id 5180) |
| MARTECHS | `/home/martechs/` | `/martechs/` (id 5193) |
| SOCIALTECHS | `/home/startups/socialtechs` | `/socialtechs/` (id 5463) |
| TECHS | `/home/techs/` | `/techs/` (id 5149) |

**Risco baixo.** Basta corrigir o link do botão — a página não é tocada, o
slug não muda, nada quebra. É só apontar o botão para onde a página já está.

### Caso B — o slug da página é realmente diferente

| Botão | Página real | Slug padronizado |
|---|---|---|
| DEEPTECHS | `/biotechs/` (id 5335) | `/deeptechs/` — **não existe** |
| HEALTHTECHS | `/health-tech/` (id 4894) | `/healthtechs/` — **não existe** |
| PET TECHS | `/pet-techs/` (id 6122) | `/pettechs/` — **não existe** |

**Risco alto.** Padronizar exige renomear o slug de páginas publicadas, o que:

- Quebra links externos que apontem para o endereço atual
- Tira as páginas da indexação de busca até serem reindexadas
- Quebra links internos do site que usem o endereço antigo
- Exige atualizar `ABAS_LINKS` no `src/config.py` junto, senão a publicação
  deixa de encontrar a página

Se for feito, o caminho seguro é: renomear o slug **e** criar um
redirecionamento do endereço antigo para o novo (plugin de redirect ou regra
no servidor), nunca renomear e deixar o antigo dar 404.

### Recomendação

Tratar o **Caso A separadamente** — é ganho real com risco quase nulo, e
resolve 9 dos 11 desalinhamentos.

O **Caso B** merece decisão consciente: `DEEPTECHS` apontando para
`/biotechs/` sugere que a categoria foi renomeada em algum momento e a URL
ficou para trás. Vale conferir o histórico antes de mexer.

---

## 5. `AGTECHS` tem botão mas está ignorada

A aba `AGTECHS` está em `ABAS_IGNORADAS` no `config.py` — ou seja, a automação
não publica nada nela. Mas existe botão para ela em /startups/, apontando para
`/home/agtechs/`, e a página `/agtechs/` está no ar.

Ou a página é mantida à mão (e a aba deveria continuar ignorada), ou a aba
deveria voltar a ser publicada. Vale confirmar com quem cuida do conteúdo.

---

## 6. Abas em `ABAS_PAIS` sem coluna de país ✅ resolvido

`POLÍTICAS DE INOVAÇÃO` (tem `UF`) e `PROPRIEDADE INTELECTUAL` (tem `PAÍS`)
estavam em `ABAS_SEM_GEOGRAFIA`, que remove o filtro geográfico inteiro. Por
isso o site mostrava apenas Organização e Categoria, escondendo a coluna que
existia na planilha.

As duas saíram de `ABAS_SEM_GEOGRAFIA` em 31/07/2026. O gerador detecta a
coluna pelo nome e exibe só a que existe, então cada uma passa a mostrar a sua:

| Aba | Colunas |
|---|---|
| POLÍTICAS DE INOVAÇÃO | Organização · UF · Categoria |
| PROPRIEDADE INTELECTUAL | Organização · PAÍS · Categoria |

`ASSOCIAÇÕES EMPRESARIAIS` continua em `ABAS_PAIS` tendo apenas `UF` — o que
funciona: o gerador mostra a coluna UF e omite a de país. Não é problema, só
um nome de lista que não descreve bem o caso.

`PERÍODICOS CIENTÍFICOS` segue sem geografia por decisão de conteúdo, embora
tenha a coluna `PAÍS` na planilha. Confirmar se é intencional.

---

## 7. Aba `TESTE` publica no site

A aba `TESTE` está mapeada para `https://inova.ufpr.br/teste/` e é publicada
normalmente quando marcada em `CHECAR ABAS`. Se for aba de rascunho, deveria
sair de `ABAS_LINKS`.

---

## 8. Falsos positivos na checagem de links

`checarLinksErros` no Apps Script marca como quebrados links que funcionam no
navegador — muitos sites bloqueiam requisições automatizadas. A função já
tolera HTTP 403 e 500, mas há outros casos (timeout, bloqueio por user-agent,
Cloudflare).

A aba `CHECAR ABAS` tem hoje várias entradas assim.

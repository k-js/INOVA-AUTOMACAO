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

Decidir qual grafia é a oficial e alinhar as três.

---

## 3. `AGTECHS` tem botão mas está ignorada

A aba `AGTECHS` está em `ABAS_IGNORADAS` no `config.py` — ou seja, a automação
não publica nada nela. Mas existe botão para ela em /startups/, apontando para
`/home/agtechs/`, que está no ar.

Ou a página é mantida à mão (e a aba deveria continuar ignorada), ou a aba
deveria voltar a ser publicada. Vale confirmar com quem cuida do conteúdo.

---

## 4. URLs inconsistentes entre os botões

Os botões de /startups/ usam três padrões diferentes:

```
https://inova.ufpr.br/home/agtechs/            <- com /home/
https://inova.ufpr.br/indtechs                 <- sem barra final
https://inova.ufpr.br/biotechs/                <- slug diferente do nome (DEEPTECHS)
https://inova.ufpr.br/home/startups/socialtechs  <- caminho aninhado
```

Todos funcionam hoje, então **não devem ser "corrigidos" sem verificar** — o
WordPress pode estar redirecionando, e mexer nisso quebraria links que estão
em uso, inclusive links externos e indexação de busca.

Qualquer automação sobre esses botões deve **preservar as URLs existentes** e
só definir a URL de botões novos.

---

## 5. Abas em `ABAS_PAIS` sem coluna de país

`ASSOCIAÇÕES EMPRESARIAIS` e `POLÍTICAS DE INOVAÇÃO` estão em `ABAS_PAIS` no
`config.py`, mas as duas têm apenas a coluna `UF` — não têm `CIDADE` nem
`PAÍS`. O gerador de país não encontra a coluna e o filtro sai incompleto.

Decidir caso a caso: acrescentar a coluna `PAÍS` na planilha, ou tirar a aba
de `ABAS_PAIS`.

---

## 6. Aba `TESTE` publica no site

A aba `TESTE` está mapeada para `https://inova.ufpr.br/teste/` e é publicada
normalmente quando marcada em `CHECAR ABAS`. Se for aba de rascunho, deveria
sair de `ABAS_LINKS`.

---

## 7. Falsos positivos na checagem de links

`checarLinksErros` no Apps Script marca como quebrados links que funcionam no
navegador — muitos sites bloqueiam requisições automatizadas. A função já
tolera HTTP 403 e 500, mas há outros casos (timeout, bloqueio por user-agent,
Cloudflare).

A aba `CHECAR ABAS` tem hoje várias entradas assim.

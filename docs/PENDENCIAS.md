# Pendências e divergências conhecidas

Coisas encontradas durante a automação que **não** foram tratadas, para não
misturar com o trabalho em andamento. Nenhuma delas impede a publicação atual.

---

## 1. Botões faltando em /startups/ — RESOLVIDO

| Aba | Desfecho |
|---|---|
| `FASHIONTECHS` | botão criado |
| `GAMETECHS` | botão criado |
| `INSURTECHS` | botão criado |
| `TRAVELTECHS` | botão criado |
| `RETAILTECHS` | **não leva botão** — decisão da equipe, 13/08/2026 |

`RETAILTECHS` continua publicada e mapeada no `config.py`, mas fica fora da
grade de /startups/ por decisão de conteúdo. Não é falha a corrigir.

O mesmo vale, ao contrário, para `AGTECHS`: tem botão e não é publicada por
esta automação, porque a página dela leva a outro portfólio (item 5).

Em comum: **a grade de /startups/ não espelha `ABAS_LINKS`**. Uma automação que
tentasse igualar as duas listas apagaria o botão da AGTECHS e criaria o da
RETAILTECHS — desfazendo as duas decisões de uma vez.

---

## 2. `PET TECHS` vs `PETTECHS` — RESOLVIDO

O botão em /startups/ exibia `PET TECHS`, com espaço, enquanto a aba se chama
`PETTECHS`. O rótulo foi corrigido na sincronização de botões; a URL
(`/pet-techs/`) ficou como estava.

Alinhar também o slug (`/pet-techs/` → `/pettechs/`) é outra história, e cai no
Caso B do item 3.

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

### Caso A — RESOLVIDO em 13/08/2026

Medido no site: `/home/...` responde **301** para o endereço canônico, e
`/home/startups/socialtechs` chega a dar **três saltos**. O primeiro salto de
cada um passa por `http://` antes de voltar para `https://`.

`sincronizar_botoes.py --normalizar-urls` aponta cada botão direto para o
destino. Ele **pergunta ao site** qual é o destino em vez de deduzir do rótulo —
deduzir erraria justamente no Caso B, onde o slug não segue o nome.

Isso não afeta link já compartilhado: o redirecionamento é do WordPress e
continua existindo. Só muda o destino de quem clica a partir da grade.

### Caso B — em aberto

Merece decisão consciente: `DEEPTECHS` apontando para `/biotechs/` sugere que a
categoria foi renomeada em algum momento e a URL ficou para trás. Vale conferir
o histórico antes de mexer.

Diferença essencial para o Caso A: ali o link antigo continua existindo; aqui
ele **deixa de existir**, e é o link já compartilhado que quebra — a menos que
se crie o redirecionamento à mão.

---

## 5. `AGTECHS` tem botão mas está ignorada — NÃO É PENDÊNCIA

Confirmado com a equipe em 13/08/2026: a página `/agtechs/` leva a **outro
portfólio** e não é alimentada por esta planilha. Está correta como está.

A aba continua em `ABAS_IGNORADAS` e o botão continua em /startups/ — nenhum
dos dois é erro. O comentário no `config.py` registra isso, para que uma
leitura futura não a "conserte" achando que faltava criar a página.

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

## 7. Aba `TESTE` publica no site — RESOLVIDO

A aba `TESTE` estava mapeada em `ABAS_LINKS` para `https://inova.ufpr.br/teste/`,
página que nunca existiu: toda execução gastava uma tentativa nela e terminava
com um aviso. Confirmado que é aba de teste da equipe e não vira página do
site, foi movida para `ABAS_IGNORADAS`.

---

## 8. Falsos positivos na checagem de links — RESOLVIDO

`checarLinksErros` marcava como quebrado tudo que não fosse HTTP 200, 403 ou
500 — inclusive 301, 429, 503 e qualquer exceção. A aba `CHECAR ABAS` enchia de
links sãos, e a lista deixava de ser confiável.

Três mudanças, em 13/08/2026:

**Cabeçalho de navegador.** O Apps Script se identificava como robô do Google, e
boa parte dos firewalls responde 403 a isso. Era a maior causa isolada.

**Classificação em vez de binário.** `classificarResposta()` separa três casos:

| Situação | O que é | Vai para a aba? |
|---|---|---|
| `ok` | 2xx e 3xx | não |
| `quebrado` | 404, 410, domínio que não resolve | **sim** |
| `inconclusivo` | site recusou o robô (401/403/405/406/409/418/429/503), servidor fora (5xx), demora, certificado | não — só a contagem no relato |

**Repetição única na demora.** Site lento que responde na segunda tentativa
deixa de virar falso positivo. Não repete veredito conclusivo: repetir um 404
só gasta tempo.

A coluna F passa a trazer o motivo. Para listar também os inconclusivos, mude
`LISTAR_INCONCLUSIVOS` para `true` no início da função.

### A paginação nunca funcionou — RESOLVIDO em 14/08/2026

Descoberto ao investigar um `Ocorreu um erro desconhecido` (erro genérico do
Google) que derrubou a execução aos 2min39s.

A função guardava a lista inteira de links em `PropertiesService`. **O limite é
de 9 KB por propriedade**, e o JSON de mais de mil links passa de 100 KB: a
gravação sempre falhava, caía no `catch`, apagava os ponteiros — e a execução
seguinte recomeçava do zero. A mensagem "rode de novo até concluir" nunca
chegava ao fim.

Somava-se a isso: links quebrados e posição só eram gravados **ao fim do lote**.
Qualquer queda no meio levava junto tudo o que já tinha sido descoberto.

| Antes | Agora |
|---|---|
| lista inteira em `PropertiesService` (>100 KB vs. limite de 9 KB) | recoletada a cada execução (`coletarLinks`), sem rede |
| posição salva ao fim do lote | salva **a cada link** (dois números curtos) |
| quebrados gravados ao fim do lote | gravados na hora em que são achados |
| nada no log | URL logada **antes** do fetch |
| sem guarda de tempo | para aos 4 min, longe do corte de 6 min |

A URL no log é o que permite saber em qual link o Google derrubou a execução —
sem ela o erro é anônimo. Como a posição é validada contra `totalLinks`, mexer
na planilha entre rodadas faz a checagem recomeçar em vez de pular linhas.

`SpreadsheetApp.getActive().toast()` saiu daqui e de `padronizarAbas`: devolve
`null` em acionador de tempo, a mesma armadilha que `obterPlanilha()` resolve.

### São 4.595 links — a checagem passou a rodar sozinha

Medido no primeiro log que chegou ao fim de um lote:

| | |
|---|---|
| links na planilha | **4.595** |
| coleta das abas | ~31 s por rodada |
| fetch | ~1,3 s por link |
| total de rede | **~100 minutos** |

Com `LOTE_TAMANHO = 40` seriam **115 execuções manuais**. O teto subiu para 500
— quem governa o lote é a guarda de tempo de 4 min, e cabem ~150 links por
rodada, ou seja ~30 rodadas.

Trinta cliques ainda é o mesmo problema em menor escala, então entrou um
acionador de tempo: `iniciarChecagemAutomatica()` roda uma rodada a cada 5 min
e **`checarLinksErros` apaga o próprio acionador ao concluir** — sem isso ele
encontraria os ponteiros zerados e recomeçaria a checagem para sempre. Ambos no
menu **CHECAR LINKS** da planilha.

Isso só é seguro porque o progresso passou a ser salvo link a link.

⚠️ Conta pessoal do Google tem cota de **90 min/dia** de execução de script; a
varredura completa passa disso e continua no dia seguinte, do ponto onde parou.
Em conta Workspace (6 h/dia) cabe de uma vez.

### `ID_PLANILHA` saiu do código

Preenchido na constante, era apagado a cada `Ctrl+A` no editor — e os
acionadores de tempo paravam sem avisar. Agora `obterPlanilha()` chama
`idDaPlanilha()`, que lê **Configurações do projeto → Propriedades do script**
quando a constante está vazia. A leitura é preguiçosa de propósito: no escopo
global, `PropertiesService` falhando em `onOpen()` (acionador simples, com
autorização reduzida) derrubaria o menu da planilha.



# Manutenção — o que fazer quando a planilha muda

Este é o guia para as situações que mais quebram a automação: **alguém renomeia
uma aba, cria uma aba nova, ou muda o nome de uma coluna no Google Sheets.**

A regra geral: **rode a validação antes de publicar.** Ela lê a planilha e
avisa o que está fora do lugar, em vez de você descobrir pelo site quebrado.

---

## 🔍 Como validar (sem risco)

A validação **não publica nada** e **não altera a planilha** — só lê e relata.

**Pelo GitHub (recomendado, é onde ficam as credenciais):**

1. Abra a aba **Actions** do repositório
2. Escolha **"Validar planilha (somente leitura)"** na lista à esquerda
3. Clique em **"Run workflow"**
4. Abra a execução e leia a saída

Ela também roda sozinha todo dia às 08:00 UTC — duas horas antes da
publicação — para que uma divergência apareça antes de virar erro.

**Localmente** (só se você tiver as credenciais em `credenciais/.env`):

```bash
python validar.py
```

---

## 📝 Situação 1: uma aba foi renomeada

**Sintoma:** a publicação falha com `Link não mapeado`, ou a página do site
para de atualizar sem erro aparente.

O validador aponta assim:

```
❌ Aba 'INSTITUTOS DE PESQUISA E CENTROS DE T&L' está em ABAS_LINKS mas não
   existe na planilha.
   Provavelmente foi renomeada para: 'INSTITUTOS DE PESQUISA E CENTROS DE T&I'
   → Atualize a chave em config.py (ABAS_LINKS).
```

**O que fazer:** abra [config.py](config.py) e corrija o nome. Ele aparece em
`ABAS_LINKS` e, dependendo da aba, também em `ABAS_PAIS` ou
`ABAS_SEM_GEOGRAFIA` — confira as três.

> ⚠️ O nome tem que bater **exatamente** com o Google Sheets, incluindo acentos
> e o `&`. Copie e cole da planilha em vez de digitar.

---

## ➕ Situação 2: uma aba nova foi criada

O validador avisa:

```
⚠️  Aba 'GAMETECHS' existe na planilha mas não tem página mapeada.
```

**Se a página já existe no site**, adicione em `ABAS_LINKS` no [config.py](config.py):

```python
"GAMETECHS": "https://inova.ufpr.br/gametechs/",
```

E confirme que a página do WordPress tem o marcador, senão a publicação falha:

```html
<!-- COMECA ATUALIZAR DAQUI -->
<table></table>
```

**Se a página ainda não existe**, adicione o nome em `ABAS_IGNORADAS` para
silenciar o aviso até criar a página.

> Hoje estão aguardando página: `AGTECHS`, `BEAUTYTECHS`, `EVENTECHS`,
> `FASHIONTECHS`, `GAMETECHS`, `INSURTECHS`, `PORTAIS DE NOTÍCIAS`,
> `SECURITYTECHS`, `SPORTECHS`, `TRAVELTECHS`.

---

## 🔤 Situação 3: uma coluna mudou de nome

**Sintoma:** a tabela é publicada, mas uma informação some — os balões ficam
vazios, ou o filtro de país não aparece. Normalmente **sem erro nenhum**.

O validador aponta:

```
❌ Aba 'FINTECHS': coluna obrigatória 'CATEGORIA' não encontrada.
   Parecido no cabeçalho: ['CATEGORIAS']
```

**O que fazer:** o mais seguro é **renomear de volta na planilha**, já que
todas as abas seguem o mesmo padrão. Se a mudança for intencional e definitiva,
altere a constante correspondente no [config.py](config.py) (`COL_CATEGORIA`,
`COL_BALAO`, etc.).

**Acento e maiúscula não são problema.** O código já compara os nomes
ignorando os dois: `PAÍS`, `PAIS` e `País` são tratados como iguais. O mesmo
vale para a coluna de identificação, que pode ser `NOME` ou `ORGANIZAÇÃO`.

---

## 📐 Colunas esperadas

| Coluna | Obrigatória | Observação |
|---|---|---|
| `NOME` ou `ORGANIZAÇÃO` | Sim | Qualquer uma das duas serve |
| `CATEGORIA` | Sim | Alimenta o filtro de categoria |
| `LINK` | Sim | URL da organização |
| `STATUS` | Sim | `ADICIONAR AO SITE`, `EDITAR`, `REMOVER` |
| `CONTEÚDO BALÃO` | Não | Sem ela, os tooltips ficam vazios |
| `UF` | Não | Filtro de estado |
| `CIDADE` / `PAÍS` | Não | Filtro geográfico secundário |

`PITCHS DE STARTUPS` tem estrutura própria (`SEGMENTO`, `INSTITUIÇÃO`) e é
tratada por um gerador separado.

---

## 🤖 Apps Script

O código que roda dentro da planilha está versionado em
[apps-script/Codigo.gs](apps-script/Codigo.gs).

Ele **não é sincronizado automaticamente** com a planilha. Ao alterar um dos
lados, replique no outro (Extensões → Apps Script no Google Sheets).

Os nomes de aba também aparecem lá — em `abasIgnoradas` e no mapeamento de
`copiarPRParaMapaPowerBI`. Ao renomear uma aba, confira os dois lugares.

---

## ⚠️ Antes de publicar

1. Rode a validação e resolva os **erros** (avisos podem esperar)
2. Confirme que a aba está listada em `CHECAR ABAS` na planilha
3. Confirme que a página do WordPress tem o marcador
   `<!-- COMECA ATUALIZAR DAQUI -->`

A publicação roda sozinha todo dia às **10:00 UTC**, ou manualmente em
Actions → "Atualizar INOVA" → "Run workflow".

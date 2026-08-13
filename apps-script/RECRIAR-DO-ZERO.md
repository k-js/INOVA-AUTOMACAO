# Recriar o Apps Script do zero

Se o projeto do Apps Script for excluído, os arquivos deste diretório são a
cópia completa. Nada se perde: o repositório é a fonte da verdade.

Tempo: cerca de 5 minutos.

---

## Passo 1 — Abrir o editor pela planilha

**Não crie um projeto avulso em script.google.com.** O projeto precisa estar
vinculado à planilha, senão o menu "CHECAR LINKS" não aparece nela.

1. Abra a planilha **PORTAL DA INOVAÇÃO E STARTUPS**
2. Menu **Extensões → Apps Script**

Isso cria um projeto novo já vinculado, com um `Código.gs` vazio.

---

## Passo 2 — Nomear o projeto

No topo, onde está "Projeto sem título", clique e renomeie para:

```
CheckExcel
```

Só organização — o nome não afeta o funcionamento.

---

## Passo 3 — Colar o Codigo.gs

1. No arquivo **`Código.gs`**, apague o `function myFunction() {}` que vem
   por padrão
2. Cole todo o conteúdo de [Codigo.gs](Codigo.gs)
3. **Salve** (`Ctrl+S`)

---

## Passo 4 — Criar o Dialog.html

1. Ao lado de "Arquivos", clique em **+** → **HTML**
2. Nomeie exatamente **`Dialog`** — sem `.html`, o editor acrescenta sozinho

   > ⚠️ O nome precisa ser esse. O `Codigo.gs` o referencia pela constante
   > `ARQUIVO_DIALOGO`. Se usar outro nome, atualize a constante junto.

3. Apague o conteúdo padrão e cole [Dialog.html](Dialog.html)
4. **Salve**

---

## Passo 5 — Preencher o ID da planilha

Na URL da planilha, copie o trecho entre `/d/` e `/edit`:

```
docs.google.com/spreadsheets/d/ESTE_TRECHO_AQUI/edit
```

No `Codigo.gs`, procure a linha (perto da 112):

```javascript
var ID_PLANILHA = '';  // ← preencher com o ID da planilha
```

E preencha:

```javascript
var ID_PLANILHA = 'o_id_que_voce_copiou';
```

**Este passo é obrigatório para os acionadores automáticos.** Sem ele,
`checarAbasComStatus` funciona pelo editor mas falha quando roda sozinho —
foi exatamente o problema que estávamos corrigindo.

---

## Passo 6 — Recriar os acionadores

Ícone de **relógio** (⏰) na barra lateral → **Adicionar acionador**.

Os que existiam antes:

| Função | Tipo | Quando |
|---|---|---|
| `checarAbasComStatus` | Baseado no tempo | Diariamente, ~03:00 |
| `padronizarAbas` | Baseado no tempo | Diariamente, ~05:00 |

Para cada um:

1. **Função a ser executada**: escolha na lista
2. **Origem do evento**: "Baseado no tempo"
3. **Tipo**: "Timer de dia"
4. **Hora**: veja a observação abaixo
5. Salvar

> ⚠️ `checarAbasComStatus` precisa rodar **antes** da publicação diária, que
> é às 10:00 UTC (por volta das 07:00 em Brasília). Um horário entre 03:00 e
> 05:00 dá margem folgada.

**Não recrie** acionador para `copiarPRParaMapaPowerBI` nem `consolidarAbas`:
essas funções foram removidas por estarem abandonadas.

---

## Passo 7 — Autorizar e testar

1. Com `checarAbasComStatus` selecionado, clique em **Executar**
2. Na primeira vez o Google pede autorização — aceite

   > A tela "app não verificado" é esperada: é um script seu, não publicado.
   > Clique em "Avançado" → "Acessar CheckExcel (não seguro)".

3. **Esperado:** um alerta dizendo quantas abas têm alterações pendentes

Depois, teste o menu: recarregue a planilha (F5) e confira se **CHECAR LINKS**
aparece na barra de menus.

---

## Se algo não funcionar

O erro mais provável é o `ID_PLANILHA` vazio. A mensagem é explícita:

```
Sem planilha ativa (execução por acionador de tempo) e ID_PLANILHA está vazio.
```

Nesse caso, volte ao Passo 5.

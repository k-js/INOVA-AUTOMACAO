# Como atualizar o Apps Script na planilha

O código deste diretório **não sincroniza sozinho** com a planilha. Para as
correções valerem, o conteúdo precisa ser colado no editor do Apps Script.

Enquanto isso não for feito, a planilha continua rodando a versão antiga — o
que é seguro, só não tem as correções.

---

## Antes de começar

**Faça uma cópia de segurança do código atual.** Leva 30 segundos e permite
voltar atrás:

1. Abra a planilha → **Extensões → Apps Script**
2. Em `Codigo.gs`, selecione tudo (`Ctrl+A`) e copie (`Ctrl+C`)
3. Cole num arquivo de texto qualquer e salve

O Apps Script tem histórico de versões próprio (**Implantações → Histórico**),
mas a cópia manual é mais direta para reverter.

---

## Passo 1 — Codigo.gs

1. No editor do Apps Script, abra o arquivo **`Codigo.gs`**
2. Selecione todo o conteúdo (`Ctrl+A`) e apague
3. Cole o conteúdo completo de [Codigo.gs](Codigo.gs)
4. Salve (`Ctrl+S`)

> ⚠️ **As funções `consolidarAbas` e `copiarPRParaMapaPowerBI` foram removidas**
> por estarem abandonadas. Se alguém ainda usar as abas `BI STARTUPS` ou
> `MAPA POWER BI`, avise antes de colar — elas param de ser alimentadas.

---

## Passo 2 — Dialog.html

1. No editor, abra o arquivo **`Dialog.html`**
2. Selecione todo o conteúdo (`Ctrl+A`) e apague
3. Cole o conteúdo completo de [Dialog.html](Dialog.html)
4. Salve (`Ctrl+S`)

> ⚠️ O nome do arquivo precisa continuar sendo **`Dialog`**. Ele é referenciado
> por string no `Codigo.gs` (constante `ARQUIVO_DIALOGO`). Se você renomear o
> arquivo, atualize a constante também.

---

## Passo 3 — Testar sem risco

Faça nesta ordem, do mais seguro para o menos seguro.

### 3.1 A função que só lê

No editor, selecione **`checarAbasComStatus`** no seletor de funções e clique
em **Executar**.

- Vai pedir autorização na primeira vez após a mudança — é normal
- **Esperado:** um alerta dizendo quantas abas têm alterações pendentes
- Confira se a coluna A da aba `CHECAR ABAS` foi preenchida corretamente

Esta é a função mais importante: é ela que decide o que o `main.py` publica.

### 3.2 O diálogo

1. Vá à aba `CHECAR ABAS`
2. Selecione uma célula **da coluna C** que tenha um link
3. Menu **CHECAR LINKS → Editar link selecionado**

**Esperado:** o diálogo abre mostrando o nome da organização e o link atual.
Clique em *Cancelar* para sair sem alterar nada.

Se quiser testar a correção de verdade, use uma linha da aba `TESTE`.

### 3.3 A formatação (altera a planilha)

**`padronizarAbas`** reformata todas as abas de dados. É a que mais mexe na
planilha — rode por último, e de preferência quando ninguém mais estiver
editando.

**Esperado:** cabeçalhos em azul, colunas com largura padronizada, e agora
também as colunas `PAÍS` e `CONTEÚDO BALÃO` formatadas (antes eram ignoradas
por causa de um bug de acentuação).

### 3.4 A checagem de links (demorada)

**`checarLinksErros`** testa cada link, em lotes de 40. Rode várias vezes até
aparecer a mensagem de conclusão. Pode levar minutos.

---

## Se algo der errado

1. Volte à cópia de segurança do Passo 0 e cole de volta
2. Ou use **Implantações → Histórico de versões** no editor

O que **não** é afetado por essa atualização:

- A publicação no site (`main.py` na GitHub Action) roda independente
- Os dados da planilha — nenhuma função nova apaga ou reescreve dados de
  organizações

---

## O que muda no comportamento

| Antes | Depois |
|---|---|
| `checarAbasComStatus` terminava em silêncio | Mostra quantas abas têm pendências e quais não têm coluna STATUS |
| Colunas `PAÍS` e `CONTEÚDO BALÃO` nunca formatadas | Formatadas corretamente |
| "Editar link" não fazia nada nas abas com `ORGANIZAÇÃO` | Funciona em todas as abas |
| Diálogo quebrado para nomes com aspas | Funciona com qualquer nome |
| Erros do diálogo invisíveis | Mensagem explicando o que houve |
| `padronizarAbas` podia estourar o tempo limite | Muito mais rápida (menos chamadas à API) |

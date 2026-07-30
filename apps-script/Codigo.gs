/**
 * Apps Script do PORTAL DA INOVAÇÃO E STARTUPS.
 *
 * Roda dentro da própria planilha (Extensões → Apps Script) e prepara os dados
 * que a automação em Python publica no site.
 *
 * Fluxo:
 *   1. A equipe marca STATUS nas abas (ADICIONAR AO SITE / EDITAR / REMOVER)
 *   2. checarAbasComStatus() lista em "CHECAR ABAS" quais abas têm pendências
 *   3. O main.py lê essa lista e publica as páginas correspondentes
 *
 * ⚠️ Este arquivo NÃO sincroniza automaticamente com a planilha. Ao alterá-lo
 *    aqui, cole o conteúdo no editor do Apps Script (e vice-versa).
 */

// =====================================================================
// Configuração — nomes de abas e colunas
// =====================================================================
// Mantidos em um só lugar. Antes as listas de abas estavam espalhadas por
// várias funções, cada uma com um conteúdo diferente e desatualizada de um
// jeito distinto.

/**
 * Abas de estrutura/apoio e rascunhos: nunca contêm organizações a publicar.
 * Devem espelhar ABAS_IGNORADAS em src/config.py do repositório.
 */
var ABAS_ESTRUTURA = [
  'HOME',
  'CHECAR ABAS',
  'HISTÓRICO',
  'BI STARTUPS',
  'MAPA POWER BI',
  // Rascunhos sem estrutura de aba de dados (sem cabeçalho ou vazias).
  // Listadas aqui para não poluírem o aviso de "sem coluna STATUS".
  'Centros de Pesquisa',
  'deeptechs comparativo'
];

/**
 * Abas de categorias que ainda NÃO têm página criada no site.
 * Ao criar a página no WordPress, remova o nome desta lista e adicione a aba
 * em ABAS_LINKS no src/config.py do repositório.
 */
var ABAS_SEM_PAGINA_NO_SITE = [
  'AGTECHS',
  'BEAUTYTECHS',
  'EVENTECHS',
  'FASHIONTECHS',
  'GAMETECHS',
  'INSURTECHS',
  'PORTAIS DE NOTÍCIAS',
  'SECURITYTECHS',
  'SPORTECHS',
  'TRAVELTECHS'
];

/** Valores de STATUS que indicam que a aba precisa ser republicada. */
var STATUS_PENDENTES = ['EDITAR', 'ADICIONAR AO SITE', 'REMOVER'];

/** Opções do dropdown da coluna STATUS. */
var STATUS_OPCOES = [
  '',                     // em branco por padrão
  'REMOVER',
  'EDITAR',
  'ADICIONAR AO SITE',
  'ADICIONADO AO SITE'
];

/** Variações aceitas para a coluna que identifica a organização. */
var COLUNAS_IDENTIFICADOR = ['NOME', 'ORGANIZACAO', 'NOME OU ORGANIZACAO'];


// =====================================================================
// Utilidades
// =====================================================================

/**
 * Maiúsculo, sem espaços nas pontas e sem acentos.
 * Permite comparar nomes sem depender de como foram digitados:
 * 'País', 'PAIS' e 'PAÍS' viram todos 'PAIS'.
 */
function normalizarTexto(txt) {
  if (txt === null || txt === undefined) return '';
  return String(txt)
    .trim()
    .toUpperCase()
    .normalize('NFD')                  // separa letra e acento
    .replace(/[̀-ͯ]/g, '');  // remove o acento
}

/**
 * Procura uma coluna pelo nome, ignorando acento e maiúsculas.
 * Retorna o índice (base 0) ou -1.
 *
 * Use sempre isto no lugar de `cabecalho.indexOf('PAÍS')`: a busca exata falha
 * quando a planilha tem o nome com acento diferente ou espaço a mais, e a
 * coluna passa a ser ignorada em silêncio.
 */
function acharColuna(cabecalho, nomeProcurado) {
  var alvo = normalizarTexto(nomeProcurado);
  for (var i = 0; i < cabecalho.length; i++) {
    if (normalizarTexto(cabecalho[i]) === alvo) return i;
  }
  return -1;
}

/**
 * Acha a coluna que identifica a organização, aceitando NOME ou ORGANIZAÇÃO.
 * Retorna o índice (base 0) ou -1.
 *
 * Necessário porque as abas não seguem um padrão único: Aceleradoras, Hubs,
 * Parques, Institutos e Inovação nas Universidades usam ORGANIZAÇÃO; as demais
 * usam NOME.
 */
function acharColunaIdentificador(cabecalho) {
  for (var i = 0; i < cabecalho.length; i++) {
    var normalizado = normalizarTexto(cabecalho[i]);
    if (COLUNAS_IDENTIFICADOR.indexOf(normalizado) !== -1) return i;
  }
  return -1;
}

/** True se a aba é de estrutura/apoio e não deve ser tratada como aba de dados. */
function ehAbaDeEstrutura(nomeAba) {
  var normalizado = normalizarTexto(nomeAba);
  for (var i = 0; i < ABAS_ESTRUTURA.length; i++) {
    if (normalizarTexto(ABAS_ESTRUTURA[i]) === normalizado) return true;
  }
  return false;
}

/** True se a aba ainda não tem página no site e portanto não deve ser publicada. */
function ehAbaSemPaginaNoSite(nomeAba) {
  var normalizado = normalizarTexto(nomeAba);
  for (var i = 0; i < ABAS_SEM_PAGINA_NO_SITE.length; i++) {
    if (normalizarTexto(ABAS_SEM_PAGINA_NO_SITE[i]) === normalizado) return true;
  }
  return false;
}


// =====================================================================
// 1. Lista, em "CHECAR ABAS", as abas com alterações pendentes
// =====================================================================
/**
 * Varre as abas de dados e escreve na coluna A de "CHECAR ABAS" o nome das que
 * têm ao menos uma linha com STATUS pendente.
 *
 * É esta lista que o main.py lê para decidir o que publicar — se uma aba não
 * aparecer aqui, ela não é atualizada no site.
 */
function checarAbasComStatus() {
  var planilha = SpreadsheetApp.getActiveSpreadsheet();
  var abaChecagem = planilha.getSheetByName('CHECAR ABAS');

  if (!abaChecagem) {
    SpreadsheetApp.getUi().alert('A aba "CHECAR ABAS" não foi encontrada.');
    return;
  }

  var abasComStatus = [];
  var abasSemColunaStatus = [];

  planilha.getSheets().forEach(function (aba) {
    var nomeAba = aba.getName();

    if (ehAbaDeEstrutura(nomeAba) || ehAbaSemPaginaNoSite(nomeAba)) return;

    var dados = aba.getDataRange().getValues();
    if (dados.length < 2) return;  // só cabeçalho, ou vazia

    // Busca tolerante: antes usava indexOf('STATUS') exato, então um espaço a
    // mais no cabeçalho fazia a aba ser pulada sem aviso — e ela deixava de
    // ser publicada sem ninguém perceber.
    var indiceStatus = acharColuna(dados[0], 'STATUS');
    if (indiceStatus === -1) {
      abasSemColunaStatus.push(nomeAba);
      return;
    }

    for (var i = 1; i < dados.length; i++) {
      var valorStatus = normalizarTexto(dados[i][indiceStatus]);
      if (STATUS_PENDENTES.indexOf(valorStatus) !== -1) {
        abasComStatus.push(nomeAba);
        return;  // basta uma linha pendente para a aba entrar na lista
      }
    }
  });

  abaChecagem.getRange('A2:A').clearContent();

  if (abasComStatus.length > 0) {
    abaChecagem
      .getRange(2, 1, abasComStatus.length, 1)
      .setValues(abasComStatus.map(function (nome) { return [nome]; }));
  }

  // Relatório visível: antes a função terminava calada, e não havia como saber
  // se "nenhuma aba listada" significava nada pendente ou algo quebrado.
  var mensagem = abasComStatus.length > 0
    ? '✅ ' + abasComStatus.length + ' aba(s) com alterações pendentes.'
    : 'Nenhuma aba com alterações pendentes.';

  if (abasSemColunaStatus.length > 0) {
    mensagem += '\n\n⚠️ Sem coluna STATUS (ignoradas): '
              + abasSemColunaStatus.join(', ');
  }

  SpreadsheetApp.getUi().alert(mensagem);
}


// =====================================================================
// 2. Padroniza formatação e dropdown de STATUS
// =====================================================================
/**
 * Aplica formatação uniforme às abas de dados e coloca o dropdown de STATUS
 * nas linhas ainda em branco.
 */
function padronizarAbas() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();

  var statusValidation = SpreadsheetApp.newDataValidation()
    .requireValueInList(STATUS_OPCOES, true)
    .setAllowInvalid(false)
    .build();

  // Largura e alinhamento por coluna. Os nomes são comparados sem acento,
  // então 'PAIS' encontra a coluna real 'PAÍS'.
  //
  // CORRIGIDO: esta função definia internamente um normalizarTexto() que NÃO
  // removia acentos, e essa versão local tinha precedência sobre a global.
  // Resultado: 'PAIS' e 'CONTEUDO BALAO' nunca casavam com as colunas reais
  // 'PAÍS' e 'CONTEÚDO BALÃO', que ficavam sem formatação alguma.
  var formatos = [
    { nome: 'NOME',           alinhamento: 'left',   largura: 300 },
    { nome: 'ORGANIZAÇÃO',    alinhamento: 'left',   largura: 300 },
    { nome: 'LINK',           alinhamento: null,     largura: 150, cor: 'blue' },
    { nome: 'UF',             alinhamento: 'center', largura: 60 },
    { nome: 'CATEGORIA',      alinhamento: 'left',   largura: 150 },
    { nome: 'CIDADE',         alinhamento: 'center', largura: 120 },
    { nome: 'PAÍS',           alinhamento: 'center', largura: 60 },
    { nome: 'CONTEÚDO BALÃO', alinhamento: 'left',   largura: 400 },
    { nome: 'STATUS',         alinhamento: 'center', largura: 200 }
  ];

  ss.getSheets().forEach(function (sheet) {
    var nomeAba = sheet.getName();

    // CORRIGIDO: a checagem antiga era "CHECHAR ABAS" (com CH a mais), então a
    // aba de controle nunca era pulada e era formatada como aba de dados.
    if (ehAbaDeEstrutura(nomeAba)) return;

    var lastRow = sheet.getLastRow();
    var lastCol = sheet.getLastColumn();
    if (lastRow < 1 || lastCol < 1) return;

    // --- Cabeçalho ---
    sheet.getRange(1, 1, 1, lastCol)
      .setFontWeight('bold')
      .setFontSize(11)
      .setFontFamily('Calibri')
      .setBackground('#cfe2f3')
      .setBorder(false, false, false, false, false, false)
      .setHorizontalAlignment('center');

    if (lastRow < 2) return;  // sem linhas de dados

    // --- Corpo ---
    sheet.getRange(2, 1, lastRow - 1, lastCol)
      .setFontSize(11)
      .setFontFamily('Calibri')
      .setBackground(null)
      .setFontWeight('normal')
      .setFontColor('black')
      .setBorder(false, false, false, false, false, false);

    var cabecalho = sheet.getRange(1, 1, 1, lastCol).getValues()[0];

    // --- Formatação por coluna ---
    formatos.forEach(function (formato) {
      var idx = acharColuna(cabecalho, formato.nome);
      if (idx === -1) return;

      var range = sheet.getRange(2, idx + 1, lastRow - 1, 1);
      if (formato.alinhamento) range.setHorizontalAlignment(formato.alinhamento);
      if (formato.cor) range.setFontColor(formato.cor);
      if (formato.largura) sheet.setColumnWidth(idx + 1, formato.largura);
    });

    // --- Dropdown de STATUS nas linhas sem organização preenchida ---
    var idxNome = acharColunaIdentificador(cabecalho);
    var idxStatus = acharColuna(cabecalho, 'STATUS');
    if (idxNome === -1 || idxStatus === -1) return;

    var nomeVals = sheet.getRange(2, idxNome + 1, lastRow - 1, 1).getValues();

    // Escrita apenas nas células que precisam mudar (linhas sem organização
    // preenchida). Uma escrita em bloco na coluna inteira seria mais rápida,
    // mas reescreveria também as linhas já preenchidas — risco desnecessário
    // em dados de produção.
    for (var i = 0; i < nomeVals.length; i++) {
      if (String(nomeVals[i][0]).trim() === '') {
        var celulaStatus = sheet.getRange(2 + i, idxStatus + 1);
        celulaStatus.setDataValidation(statusValidation);
        celulaStatus.setValue('');
      }
    }
  });

  SpreadsheetApp.getActive().toast('✅ Formatação padronizada.');
}


// =====================================================================
// 3. Checagem de links quebrados (processa em lotes)
// =====================================================================
/**
 * Testa os links das abas de dados e registra os quebrados em "CHECAR ABAS"
 * (colunas C, D e E: link, organização, aba de origem).
 *
 * O Apps Script tem tempo limite de execução, então a varredura é feita em
 * lotes: cada chamada processa LOTE_TAMANHO links e guarda a posição. Rode
 * repetidamente até aparecer a mensagem de conclusão.
 */
function checarLinksErros() {
  var LOTE_TAMANHO = 40;
  var PAUSA_MS = 500;

  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var abaDestino = ss.getSheetByName('CHECAR ABAS');
  if (!abaDestino) {
    SpreadsheetApp.getUi().alert('A aba "CHECAR ABAS" não foi encontrada.');
    return;
  }

  var props = PropertiesService.getScriptProperties();

  var todosLinks = [];
  try {
    todosLinks = JSON.parse(props.getProperty('todosLinks') || '[]');
  } catch (e) {
    todosLinks = [];
  }

  var ultimaPos = parseInt(props.getProperty('ultimaPos') || '0', 10);

  // --- Primeira execução do ciclo: coleta os links ---
  if (todosLinks.length === 0) {
    ss.getSheets().forEach(function (sheet) {
      var nomeAba = sheet.getName();
      if (ehAbaDeEstrutura(nomeAba)) return;

      var valores = sheet.getDataRange().getValues();
      if (valores.length < 2) return;

      var headers = valores.shift();
      var idxLink = acharColuna(headers, 'LINK');
      if (idxLink === -1) return;

      // Antes eram quatro indexOf() encadeados tentando adivinhar a grafia
      // ('NOME', 'ORGANIZAÇÃO', 'ORGANIZACAO', 'Organização'). A busca
      // normalizada cobre todas as variações de uma vez.
      var idxNome = acharColunaIdentificador(headers);

      valores.forEach(function (linha) {
        var link = linha[idxLink];
        if (typeof link === 'string' && link.match(/^https?:\/\//i)) {
          todosLinks.push({
            url: link,
            nome: (idxNome !== -1) ? linha[idxNome] : '',
            aba: nomeAba
          });
        }
      });
    });

    if (todosLinks.length === 0) {
      SpreadsheetApp.getUi().alert('Nenhum link encontrado para checar.');
      return;
    }

    // Limpa o resultado da checagem anterior.
    // Mantido o intervalo original C:F — a checagem grava em C, D e E, mas a
    // coluna F pode ter conteúdo de versões anteriores. Não reduzir o alcance
    // sem antes conferir o que existe em F na planilha.
    var ultimaLinha = abaDestino.getLastRow();
    if (ultimaLinha > 1) {
      abaDestino.getRange('C2:F' + ultimaLinha).clearContent();
    }
    ultimaPos = 0;
  }

  // --- Processa o lote atual ---
  var erros = [];
  var fim = Math.min(ultimaPos + LOTE_TAMANHO, todosLinks.length);

  for (var i = ultimaPos; i < fim; i++) {
    var item = todosLinks[i];
    var status = 'OK';

    try {
      var resposta = UrlFetchApp.fetch(item.url, {
        muteHttpExceptions: true,
        followRedirects: true,
        validateHttpsCertificates: false
      });
      var codigo = resposta.getResponseCode();
      // 403 e 500 são tolerados: muitos sites bloqueiam requisições
      // automatizadas mas funcionam normalmente no navegador.
      if (codigo !== 200 && codigo !== 403 && codigo !== 500) {
        status = 'Erro ' + codigo;
      }
    } catch (e) {
      status = 'Falhou';
    }

    if (status !== 'OK') {
      erros.push([item.url, item.nome, item.aba]);
    }

    if ((i - ultimaPos + 1) % 10 === 0) Utilities.sleep(PAUSA_MS);
  }

  if (erros.length > 0) {
    abaDestino
      .getRange(abaDestino.getLastRow() + 1, 3, erros.length, 3)
      .setValues(erros);
  }

  // --- Salva a posição ou encerra o ciclo ---
  if (fim >= todosLinks.length) {
    props.deleteProperty('todosLinks');
    props.deleteProperty('ultimaPos');
    SpreadsheetApp.getActive().toast(
      '✅ Checagem finalizada: ' + todosLinks.length + ' links verificados.'
    );
    return;
  }

  try {
    props.setProperty('todosLinks', JSON.stringify(todosLinks));
    props.setProperty('ultimaPos', String(fim));
    SpreadsheetApp.getActive().toast(
      '🔎 ' + fim + '/' + todosLinks.length + ' — rode de novo para continuar.'
    );
  } catch (err) {
    // O limite por propriedade é de 9 KB; com muitos links o JSON estoura.
    // Antes o erro era silencioso e a checagem recomeçava do zero a cada
    // execução, sem nunca terminar.
    props.deleteProperty('todosLinks');
    props.deleteProperty('ultimaPos');
    SpreadsheetApp.getUi().alert(
      'Não foi possível salvar o progresso: são links demais para a memória '
      + 'do Apps Script.\n\nA checagem foi interrompida. Reduza LOTE_TAMANHO '
      + 'ou rode a checagem por partes.'
    );
  }
}


// =====================================================================
// 4. Menu e edição de link individual
// =====================================================================

function onOpen() {
  SpreadsheetApp.getUi()
    .createMenu('CHECAR LINKS')
    .addItem('Editar link selecionado', 'abrirDialog')
    .addToUi();
}


/**
 * Abre o diálogo de ação para o link selecionado na aba "CHECAR ABAS".
 * Espera que a célula ativa esteja na coluna C (LINK).
 */
function abrirDialog() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var aba = ss.getActiveSheet();
  var range = aba.getActiveRange();

  if (aba.getName() !== 'CHECAR ABAS' || range.getColumn() !== 3) {
    SpreadsheetApp.getUi().alert(
      'Selecione uma célula da coluna LINK (C) na aba CHECAR ABAS.'
    );
    return;
  }

  var linha = range.getRow();
  if (linha < 2) return;

  var linkAtual = range.getValue();
  if (!linkAtual) {
    SpreadsheetApp.getUi().alert('A célula selecionada está vazia.');
    return;
  }

  var template = HtmlService.createTemplateFromFile('Dialog');
  template.linha = linha;
  template.linkAtual = linkAtual;
  template.nomeOrg = aba.getRange(linha, 4).getValue();
  template.nomeAbaOrigem = aba.getRange(linha, 5).getValue();

  SpreadsheetApp.getUi().showModalDialog(
    template.evaluate().setWidth(400).setHeight(200),
    'Ação para Link'
  );
}


/**
 * Aplica na aba de origem a ação escolhida no diálogo e remove a linha
 * correspondente de "CHECAR ABAS".
 *
 * Chamada pelo Dialog.html via google.script.run.
 */
function processarAcao(linha, linkAtual, nomeOrg, nomeAbaOrigem, acao, novoLink) {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var abaChecar = ss.getSheetByName('CHECAR ABAS');
  var abaOrigem = ss.getSheetByName(nomeAbaOrigem);

  if (!abaOrigem) {
    throw new Error('Aba de origem "' + nomeAbaOrigem + '" não encontrada.');
  }

  var headers = abaOrigem.getRange(1, 1, 1, abaOrigem.getLastColumn()).getValues()[0];

  // CORRIGIDO: antes usava headers.indexOf('NOME') exato. Nas abas que usam
  // ORGANIZAÇÃO (Aceleradoras, Hubs, Parques, Institutos, Inovação nas
  // Universidades) a função saía sem fazer nada, sem avisar o usuário.
  var idxNome = acharColunaIdentificador(headers);
  var idxLink = acharColuna(headers, 'LINK');
  var idxStatus = acharColuna(headers, 'STATUS');

  if (idxNome === -1 || idxLink === -1 || idxStatus === -1) {
    throw new Error(
      'A aba "' + nomeAbaOrigem + '" não tem as colunas necessárias '
      + '(organização, LINK e STATUS).'
    );
  }

  var ultimaLinha = abaOrigem.getLastRow();
  if (ultimaLinha < 2) {
    throw new Error('A aba "' + nomeAbaOrigem + '" não tem dados.');
  }

  // CORRIGIDO: a leitura anterior era getRange(2, idxNome, n, 2), que presumia
  // LINK imediatamente após NOME. Quando não era o caso, comparava a coluna
  // errada. Agora nome e link são lidos por índice próprio.
  var nomes = abaOrigem.getRange(2, idxNome + 1, ultimaLinha - 1, 1).getValues();
  var links = abaOrigem.getRange(2, idxLink + 1, ultimaLinha - 1, 1).getValues();

  // Casa por nome E link. Só pelo nome, organizações homônimas faziam a edição
  // cair na linha errada.
  var linhaOrigem = null;
  for (var i = 0; i < nomes.length; i++) {
    if (String(nomes[i][0]).trim() === String(nomeOrg).trim() &&
        String(links[i][0]).trim() === String(linkAtual).trim()) {
      linhaOrigem = i + 2;
      break;
    }
  }

  // Sem o link correspondente, aceita só o nome — o link pode ter sido
  // alterado na planilha depois que a checagem rodou.
  if (linhaOrigem === null) {
    for (var j = 0; j < nomes.length; j++) {
      if (String(nomes[j][0]).trim() === String(nomeOrg).trim()) {
        linhaOrigem = j + 2;
        break;
      }
    }
  }

  if (linhaOrigem === null) {
    throw new Error(
      'Organização "' + nomeOrg + '" não encontrada na aba "' + nomeAbaOrigem + '".'
    );
  }

  if (acao === 'alterar') {
    if (!novoLink) throw new Error('Nenhum link novo informado.');
    abaOrigem.getRange(linhaOrigem, idxLink + 1).setValue(novoLink);
    abaOrigem.getRange(linhaOrigem, idxStatus + 1).setValue('EDITAR');
  } else if (acao === 'remover') {
    abaOrigem.getRange(linhaOrigem, idxStatus + 1).setValue('REMOVER');
  } else {
    throw new Error('Ação desconhecida: ' + acao);
  }

  abaChecar.deleteRow(linha);
}

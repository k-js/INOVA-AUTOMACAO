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
// Todas as listas de abas ficam aqui, e não espalhadas pelas funções, para
// que não divirjam entre si.

/**
 * Abas de estrutura/apoio e rascunhos: nunca contêm organizações a publicar.
 * Devem espelhar ABAS_IGNORADAS em src/config.py do repositório.
 *
 * @type {!Array<string>}
 * @const
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
 *
 * @type {!Array<string>}
 * @const
 */
var ABAS_SEM_PAGINA_NO_SITE = [
  'AGTECHS',              ///REMOVER LINHA QUANDO CRIAR ABA NO SITE
  'BEAUTYTECHS',          ///REMOVER LINHA QUANDO CRIAR ABA NO SITE
  'EVENTECHS',            ///REMOVER LINHA QUANDO CRIAR ABA NO SITE
  'PORTAIS DE NOTÍCIAS',  ///REMOVER LINHA QUANDO CRIAR ABA NO SITE
  'SECURITYTECHS',        ///REMOVER LINHA QUANDO CRIAR ABA NO SITE
  'SPORTECHS'             ///REMOVER LINHA QUANDO CRIAR ABA NO SITE
  // FASHIONTECHS, GAMETECHS, INSURTECHS e TRAVELTECHS saíram desta lista:
  // passam a ser varridas por checarAbasComStatus e aparecem em "CHECAR ABAS"
  // quando tiverem STATUS pendente.
  //
  // ⚠️ As páginas dessas 4 ainda NÃO existem no site (verificado na API do
  // WordPress). Enquanto não forem criadas, a publicação vai reportar
  // "Link não mapeado" para elas. Ao criar cada página, adicione a URL em
  // ABAS_LINKS no src/config.py e tire o nome de ABAS_IGNORADAS.
];

/**
 * Valores de STATUS que indicam que a aba precisa ser republicada.
 *
 * @type {!Array<string>}
 * @const
 */
var STATUS_PENDENTES = ['EDITAR', 'ADICIONAR AO SITE', 'REMOVER'];

/**
 * Lista de opções do dropdown de STATUS (primeiro item é string vazia).
 *
 * @type {!Array<string>}
 * @const
 */
var STATUS_OPCOES = [
  '',                     // deixa o seletor aparecer em branco inicialmente
  'REMOVER',
  'EDITAR',
  'ADICIONAR AO SITE',
  'ADICIONADO AO SITE'
];

/**
 * Variações aceitas para a coluna que identifica a organização.
 *
 * @type {!Array<string>}
 * @const
 */
var COLUNAS_IDENTIFICADOR = ['NOME', 'ORGANIZACAO', 'NOME OU ORGANIZACAO'];

/**
 * ID da planilha, usado quando o script roda por acionador de tempo.
 *
 * SpreadsheetApp.getActiveSpreadsheet() retorna null nesse contexto: não há
 * planilha "ativa" fora de uma sessão de usuário. As funções agendadas
 * falhavam em 0 segundos por causa disso.
 *
 * Está no arquivo por ser o mesmo ID que já aparece na URL da planilha — não
 * é segredo. Quem tem acesso ao script já tem acesso à planilha.
 *
 * Para descobrir: na URL da planilha, é o trecho entre /d/ e /edit
 *   docs.google.com/spreadsheets/d/<ID_AQUI>/edit
 *
 * @type {string}
 * @const
 */
var ID_PLANILHA = '';  // ← preencher com o ID da planilha

/**
 * Nome do arquivo HTML do diálogo, sem a extensão.
 *
 * ⚠️ Esta é uma referência POR STRING a outro arquivo do projeto Apps Script.
 * O editor não a verifica: se o arquivo Dialog.html for renomeado, nada acusa
 * o problema até alguém clicar no menu e a chamada falhar em execução.
 *
 * A API do HtmlService só aceita o nome como texto, então a referência por
 * string é inevitável — mas fica centralizada aqui, e verificarArquivoDialog()
 * transforma a falha em uma mensagem que diz o que fazer.
 *
 * Ao renomear o arquivo no editor do Apps Script, atualize este valor.
 *
 * @type {string}
 * @const
 */
var ARQUIVO_DIALOGO = 'Dialog';


// =====================================================================
// Utilidades
// =====================================================================
//
// Nota sobre desempenho neste arquivo:
//
// O custo dominante NÃO é o processamento em JavaScript, e sim cada chamada à
// API do Sheets (getRange, setValue, getValues...). Uma chamada dessas custa
// dezenas de milissegundos — ordens de grandeza mais que uma iteração de laço.
// Com o limite de 6 minutos de execução do Apps Script, o que importa é
// reduzir o NÚMERO DE CHAMADAS À API, não a complexidade dos laços.
//
// Por isso as otimizações aqui seguem duas linhas:
//   1. Evitar recomputar o que não muda (memoização e pré-normalização)
//   2. Agrupar escritas em uma única chamada quando elas atingem as mesmas
//      células que seriam escritas individualmente

/**
 * Cache de normalizações já calculadas.
 *
 * normalizarTexto() é chamada milhares de vezes por execução, quase sempre
 * sobre os mesmos valores (nomes de aba, cabeçalhos, valores de STATUS que se
 * repetem em todas as linhas). Como normalize('NFD') + regex aloca strings
 * novas a cada chamada, memorizar o resultado troca esse custo por uma
 * consulta O(1).
 *
 * Um Map é usado no lugar de objeto literal para evitar colisão com nomes
 * herdados de Object.prototype (ex.: uma aba chamada 'constructor').
 *
 * @type {!Map<string, string>}
 * @private
 */
var _cacheNormalizacao = new Map();

/**
 * Maiúsculo, sem espaços nas pontas e sem acentos.
 *
 * Permite comparar nomes sem depender de como foram digitados:
 * 'País', 'PAIS' e 'PAÍS' viram todos 'PAIS'.
 *
 * Custo: O(t) na primeira vez para um texto de tamanho t; O(1) nas seguintes.
 *
 * @param {*} txt Texto a normalizar. Valores não-string são convertidos;
 *     null e undefined viram string vazia.
 * @return {string} Texto em maiúsculas, sem acentos e sem espaços nas pontas.
 */
function normalizarTexto(txt) {
  if (txt === null || txt === undefined) return '';

  var chave = String(txt);
  var emCache = _cacheNormalizacao.get(chave);
  if (emCache !== undefined) return emCache;

  var resultado = chave
    .trim()
    .toUpperCase()
    .normalize('NFD')                  // separa acentos
    .replace(/[̀-ͯ]/g, '');  // remove acentos

  _cacheNormalizacao.set(chave, resultado);
  return resultado;
}

/**
 * Constrói um índice nome-normalizado -> posição a partir de um cabeçalho.
 *
 * Vale a pena quando várias colunas são procuradas no mesmo cabeçalho: em vez
 * de uma varredura por busca (O(C) cada), faz uma única passada O(C) e depois
 * responde em O(1). É o caso de padronizarAbas, que procura 9 colunas por aba.
 *
 * Retorna um Map, cujas chaves não colidem com Object.prototype.
 *
 * @param {!Array<*>} cabecalho Primeira linha da aba, como vem de getValues().
 * @return {!Map<string, number>} Nome normalizado -> índice base 0. Em caso de
 *     nomes repetidos, a primeira ocorrência vence (como indexOf()).
 */
function indexarCabecalho(cabecalho) {
  var indice = new Map();
  for (var i = 0; i < cabecalho.length; i++) {
    var chave = normalizarTexto(cabecalho[i]);
    // Primeira ocorrência vence, para espelhar o comportamento de indexOf()
    // quando o cabeçalho tem nomes repetidos.
    if (!indice.has(chave)) indice.set(chave, i);
  }
  return indice;
}

/**
 * Procura uma coluna pelo nome, ignorando acento e maiúsculas.
 * Retorna o índice (base 0) ou -1.
 *
 * Use sempre isto no lugar de `cabecalho.indexOf('PAÍS')`: a busca exata falha
 * quando a planilha tem o nome com acento diferente ou espaço a mais, e a
 * coluna passa a ser ignorada em silêncio.
 *
 * Aceita tanto o array de cabeçalho quanto um índice pronto de
 * indexarCabecalho(). Passe o índice quando for procurar várias colunas no
 * mesmo cabeçalho.
 *
 * @param {!Array<*>|!Map<string, number>} cabecalhoOuIndice Cabeçalho cru ou
 *     índice construído por indexarCabecalho().
 * @param {string} nomeProcurado Nome da coluna, com ou sem acento.
 * @return {number} Índice base 0 da coluna, ou -1 se não existir.
 */
function acharColuna(cabecalhoOuIndice, nomeProcurado) {
  var alvo = normalizarTexto(nomeProcurado);

  if (cabecalhoOuIndice instanceof Map) {
    var achado = cabecalhoOuIndice.get(alvo);
    return (achado === undefined) ? -1 : achado;
  }

  for (var i = 0; i < cabecalhoOuIndice.length; i++) {
    if (normalizarTexto(cabecalhoOuIndice[i]) === alvo) return i;
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
 *
 * A busca varre o cabeçalho na ordem das colunas (e não na ordem das variações
 * aceitas) para que, numa aba com NOME e ORGANIZAÇÃO, vença a que aparece
 * primeiro — o mesmo critério do restante do código.
 *
 * @param {!Array<*>|!Map<string, number>} cabecalhoOuIndice Cabeçalho cru ou
 *     índice construído por indexarCabecalho().
 * @return {number} Índice base 0 da coluna identificadora, ou -1.
 */
function acharColunaIdentificador(cabecalhoOuIndice) {
  if (cabecalhoOuIndice instanceof Map) {
    var melhor = -1;
    _IDENTIFICADORES.forEach(function (variacao) {
      var idx = cabecalhoOuIndice.get(variacao);
      if (idx !== undefined && (melhor === -1 || idx < melhor)) melhor = idx;
    });
    return melhor;
  }

  for (var i = 0; i < cabecalhoOuIndice.length; i++) {
    if (_IDENTIFICADORES.has(normalizarTexto(cabecalhoOuIndice[i]))) return i;
  }
  return -1;
}

// -------------------------------------------------------------------
// Conjuntos pré-normalizados
// -------------------------------------------------------------------
// As listas de configuração são fixas, então são normalizadas uma única vez na
// carga do script, e não a cada consulta — com 51 abas na planilha, isso
// pouparia ~870 normalizações repetidas por execução.
//
// Set em vez de Array: `has()` é O(1), contra O(k) do indexOf().

/** @type {Set<string>} */
var _ABAS_ESTRUTURA_NORM = new Set(ABAS_ESTRUTURA.map(normalizarTexto));

/** @type {Set<string>} */
var _ABAS_SEM_PAGINA_NORM = new Set(ABAS_SEM_PAGINA_NO_SITE.map(normalizarTexto));

/** @type {Set<string>} */
var _STATUS_PENDENTES_NORM = new Set(STATUS_PENDENTES.map(normalizarTexto));

/** @type {Set<string>} */
var _IDENTIFICADORES = new Set(COLUNAS_IDENTIFICADOR.map(normalizarTexto));

/**
 * True se a aba é de estrutura/apoio e não deve ser tratada como aba de dados.
 *
 * @param {string} nomeAba Nome da aba, como aparece na planilha.
 * @return {boolean}
 */
function ehAbaDeEstrutura(nomeAba) {
  return _ABAS_ESTRUTURA_NORM.has(normalizarTexto(nomeAba));
}

/**
 * True se a aba ainda não tem página no site e portanto não deve ser publicada.
 *
 * @param {string} nomeAba Nome da aba, como aparece na planilha.
 * @return {boolean}
 */
function ehAbaSemPaginaNoSite(nomeAba) {
  return _ABAS_SEM_PAGINA_NORM.has(normalizarTexto(nomeAba));
}

/**
 * True se o valor de STATUS indica que a aba precisa ser republicada.
 *
 * @param {*} valor Conteúdo da célula de STATUS.
 * @return {boolean}
 */
function ehStatusPendente(valor) {
  return _STATUS_PENDENTES_NORM.has(normalizarTexto(valor));
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
 *
 * Rodar pelo editor do Apps Script (Executar → checarAbasComStatus).
 *
 * @return {void}
 */
function checarAbasComStatus() {
  var planilha = obterPlanilha();
  var abaChecagem = planilha.getSheetByName('CHECAR ABAS');

  if (!abaChecagem) {
    relatar('A aba "CHECAR ABAS" não foi encontrada.');
    return;
  }

  var abasComStatus = [];
  var abasSemColunaStatus = [];

  planilha.getSheets().forEach(function (aba) {
    var nomeAba = aba.getName();

    if (ehAbaDeEstrutura(nomeAba) || ehAbaSemPaginaNoSite(nomeAba)) return;

    var ultimaLinha = aba.getLastRow();
    var ultimaColuna = aba.getLastColumn();
    if (ultimaLinha < 2 || ultimaColuna < 1) return;  // só cabeçalho, ou vazia

    // Só o cabeçalho: uma linha, em vez da aba inteira.
    var cabecalho = aba.getRange(1, 1, 1, ultimaColuna).getValues()[0];

    // Busca tolerante a acento e espaço: com indexOf() exato, um espaço a mais
    // no cabeçalho faria a aba ser pulada sem aviso, e ela deixaria de ser
    // publicada sem ninguém perceber.
    var indiceStatus = acharColuna(cabecalho, 'STATUS');
    if (indiceStatus === -1) {
      abasSemColunaStatus.push(nomeAba);
      return;
    }

    // Apenas a coluna STATUS. getDataRange() traria todas as colunas de todas
    // as linhas — dezenas de milhares de células somando as 38 abas — quando
    // basta uma coluna para decidir se a aba tem pendência.
    var status = aba.getRange(2, indiceStatus + 1, ultimaLinha - 1, 1).getValues();

    // Busca em Set (O(1)) no lugar de indexOf em Array (O(k)), e a saída
    // antecipada evita varrer o resto da aba assim que a primeira pendência
    // aparece: no melhor caso, 1 linha em vez de todas.
    for (var i = 0; i < status.length; i++) {
      if (ehStatusPendente(status[i][0])) {
        abasComStatus.push(nomeAba);
        return;  // basta uma linha pendente para a aba entrar na lista
      }
    }
  });

  // Limpa e escreve os nomes na aba "CHECAR ABAS"
  abaChecagem.getRange('A2:A').clearContent();

  if (abasComStatus.length > 0) {
    abaChecagem
      .getRange(2, 1, abasComStatus.length, 1)
      .setValues(abasComStatus.map(function (nome) { return [nome]; }));
  }

  // Relatório visível ao final: sem ele, "nenhuma aba listada" seria
  // ambíguo entre nada pendente e algo quebrado.
  var mensagem = abasComStatus.length > 0
    ? '✅ ' + abasComStatus.length + ' aba(s) com alterações pendentes.'
    : 'Nenhuma aba com alterações pendentes.';

  if (abasSemColunaStatus.length > 0) {
    mensagem += '\n\n⚠️ Sem coluna STATUS (ignoradas): '
              + abasSemColunaStatus.join(', ');
  }

  relatar(mensagem);
}


/**
 * Devolve a planilha, funcionando nos dois contextos de execução.
 *
 * getActiveSpreadsheet() só funciona quando há sessão de usuário: pelo editor,
 * pelo menu ou por acionador simples. Em acionador POR TEMPO ele retorna null,
 * e a função morre na linha seguinte — em 0 segundos, sem mensagem útil.
 *
 * Por isso, quando não há planilha ativa, abre pelo ID.
 *
 * @return {!Spreadsheet}
 * @throws {Error} Se não houver planilha ativa nem ID_PLANILHA preenchido.
 */
function obterPlanilha() {
  var planilha = SpreadsheetApp.getActiveSpreadsheet();
  if (planilha) return planilha;

  if (!ID_PLANILHA) {
    throw new Error(
      'Sem planilha ativa (execução por acionador de tempo) e ID_PLANILHA está '
      + 'vazio. Preencha a constante ID_PLANILHA no início do Codigo.gs com o '
      + 'ID que aparece na URL da planilha, entre /d/ e /edit.'
    );
  }

  return SpreadsheetApp.openById(ID_PLANILHA);
}

/**
 * Mostra uma mensagem ao usuário, funcionando nos dois contextos de execução.
 *
 * getUi() só existe quando o script é acionado a partir da planilha (menu,
 * botão, gatilho de UI). Rodando pelo editor do Apps Script não há interface
 * associada, e a chamada falha. O log cobre esse caso: aparece no Registro de
 * execução.
 *
 * @param {string} mensagem
 * @return {void}
 */
function relatar(mensagem) {
  console.log(mensagem);

  try {
    SpreadsheetApp.getUi().alert(mensagem);
  } catch (e) {
    // Sem interface disponível (execução pelo editor): o console.log acima já
    // registrou a mensagem.
  }
}


// =====================================================================
// 2. Padroniza formatação e dropdown de STATUS
// =====================================================================
/**
 * Aplica formatação uniforme às abas de dados e coloca o dropdown de STATUS
 * nas linhas ainda em branco.
 *
 * Rodar pelo editor do Apps Script (Executar → padronizarAbas).
 *
 * @return {void}
 */
function padronizarAbas() {
  var ss = obterPlanilha();

  // Construir objeto de validação uma vez
  var statusValidation = SpreadsheetApp.newDataValidation()
    .requireValueInList(STATUS_OPCOES, true)   // true => mostrar dropdown
    .setAllowInvalid(false)                    // não permitir valores fora da lista
    .build();

  // Largura e alinhamento por coluna. Os nomes são comparados sem acento nem
  // diferença de caixa, então 'PAIS' encontra a coluna real 'PAÍS' e
  // 'CONTEUDO BALAO' encontra 'CONTEÚDO BALÃO'.
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

    // Ignorar abas específicas
    if (ehAbaDeEstrutura(nomeAba)) return;

    var lastRow = sheet.getLastRow();
    var lastCol = sheet.getLastColumn();
    if (lastRow < 1 || lastCol < 1) return;

    // --- Cabeçalho (primeira linha) ---
    sheet.getRange(1, 1, 1, lastCol)
      .setFontWeight('bold')
      .setFontSize(11)
      .setFontFamily('Calibri')
      .setBackground('#cfe2f3')
      .setBorder(false, false, false, false, false, false)
      .setHorizontalAlignment('center');

    if (lastRow < 2) return;  // sem linhas de dados

    // --- Restante da planilha ---
    sheet.getRange(2, 1, lastRow - 1, lastCol)
      .setFontSize(11)
      .setFontFamily('Calibri')
      .setBackground(null)
      .setFontWeight('normal')
      .setFontColor('black')
      .setBorder(false, false, false, false, false, false);

    // Normalizar cabeçalhos
    var cabecalho = sheet.getRange(1, 1, 1, lastCol).getValues()[0];

    // Um índice construído em uma passada O(C) responde as 9 buscas seguintes
    // em O(1) cada, no lugar de 9 varreduras completas do cabeçalho.
    var indiceCabecalho = indexarCabecalho(cabecalho);

    // --- Aplicar formatação por coluna ---
    // (era a "função auxiliar para procurar e aplicar formatação"; agora a
    // busca sai do índice pré-construído em vez de varrer o cabeçalho)
    formatos.forEach(function (formato) {
      var idx = acharColuna(indiceCabecalho, formato.nome);
      if (idx === -1) return;

      var range = sheet.getRange(2, idx + 1, lastRow - 1, 1);
      if (formato.alinhamento) range.setHorizontalAlignment(formato.alinhamento);
      if (formato.cor) range.setFontColor(formato.cor);
      if (formato.largura) sheet.setColumnWidth(idx + 1, formato.largura);
    });

    // --- Dropdown de STATUS nas linhas sem organização preenchida ---
    var idxNome = acharColunaIdentificador(indiceCabecalho);
    var idxStatus = acharColuna(indiceCabecalho, 'STATUS');
    // Só executa se achar o STATUS, o Identificador (Nome/Org) e se houver
    // linhas com dados
    if (idxNome === -1 || idxStatus === -1) return;

    var nomeVals = sheet.getRange(2, idxNome + 1, lastRow - 1, 1).getValues();

    // A coluna STATUS inteira é lida, alterada em memória e gravada de volta
    // em uma única chamada. As linhas com organização preenchida mantêm o
    // valor e a validação que já tinham — só as vazias mudam.
    //
    // setDataValidation (singular) só existe em Range, não em RangeList: por
    // isso o trabalho é feito sobre a matriz da coluna, e não célula a célula.
    // Numa aba com 600 linhas, isso troca 1.200 chamadas à API por 2.
    var colunaStatus = sheet.getRange(2, idxStatus + 1, lastRow - 1, 1);
    var statusVals = colunaStatus.getValues();
    var validacoes = colunaStatus.getDataValidations();
    var alterou = false;

    for (var i = 0; i < nomeVals.length; i++) {
      if (String(nomeVals[i][0]).trim() === '') {
        validacoes[i][0] = statusValidation;
        statusVals[i][0] = '';
        alterou = true;
      }
    }

    if (!alterou) return;

    colunaStatus.setDataValidations(validacoes);
    colunaStatus.setValues(statusVals);
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
 *
 * Rodar pelo editor do Apps Script (Executar → checarLinksErros).
 *
 * @return {void}
 */
function checarLinksErros() {
  var LOTE_TAMANHO = 40;
  var PAUSA_MS = 500;

  var ss = obterPlanilha();
  var abaDestino = ss.getSheetByName('CHECAR ABAS');
  if (!abaDestino) {
    relatar('A aba "CHECAR ABAS" não foi encontrada.');
    return;
  }

  var props = PropertiesService.getScriptProperties();

  // Carrega a lista da memória do Apps Script
  var todosLinks = [];
  try {
    todosLinks = JSON.parse(props.getProperty('todosLinks') || '[]');
  } catch (e) {
    todosLinks = [];
  }

  var ultimaPos = parseInt(props.getProperty('ultimaPos') || '0', 10);

  // --- Primeira execução do ciclo: varre todas as abas para coletar os links ---
  if (todosLinks.length === 0) {
    ss.getSheets().forEach(function (sheet) {
      var nomeAba = sheet.getName();
      if (ehAbaDeEstrutura(nomeAba)) return;

      var valores = sheet.getDataRange().getValues();
      if (valores.length < 2) return;

      // Remove e isola a primeira linha (cabeçalhos) com segurança
      var headers = valores.shift();
      var indiceCabecalho = indexarCabecalho(headers);

      // Mapeia onde estão as colunas necessárias
      var idxLink = acharColuna(indiceCabecalho, 'LINK');
      if (idxLink === -1) return;

      // A busca normalizada cobre de uma vez todas as grafias possíveis
      // ('NOME', 'ORGANIZAÇÃO', 'ORGANIZACAO', 'Organização').
      var idxNome = acharColunaIdentificador(indiceCabecalho);

      // Varre as linhas de dados restantes
      valores.forEach(function (linha) {
        var link = linha[idxLink];
        if (typeof link === 'string' && link.match(/^https?:\/\//i)) {
          // Armazena em formato de OBJETO nomeado para evitar bugs de leitura
          todosLinks.push({
            url: link,
            nome: (idxNome !== -1) ? linha[idxNome] : '',
            aba: nomeAba
          });
        }
      });
    });

    if (todosLinks.length === 0) {
      relatar('Nenhum link encontrado para checar.');
      return;
    }

    // Limpa registros anteriores na aba de checagem.
    // Mantido o intervalo original C:F — a checagem grava em C, D e E, mas a
    // coluna F pode ter conteúdo de versões anteriores. Não reduzir o alcance
    // sem antes conferir o que existe em F na planilha.
    var ultimaLinha = abaDestino.getLastRow();
    if (ultimaLinha > 1) {
      abaDestino.getRange('C2:F' + ultimaLinha).clearContent();
    }
    ultimaPos = 0;
  }

  // --- Processa o lote atual de links coletados ---
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

  // Grava os erros deste lote na planilha de controle
  if (erros.length > 0) {
    abaDestino
      .getRange(abaDestino.getLastRow() + 1, 3, erros.length, 3)
      .setValues(erros);
  }

  // --- Finalização ou avanço do lote: atualiza os ponteiros de paginação ---
  if (fim >= todosLinks.length) {
    props.deleteProperty('todosLinks');
    props.deleteProperty('ultimaPos');
    SpreadsheetApp.getActive().toast(
      '✅ Checagem finalizada: ' + todosLinks.length + ' links verificados.'
    );
    return;
  }

  try {
    // Atualiza os ponteiros de paginação na memória do sistema
    props.setProperty('todosLinks', JSON.stringify(todosLinks));
    props.setProperty('ultimaPos', String(fim));
    SpreadsheetApp.getActive().toast(
      '🔎 ' + fim + '/' + todosLinks.length + ' — rode de novo para continuar.'
    );
  } catch (err) {
    // O limite por propriedade é de 9 KB; com muitos links o JSON estoura.
    // Sem interromper aqui, a checagem recomeçaria do zero a cada execução,
    // sem nunca terminar.
    props.deleteProperty('todosLinks');
    props.deleteProperty('ultimaPos');
    relatar(
      'Não foi possível salvar o progresso: são links demais para a memória '
      + 'do Apps Script.\n\nA checagem foi interrompida. Reduza LOTE_TAMANHO '
      + 'ou rode a checagem por partes.'
    );
  }
}


// =====================================================================
// 4. Menu e edição de link individual
// =====================================================================

/**
 * Cria o menu personalizado da planilha.
 *
 * Gatilho simples: o Apps Script chama esta função sozinho toda vez que a
 * planilha é aberta. Não deve ser executada manualmente.
 *
 * @return {void}
 */
function onOpen() {
  SpreadsheetApp.getUi()
    .createMenu('CHECAR LINKS')
    .addItem('Editar link selecionado', 'abrirDialog')
    .addToUi();
}


/**
 * Abre o diálogo de ação para o link selecionado na aba "CHECAR ABAS".
 * Espera que a célula ativa esteja na coluna C (LINK).
 *
 * Acionada pelo menu "CHECAR LINKS" → "Editar link selecionado".
 *
 * @return {void}
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

  // A referência ao arquivo do diálogo é por string e o editor do Apps Script
  // não a valida. Sem este tratamento, um arquivo renomeado produz um erro
  // genérico do Google, que não indica a causa nem o conserto.
  var template;
  try {
    template = HtmlService.createTemplateFromFile(ARQUIVO_DIALOGO);
  } catch (e) {
    SpreadsheetApp.getUi().alert(
      'Não foi possível abrir o diálogo: o arquivo "' + ARQUIVO_DIALOGO
      + '.html" não foi encontrado no projeto.\n\n'
      + 'Se ele foi renomeado, atualize a constante ARQUIVO_DIALOGO no topo '
      + 'do Codigo.gs para bater com o novo nome.'
    );
    return;
  }

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
 * Chamada pelo Dialog.html via google.script.run. Os erros lançados aqui
 * chegam ao withFailureHandler() do diálogo.
 *
 * @param {number} linha Linha em "CHECAR ABAS" a remover após a ação.
 * @param {string} linkAtual Link quebrado, usado para desambiguar organizações
 *     de mesmo nome.
 * @param {string} nomeOrg Nome da organização na aba de origem.
 * @param {string} nomeAbaOrigem Aba onde a organização está cadastrada.
 * @param {string} acao 'alterar' ou 'remover'.
 * @param {string} novoLink Link novo; usado apenas quando acao é 'alterar'.
 * @return {void}
 * @throws {Error} Se a aba não existir, se faltar coluna obrigatória, se a
 *     organização não for encontrada ou se a ação for desconhecida.
 */
function processarAcao(linha, linkAtual, nomeOrg, nomeAbaOrigem, acao, novoLink) {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var abaChecar = ss.getSheetByName('CHECAR ABAS');
  var abaOrigem = ss.getSheetByName(nomeAbaOrigem);

  if (!abaOrigem) {
    throw new Error('Aba de origem "' + nomeAbaOrigem + '" não encontrada.');
  }

  var headers = abaOrigem.getRange(1, 1, 1, abaOrigem.getLastColumn()).getValues()[0];
  var indiceCabecalho = indexarCabecalho(headers);

  // Busca que aceita NOME ou ORGANIZAÇÃO: as abas Aceleradoras, Hubs, Parques,
  // Institutos e Inovação nas Universidades usam ORGANIZAÇÃO.
  var idxNome = acharColunaIdentificador(indiceCabecalho);
  var idxLink = acharColuna(indiceCabecalho, 'LINK');
  var idxStatus = acharColuna(indiceCabecalho, 'STATUS');

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

  // Nome e link são localizados por índice próprio, sem presumir que LINK vem
  // logo depois de NOME.
  //
  // Uma única leitura do bloco que cobre as duas colunas, em vez de duas
  // chamadas à API. Ler um intervalo contíguo custa praticamente o mesmo que
  // ler uma coluna só — o caro é a ida e volta, não o volume.
  var colInicio = Math.min(idxNome, idxLink) + 1;
  var colFim = Math.max(idxNome, idxLink) + 1;
  var bloco = abaOrigem
    .getRange(2, colInicio, ultimaLinha - 1, colFim - colInicio + 1)
    .getValues();

  // Posição de cada coluna dentro do bloco lido.
  var posNome = idxNome + 1 - colInicio;
  var posLink = idxLink + 1 - colInicio;

  var nomeAlvo = String(nomeOrg).trim();
  var linkAlvo = String(linkAtual).trim();

  // Uma passada só: registra a primeira linha que casa por nome+link (ideal) e,
  // na mesma varredura, a primeira que casa apenas por nome (reserva).
  var linhaOrigem = null;
  var linhaSomenteNome = null;

  for (var i = 0; i < bloco.length; i++) {
    if (String(bloco[i][posNome]).trim() !== nomeAlvo) continue;

    // Casa por nome E link: só pelo nome, organizações homônimas faziam a
    // edição cair na linha errada.
    if (String(bloco[i][posLink]).trim() === linkAlvo) {
      linhaOrigem = i + 2;
      break;
    }

    if (linhaSomenteNome === null) linhaSomenteNome = i + 2;
  }

  // Sem o link correspondente, aceita só o nome — o link pode ter sido
  // alterado na planilha depois que a checagem rodou.
  if (linhaOrigem === null) linhaOrigem = linhaSomenteNome;

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

  // Apaga a linha da CHECAR ABAS
  abaChecar.deleteRow(linha);
}

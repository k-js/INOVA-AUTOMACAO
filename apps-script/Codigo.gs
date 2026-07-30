function checarAbasComStatus() {
  const planilha = SpreadsheetApp.getActiveSpreadsheet();
  const abasIgnoradas = [
    'HISTÓRICO', 
    'HOME', 
    'CHECAR ABAS', 
    'BEAUTYTECHS',  ///REMOVER LINHA QUANDO CRIAR ABA NO SITE
    'EVENTECHS',    ///REMOVER LINHA QUANDO CRIAR ABA NO SITE
    'FASHIONTECHS', ///REMOVER LINHA QUANDO CRIAR ABA NO SITE
    'GAMETECHS',    ///REMOVER LINHA QUANDO CRIAR ABA NO SITE
    'SECURITYTECHS', ///REMOVER LINHA QUANDO CRIAR ABA NO SITE
    'SPORTECHS',    ///REMOVER LINHA QUANDO CRIAR ABA NO SITE
    'TRAVELTECHS',   ///REMOVER LINHA QUANDO CRIAR ABA NO SITE
    'INSURTECHS'      ///REMOVER LINHA QUANDO CRIAR ABA NO SITE
    ];
  const abaChecagem = planilha.getSheetByName('CHECAR ABAS');
  if (!abaChecagem) {
    SpreadsheetApp.getUi().alert('A aba "CHECAR ABAS" não foi encontrada.');
    return;
  }

  const valoresAlvo = ['EDITAR', 'ADICIONAR AO SITE', 'REMOVER'];
  const abasComStatus = [];

  const todasAsAbas = planilha.getSheets();

  for (const aba of todasAsAbas) {
    const nomeAba = aba.getName();
    if (abasIgnoradas.includes(nomeAba)) continue;

    const dados = aba.getDataRange().getValues();
    const cabecalho = dados[0];
    const indiceStatus = cabecalho.indexOf('STATUS');
    if (indiceStatus === -1) continue;

    for (let i = 1; i < dados.length; i++) {
      const valorStatus = String(dados[i][indiceStatus]).toUpperCase().trim();
      if (valoresAlvo.includes(valorStatus)) {
        abasComStatus.push(nomeAba);
        break;
      }
    }
  }

  // Limpa e escreve os nomes na aba "CHECAR ABAS"
  abaChecagem.getRange('A2:A').clearContent();
  if (abasComStatus.length > 0) {
    const valoresParaInserir = abasComStatus.map(nome => [nome]);
    abaChecagem.getRange(2, 1, valoresParaInserir.length, 1).setValues(valoresParaInserir);
  }
}


function copiarPRParaMapaPowerBI() {
   var ss = SpreadsheetApp.getActiveSpreadsheet();
  
  // Mapeamento de nomes
  var mapeamentoNomes = {
    "ACELERADORAS E INCUBADORAS": "Aceleradora Incubadora",
    "PARQUES CIENTÍFICOS": "Parques Tecnológicos",
    "INOVAÇÃO NAS UNIVERSIDADES": "Inovação nas Universidades",
    "INSTITUTOS DE PESQUISA E CENTROS DE T&I": "Institutos de Pesquisa e Centros de T&I"
  };
  
  var abasOrigem = Object.keys(mapeamentoNomes);
  var abaDestino = ss.getSheetByName("MAPA POWER BI");
  
  // Limpa apenas a partir da linha 2
  if (abaDestino.getLastRow() > 1) {
    abaDestino.getRange(2, 1, abaDestino.getLastRow() - 1, abaDestino.getLastColumn()).clearContent();
  }
  
  var destinoDados = [];
  var cabecalhoFinal = null;
  
  abasOrigem.forEach(function(nomeAba) {
    var sheet = ss.getSheetByName(nomeAba);
    if (!sheet) return;
    
    var dados = sheet.getDataRange().getValues();
    if (dados.length < 2) return;
    
    var cabecalho = dados[0];
    var indiceUF = cabecalho.indexOf("UF");
    var indiceStatus = cabecalho.indexOf("STATUS");
    if (indiceUF === -1) return;
    
    // Cria cabeçalho final só uma vez
    if (!cabecalhoFinal) {
      var cabecalhoSemStatus = cabecalho.filter((_, idx) => idx !== indiceStatus);
      cabecalhoFinal = ["FILTRO BI"].concat(cabecalhoSemStatus);
    }
    
    for (var i = 1; i < dados.length; i++) {
      if (dados[i][indiceUF] === "PR") {
        var linhaSemStatus = dados[i].filter((_, idx) => idx !== indiceStatus);
        destinoDados.push([mapeamentoNomes[nomeAba]].concat(linhaSemStatus));
      }
    }
  });
  
  if (destinoDados.length > 0) {
    // Cabeçalho na linha 1
    abaDestino.getRange(1, 1, 1, cabecalhoFinal.length).setValues([cabecalhoFinal]);
    // Dados a partir da linha 2
    abaDestino.getRange(2, 1, destinoDados.length, destinoDados[0].length).setValues(destinoDados);
  }
}


function normalizarTexto(txt) {
  return txt
    .toString()
    .trim()
    .toUpperCase()
    .normalize("NFD") // separa acentos
    .replace(/[\u0300-\u036f]/g, ""); // remove acentos
}


function padronizarAbas() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sheets = ss.getSheets();

  // Helper para normalizar texto (mantive por segurança)
  function normalizarTexto(t) {
    if (t === null || t === undefined) return "";
    return String(t).toString().trim().toUpperCase();
  }

  // Lista de opções do dropdown de STATUS (primeiro item é string vazia)
  var statusOptions = [
    "", // deixa o seletor aparecer em branco inicialmente
    "REMOVER",
    "EDITAR",
    "ADICIONAR AO SITE",
    "ADICIONADO AO SITE",
  ];

  // Construir objeto de validação uma vez
  var statusValidation = SpreadsheetApp.newDataValidation()
    .requireValueInList(statusOptions, true) // true => mostrar dropdown
    .setAllowInvalid(false) // não permitir valores fora da lista
    .build();

  sheets.forEach(function (sheet) {
    var nomeAba = sheet.getName();

    // Ignorar abas específicas
    // CORRIGIDO: estava "CHECHAR ABAS" (com CH a mais), então a aba de controle
    // "CHECAR ABAS" nunca era pulada e acabava sendo formatada como se fosse
    // uma aba de dados.
    if (nomeAba == "HOME" || nomeAba == "CHECAR ABAS" || nomeAba == "HISTÓRICO") {
      return;
    }

    var lastRow = sheet.getLastRow();
    var lastCol = sheet.getLastColumn();

    if (lastRow > 0 && lastCol > 0) {
      // Cabeçalho (primeira linha)
      var headerRange = sheet.getRange(1, 1, 1, lastCol);
      headerRange.setFontWeight("bold")
                 .setFontSize(11)
                 .setFontFamily("Calibri")
                 .setBackground("#cfe2f3")
                 .setBorder(false, false, false, false, false, false)
                 .setHorizontalAlignment("center");

      // Restante da planilha
      if (lastRow > 1) {
        var dataRange = sheet.getRange(2, 1, lastRow - 1, lastCol);
        dataRange.setFontSize(11)
                 .setFontFamily("Calibri")
                 .setBackground(null)
                 .setFontWeight("normal")
                 .setFontColor("black")
                 .setBorder(false, false, false, false, false, false);
      }

      // Normalizar cabeçalhos
      var headerValues = sheet.getRange(1, 1, 1, lastCol).getValues()[0].map(normalizarTexto);

      // Função auxiliar para procurar e aplicar formatação
      function formatarColuna(nome, align, width, color) {
        var idx = headerValues.indexOf(normalizarTexto(nome));
        if (idx !== -1 && lastRow > 1) {
          var range = sheet.getRange(2, idx + 1, lastRow - 1, 1);
          if (align) range.setHorizontalAlignment(align);
          if (color) range.setFontColor(color);
          if (width) sheet.setColumnWidth(idx + 1, width);
        }
      }

      // Aplicar formatação
      formatarColuna("NOME", "left", 300);
      formatarColuna("LINK", null, 150, "blue");
      formatarColuna("UF", "center", 60);
      formatarColuna("CATEGORIA", "left", 150);
      formatarColuna("CIDADE", "center", 120);
      formatarColuna("PAIS", "center", 60);
      formatarColuna("CONTEUDO BALAO", "left", 400);
      formatarColuna("STATUS", "center", 200);

      // --- BLOCO CORRIGIDO: Aceita NOME ou ORGANIZAÇÃO sem quebrar ---
      var idxNome = headerValues.findIndex(function(header) {
        return header === "NOME" || header === "ORGANIZACAO" || header === "ORGANIZAÇÃO";
      });
      
      var idxStatus = headerValues.indexOf("STATUS");

      // Só executa se achar o STATUS, o Identificador (Nome/Org) e se houver linhas com dados
      if (idxStatus !== -1 && idxNome !== -1 && lastRow > 1) {
        // Pegar todas as células de NOME e STATUS de uma vez (para performance)
        var nomeRange = sheet.getRange(2, idxNome + 1, lastRow - 1, 1);
        var statusRange = sheet.getRange(2, idxStatus + 1, lastRow - 1, 1);
        var nomeVals = nomeRange.getValues();
        var statusVals = statusRange.getValues(); 

        // Iterar linhas e aplicar validação apenas onde NOME estiver em branco
        for (var i = 0; i < nomeVals.length; i++) {
          var nomeCell = nomeVals[i][0];

          if (String(nomeCell).toString().trim() === "") {
            // Aplica a validação na célula STATUS correspondente
            sheet.getRange(2 + i, idxStatus + 1).setDataValidation(statusValidation);
            // Limpar valor atual e deixar em branco
            sheet.getRange(2 + i, idxStatus + 1).setValue("");
          }
        }
      }
      // --- fim do bloco corrigido ---

      // Log para debug
      console.log("Aba:", nomeAba, " ->", headerValues);
    }
  });
}


function consolidarAbas() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var abaDestino = ss.getSheetByName("BI STARTUPS");
  
  // Limpa a aba destino
  abaDestino.clearContents();
  
  // Lista de abas que serão copiadas
  var abasOrigem = [
    "DEEPTECHS",
    "CONSTRUTECHS E PROPTECHS",
    "EDTECHS",
    "ENERGYTECHS",
    "FINTECHS",
    "FOODTECHS",
    "GOVTECHS",
    "GREENTECHS",
    "HEALTHTECHS",
    "INDTECHS",
    "LAWTECHS E LEGALTECHS",
    "LOGTECHS",
    "MARTECHS",
    "MOBITECHS",
    "PET TECHS",
    "RETAILTECHS",
    "SOCIALTECHS",
    "TECHS",
    "WATERTECHS"
  ];
  
  var linhaDestino = 1;
  var cabecalhoFinal = null;
  
  abasOrigem.forEach(function(nomeAba, index) {
    var aba = ss.getSheetByName(nomeAba);
    if (aba) {
      var valores = aba.getDataRange().getValues();
      if (valores.length === 0) return;
      
      // Identifica índices das colunas STATUS e CONTEÚDO BALÃO
      var cabecalho = valores[0];
      var idxStatus = cabecalho.indexOf("STATUS");
      var idxConteudo = cabecalho.indexOf("CONTEÚDO BALÃO");
      
      // Remove colunas indesejadas
      valores = valores.map(function(linha) {
        var novaLinha = [];
        for (var i = 0; i < linha.length; i++) {
          if (i !== idxStatus && i !== idxConteudo) {
            novaLinha.push(linha[i]);
          }
        }
        return novaLinha;
      });
      
      // Se for a primeira aba, monta o cabeçalho final com "TIPO"
      if (linhaDestino === 1) {
        cabecalhoFinal = ["TIPO"].concat(valores[0]);
        abaDestino.getRange(linhaDestino, 1, 1, cabecalhoFinal.length).setValues([cabecalhoFinal]);
        linhaDestino++;
      }
      
      // Remove cabeçalho das próximas abas
      var dados = valores.slice(1).map(function(linha) {
        return [nomeAba].concat(linha);
      });
      
      // Cola dados na aba destino
      if (dados.length > 0) {
        abaDestino.getRange(linhaDestino, 1, dados.length, dados[0].length).setValues(dados);
        linhaDestino += dados.length;
      }
    }
  });
}

function checarLinksErros() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var abaDestino = ss.getSheetByName("CHECAR ABAS");
  if (!abaDestino) return;

  var props = PropertiesService.getScriptProperties();
  var ignorar = ["HISTÓRICO", "CHECAR ABAS", "AGTECHS", "HOME", "BI STARTUPS", "MAPA POWER BI", "TESTE"];
  var lote = 40; 
  var pausa = 500; 

  // Carrega a lista da memória do Apps Script
  var todosLinks = [];
  try {
    todosLinks = JSON.parse(props.getProperty("todosLinks") || "[]");
  } catch (e) {
    todosLinks = [];
  }
  
  var ultimaPos = parseInt(props.getProperty("ultimaPos") || "0");

  if (todosLinks.length === 0) {
    // Varre todas as abas para coletar os links
    var sheets = ss.getSheets();
    sheets.forEach(function(sheet) {
      var nomeAba = sheet.getName();
      if (ignorar.indexOf(nomeAba) !== -1) return;

      var valores = sheet.getDataRange().getValues();
      if (valores.length < 2) return; 
      
      // Remove e isola a primeira linha (cabeçalhos) com segurança
      var headers = valores.shift(); 

      // Mapeia onde estão as colunas necessárias
      var idxLink = headers.indexOf("LINK");
      var idxNome = headers.indexOf("NOME");
      if (idxNome === -1) idxNome = headers.indexOf("ORGANIZAÇÃO");
      if (idxNome === -1) idxNome = headers.indexOf("ORGANIZACAO");
      if (idxNome === -1) idxNome = headers.indexOf("Organização");

      if (idxLink === -1) return;

      // Varre as linhas de dados restantes
      valores.forEach(function(linha) {
        var link = linha[idxLink];
        var nome = (idxNome !== -1) ? linha[idxNome] : "";
        
        if (typeof link === "string" && link.match(/^https?:\/\//i)) {
          // Armazena em formato de OBJETO nomeado para evitar bugs de leitura
          todosLinks.push({ url: link, nome: nome, aba: nomeAba });
        }
      });
    });

    // Limpa registros anteriores na aba de checagem
    var ultimaLinhaDestino = abaDestino.getLastRow();
    if (ultimaLinhaDestino > 1) {
      abaDestino.getRange("C2:F" + ultimaLinhaDestino).clearContent();
    }
    ultimaPos = 0;
  }

  // Processa o lote atual de links coletados
  var erros = [];
  var fim = Math.min(ultimaPos + lote, todosLinks.length);
  
  for (var i = ultimaPos; i < fim; i++) {
    var item = todosLinks[i];
    var urlAlvo = item.url;
    var nomeAlvo = item.nome;
    var abaAlvo = item.aba;

    var status = "OK";
    try {
      var response = UrlFetchApp.fetch(urlAlvo, { 
        muteHttpExceptions: true,
        followRedirects: true,
        validateHttpsCertificates: false
      });
      var code = response.getResponseCode();
      if (code !== 200 && code !== 403 && code !== 500) { 
        status = "Erro " + code;
      }
    } catch (e) {
      status = "Falhou";
    }

    if (status !== "OK") {
      erros.push([urlAlvo, nomeAlvo, abaAlvo]);
    }

    if ((i - ultimaPos + 1) % 10 === 0) Utilities.sleep(pausa); 
  }

  // Grava os erros deste lote na planilha de controle
  if (erros.length > 0) {
    var proximaLinhaDisponivel = abaDestino.getLastRow() + 1;
    abaDestino.getRange(proximaLinhaDisponivel, 3, erros.length, 3).setValues(erros);
  }

  // Atualiza os ponteiros de paginação na memória do sistema
  try {
    props.setProperty("todosLinks", JSON.stringify(todosLinks));
    props.setProperty("ultimaPos", String(fim));
  } catch (err) {
    SpreadsheetApp.getActive().toast("Armazenamento temporário cheio.", "Aviso");
  }

  // Finalização ou avanço do lote
  if (fim >= todosLinks.length) {
    props.deleteProperty("todosLinks");
    props.deleteProperty("ultimaPos");
    SpreadsheetApp.getActive().toast("✅ Checagem de links finalizada com sucesso!");
  } else {
    SpreadsheetApp.getActive().toast("🔎 Links processados: " + fim + "/" + todosLinks.length);
  }
}



function onOpen() {
  SpreadsheetApp.getUi()
    .createMenu('CHECAR LINKS')
    .addItem('Editar link selecionado', 'abrirDialog')
    .addToUi();
}


function abrirDialog() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var aba = ss.getActiveSheet();
  var range = aba.getActiveRange();

  if (aba.getName() !== "CHECAR ABAS" || range.getColumn() !== 3) {
    SpreadsheetApp.getUi().alert("Selecione uma célula da coluna LINK (C) na aba CHECAR ABAS");
    return;
  }

  var linha = range.getRow();
  if (linha < 2) return;

  var linkAtual = range.getValue();
  var nomeOrg = aba.getRange(linha, 4).getValue();
  var nomeAbaOrigem = aba.getRange(linha, 5).getValue();

  var template = HtmlService.createTemplateFromFile('Dialog');
  template.linha = linha;
  template.linkAtual = linkAtual;
  template.nomeOrg = nomeOrg;
  template.nomeAbaOrigem = nomeAbaOrigem;

  var html = template.evaluate()
      .setWidth(400)
      .setHeight(200);
  SpreadsheetApp.getUi().showModalDialog(html, 'Ação para Link');
}


function processarAcao(linha, linkAtual, nomeOrg, nomeAbaOrigem, acao, novoLink) {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var abaChecar = ss.getSheetByName("CHECAR ABAS");
  var abaOrigem = ss.getSheetByName(nomeAbaOrigem);
  if (!abaOrigem) return;

  var headers = abaOrigem.getRange(1, 1, 1, abaOrigem.getLastColumn()).getValues()[0];
  var idxLink = headers.indexOf("LINK") + 1;
  var idxNome = headers.indexOf("NOME") + 1;
  var idxStatus = headers.indexOf("STATUS") + 1;
  if (idxLink === 0 || idxNome === 0 || idxStatus === 0) return;

  var valores = abaOrigem.getRange(2, idxNome, abaOrigem.getLastRow() - 1, 2).getValues();
  var linhaOrigem = null;
  for (var i = 0; i < valores.length; i++) {
    if (valores[i][0] === nomeOrg) {
      linhaOrigem = i + 2;
      break;
    }
  }
  if (!linhaOrigem) return;

  if (acao === 'alterar') {
    abaOrigem.getRange(linhaOrigem, idxLink).setValue(novoLink);
    abaOrigem.getRange(linhaOrigem, idxStatus).setValue('EDITAR');
  } else if (acao === 'remover') {
    abaOrigem.getRange(linhaOrigem, idxStatus).setValue("REMOVER");
  }

  // Apaga a linha da CHECAR ABAS
  abaChecar.deleteRow(linha);
}

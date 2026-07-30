import pandas as pd
from datetime import datetime
import pyperclip
from conexao_api import client
import gspread.exceptions
from atualizador_WP import atualizar_pagina_wp
import re
from io import StringIO

def get_video_id(link):
    match = re.search(r'(?:v=|\/)([0-9A-Za-z_-]{11})(?:[&?]|$)', link)
    return match.group(1) if match else ''

def processa_pitchs_com_historico():
    try:
        planilha = client.open("PORTAL DA INOVAÇÃO E STARTUPS")
        aba = planilha.worksheet("PITCHS DE STARTUPS")

        dados_raw = aba.get_all_values()
        if not dados_raw:
            print("Aba PITCHS DE STARTUPS vazia.")
            return None

        cabecalho = dados_raw[0]
        data_linhas = dados_raw[1:]

        # Mapeamento de colunas esperadas
        col_map = {nome.upper().strip(): i for i, nome in enumerate(cabecalho)}
        required = ["NOME", "CATEGORIA", "LINK", "STATUS"]
        if not all(col in col_map for col in required):
            print("Colunas obrigatórias ausentes em PITCHS DE STARTUPS.")
            return None

        idx_nome = col_map["NOME"]
        idx_categoria = col_map["CATEGORIA"]
        idx_link = col_map["LINK"]
        idx_status = col_map["STATUS"]

        novas_linhas_aba = [cabecalho]
        entradas, saidas = [], []

        for linha in data_linhas:
            if len(linha) <= idx_status:
                novas_linhas_aba.append(linha)
                continue

            status = str(linha[idx_status]).strip().upper()
            nome = linha[idx_nome] if len(linha) > idx_nome else ""
            categoria = linha[idx_categoria] if len(linha) > idx_categoria else ""
            link = linha[idx_link] if len(linha) > idx_link else ""
            timestamp = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

            if status == "ADICIONAR AO SITE":
                entradas.append(["ENTRADA", "PITCHS DE STARTUPS", timestamp, nome, categoria, link])
                linha_mod = list(linha)
                linha_mod[idx_status] = "ADICIONADO AO SITE"
                novas_linhas_aba.append(linha_mod)
            elif status == "REMOVER":
                saidas.append(["SAÍDA", "PITCHS DE STARTUPS", timestamp, nome, categoria, link])
            else:
                novas_linhas_aba.append(linha)

        # Atualiza aba original
        aba.clear()
        if novas_linhas_aba:
            aba.update(f"A1:{chr(65 + len(cabecalho) - 1)}{len(novas_linhas_aba)}", novas_linhas_aba)

        # Atualiza aba HISTÓRICO
        try:
            aba_historico = planilha.worksheet("HISTÓRICO")
        except gspread.exceptions.WorksheetNotFound:
            aba_historico = planilha.add_worksheet("HISTÓRICO", rows=1, cols=10)
            aba_historico.append_row(["TIPO OPERAÇÃO", "ABA", "DATA", "NOME", "CATEGORIA", "LINK"])

        historico = entradas + saidas
        if historico:
            aba_historico.append_rows(historico)
            print(f"{len(historico)} linhas adicionadas à aba HISTÓRICO.")
        return True

    except Exception as e:
        print(f"Erro ao processar histórico: {e}")
        return None

def gerar_html_pitchs(df):
    if df.empty:
        print("DataFrame vazio, nada para gerar.")
        return None

    # Filtrar apenas linhas com dados válidos
    df = df.dropna(subset=['NOME', 'LINK'], how='all')
    df = df[(df['NOME'].str.strip() != '') & (df['LINK'].str.strip() != '')]
    
    html = StringIO()
    
    # Escrever o cabeçalho da tabela
    html.write("""
<body>
<!-- COMECA ATUALIZAR DAQUI -->
    <div class="container">
        <input type="text" id="searchInput" placeholder="Pesquise por vídeo...">
    </div>
<div class="p-2 mr-2" id="count">
<p><b>Total de organizações:</b> """ + str(len(df)) + """</p>
</div>

<table id="organization_table">
    <thead>
        <tr>
            <th scope="col">
                <p>Organização</p>
            </th>
            <th scope="col">
                <select id="categoriaSelect" onchange="filterTable()">
                    <option value="">Categorias</option>
                </select>
            </th>
            <th scope="col">
                <select id="instituicaoSelect" onchange="filterTable()" style="width: 350px; overflow: hidden; text-overflow: ellipsis;">
                    <option value="">Instituições</option>
                </select>
            </th>
            <th scope="col">
                <select id="segmentoSelect" onchange="filterTable()">
                    <option value="">Segmentos</option>
                </select>
            </th>
        </tr>
    </thead>
    <tbody>
""")
    
    # Escrever as linhas da tabela seguindo exatamente o padrão
    for _, row in df.iterrows():
        video_id = get_video_id(str(row.get("LINK", "")))
        if not video_id:
            continue

        nome = row.get('NOME', '')
        categoria = row.get('CATEGORIA', '')
        instituicao = row.get('INSTITUIÇÃO', '')
        segmento = row.get('SEGMENTO', '')
        link = row.get('LINK', '')
        conteudo_balao = row.get('CONTEÚDO BALÃO', '')
        embed_link = f"https://www.youtube.com/embed/{video_id}"
        thumb_link = f"https://img.youtube.com/vi/{video_id}/0.jpg"

        html.write(f"""
        <tr class="organizationRow"
            data-categoria="{categoria}"
            data-instituicao="{instituicao}"
            data-segmento="{segmento}">
            <td scope="row" style="text-align: center; position: relative; width: 600px;">
                <div style="color: darkblue; font-weight: bold; margin-bottom: 5px;">
                    <a href="{link}" target="_blank">{nome}</a>
                </div>
                <a href="#" onclick="openFullscreen('{embed_link}')"
                    style="display: inline-block; position: relative;">
                    <div class="tooltip-container">
                        <img src="{thumb_link}" alt="Miniatura do vídeo"
                            style="width: 180px; cursor: pointer; display: block;">
                        <div class="play-button">▶</div>
                        <span class="tooltip-inner">{conteudo_balao}</span>
                    </div>
                </a>
            </td>
            <td style="text-align: center; vertical-align: middle;">{categoria}</td>
            <td style="text-align: center; vertical-align: middle;">{instituicao}</td>
            <td style="text-align: center; vertical-align: middle;">{segmento}</td>
        </tr>
        """)

    # Fechar a tabela e adicionar os elementos restantes
    html.write("""
    </tbody>
</table>

<div class="video-container">
    <div id="videoModal">
        <iframe id="fullscreenVideo" frameborder="0"
            allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
            allowfullscreen></iframe>
        <button id="closeButton" onclick="closeFullscreen()">Fechar</button>
    </div>
</div>

<script src="https://code.jquery.com/jquery-3.6.0.min.js"></script>

<script>
    function openFullscreen(videoUrl) {
        document.getElementById("fullscreenVideo").src = videoUrl + "?autoplay=1";
        document.getElementById("videoModal").style.display = "flex";
    }

    function closeFullscreen() {
        document.getElementById("fullscreenVideo").src = "";
        document.getElementById("videoModal").style.display = "none";
    }

    function updateOrganizationCount() {
        var visibleRows = $("#organization_table tbody tr:visible").length;
        $("#count p").html("<b>Total de organizações:</b> " + visibleRows);
    }

    function populateSelects() {
        var categoriaSet = new Set();
        var instituicaoSet = new Set();
        var segmentoSet = new Set();

        $("#organization_table tbody tr").each(function() {
            categoriaSet.add($(this).data("categoria"));
            instituicaoSet.add($(this).data("instituicao"));
            segmentoSet.add($(this).data("segmento"));
        });

        var categoriaArray = Array.from(categoriaSet).sort();
        var instituicaoArray = Array.from(instituicaoSet).sort();
        var segmentoArray = Array.from(segmentoSet).sort();

        categoriaArray.forEach(function(categoria) {
            if (categoria) {
                $("#categoriaSelect").append(new Option(categoria, categoria));
            }
        });

        instituicaoArray.forEach(function(instituicao) {
            if (instituicao) {
                $("#instituicaoSelect").append(new Option(instituicao, instituicao));
            }
        });

        segmentoArray.forEach(function(segmento) {
            if (segmento) {
                $("#segmentoSelect").append(new Option(segmento, segmento));
            }
        });
    }

    function filterTable() {
        var categoriaFilter = $("#categoriaSelect").val()?.toLowerCase() || "";
        var instituicaoFilter = $("#instituicaoSelect").val()?.toLowerCase() || "";
        var segmentoFilter = $("#segmentoSelect").val()?.toLowerCase() || "";

        $("#organization_table tbody tr").each(function() {
            var categoriaText = ($(this).data("categoria") || "").toLowerCase();
            var instituicaoText = ($(this).data("instituicao") || "").toLowerCase();
            var segmentoText = ($(this).data("segmento") || "").toLowerCase();

            if ((categoriaFilter === "" || categoriaText === categoriaFilter) &&
                (instituicaoFilter === "" || instituicaoText === instituicaoFilter) &&
                (segmentoFilter === "" || segmentoText === segmentoFilter)) {
                $(this).show();
            } else {
                $(this).hide();
            }
        });

        updateOrganizationCount();
    }

    $(document).ready(function() {
        populateSelects();
        updateOrganizationCount();

        $("#categoriaSelect, #instituicaoSelect, #segmentoSelect").on("change", function() {
            filterTable();
        });

        $("#searchInput").on("keyup", function() {
            var value = $(this).val().toLowerCase();
            $("#organization_table tr.organizationRow").filter(function() {
                $(this).toggle($(this).text().toLowerCase().indexOf(value) > -1);
            });
            updateOrganizationCount();
        });
    });
</script>
</body>
</html>
""")

    result_html = html.getvalue()
    pyperclip.copy(result_html)
    print("HTML copiado para a área de transferência.")
    return result_html


def gerar_html_pitchs_via_api():
    try:
        planilha = client.open("PORTAL DA INOVAÇÃO E STARTUPS")
        aba = planilha.worksheet("PITCHS DE STARTUPS")
        dados = aba.get_all_records()
        df = pd.DataFrame(dados)

        processa_pitchs_com_historico()
        return gerar_html_pitchs(df)

    except Exception as e:
        print(f"Erro ao gerar HTML dos pitchs: {e}")
        return None

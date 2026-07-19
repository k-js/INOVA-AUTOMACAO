import pandas as pd
import os
import pyperclip
from datetime import datetime
import gspread
import gspread.exceptions
import unicodedata
from conexao_api import client

def numero_para_coluna(n):
    resultado = ''
    while n:
        n, r = divmod(n - 1, 26)
        resultado = chr(65 + r) + resultado
    return resultado

def _normalizar(texto):
    """Deixa maiúsculo e remove acentos, para comparação flexível de nomes de coluna."""
    if texto is None:
        return ''
    texto = str(texto).strip().upper()
    texto = unicodedata.normalize('NFKD', texto).encode('ASCII', 'ignore').decode('ASCII')
    return texto

# ✅ Detecta a coluna de identificação da organização (NOME, ORGANIZAÇÃO, etc.),
# de forma flexível: ignora maiúsculas/minúsculas e acentos.
def encontrar_coluna_identificador(cabecalho):
    variacoes_aceitas = {
        "NOME OU ORGANIZACAO",
        "ORGANIZACAO",
        "NOME",
    }
    for col in cabecalho:
        if _normalizar(col) in variacoes_aceitas:
            return col  # retorna o nome EXATO como está no cabeçalho da planilha
    return None

def gerar_html_3COL(
    aba,
    output_directory=r"C:\Users\marco\OneDrive\Área de Trabalho\Economia\INOVA\tabelas-atualizadas"
):
    try:
        planilha = client.open("PORTAL DA INOVAÇÃO E STARTUPS")
        aba_origem = planilha.worksheet(aba)

        try:
            aba_historico = planilha.worksheet("HISTÓRICO")
        except gspread.exceptions.WorksheetNotFound:
            aba_historico = planilha.add_worksheet("HISTÓRICO", rows=1, cols=10)
            print("Aba 'HISTÓRICO' criada.")

        dados_origem_raw = aba_origem.get_all_values()
        if not dados_origem_raw:
            print(f"A aba '{aba}' está vazia.")
            return None

        cabecalho = dados_origem_raw[0]

        if 'STATUS' not in cabecalho:
            print(f"Coluna 'STATUS' ausente na aba '{aba}'.")
            return None

        status_index = cabecalho.index("STATUS")
        coluna_identificador = encontrar_coluna_identificador(cabecalho) or "NOME"
        colunas_desejadas = [coluna_identificador, "CATEGORIA", "LINK", "PAÍS", "CONTEÚDO BALÃO"]
        indices_colunas_desejadas = [cabecalho.index(col) for col in colunas_desejadas if col in cabecalho]
        colunas_presentes = [col for col in colunas_desejadas if col in cabecalho]

        novas_linhas_saida = []
        novas_linhas_entrada = []
        novas_linhas_origem = [cabecalho]

        for linha in dados_origem_raw[1:]:
            if len(linha) <= status_index:
                novas_linhas_origem.append(linha)
                continue
            status = linha[status_index].strip().upper()
            dados_base = [linha[idx] if idx < len(linha) else '' for idx in indices_colunas_desejadas]

            if status == "REMOVER":
                novas_linhas_saida.append(["SAÍDA", aba, datetime.now().strftime("%d/%m/%Y %H:%M:%S")] + dados_base)
            elif status in ("ADICIONAR AO SITE", "EDITAR"):
                novas_linhas_entrada.append(["ENTRADA", aba, datetime.now().strftime("%d/%m/%Y %H:%M:%S")] + dados_base)
                linha[status_index] = "ADICIONADO AO SITE"
                novas_linhas_origem.append(linha)
            else:
                novas_linhas_origem.append(linha)

        aba_origem.clear()
        if novas_linhas_origem:
            aba_origem.update(f"A1:{numero_para_coluna(len(novas_linhas_origem[0]))}{len(novas_linhas_origem)}", novas_linhas_origem)

        if not aba_historico.get_all_values():
            aba_historico.append_row(["TIPO OPERAÇÃO", "ABA", "DATA"] + colunas_presentes)

        if novas_linhas_saida + novas_linhas_entrada:
            aba_historico.append_rows(novas_linhas_saida + novas_linhas_entrada)

        data = pd.DataFrame(aba_origem.get_all_records())

    # ✅ Padroniza a coluna de identificação para 'NOME', não importa se na planilha
        # ela está como 'NOME', 'ORGANIZAÇÃO', 'Organização', 'ORGANIZACAO', etc.
        coluna_identificada_df = encontrar_coluna_identificador(list(data.columns))
        if coluna_identificada_df and coluna_identificada_df != 'NOME':
            data = data.rename(columns={coluna_identificada_df: 'NOME'})
        elif 'NOME' not in data.columns:
            data['NOME'] = ''

    except Exception as e:
        print(f"Erro: {e}")
        return None

    if data.empty:
        print(f"Aba '{aba}' sem dados para HTML.")
        return None

    def formatar_nome(nome):
        preps = {'de', 'da', 'do', 'das', 'dos', 'em', 'no', 'na', 'nos', 'nas', 'a', 'o', 'e', 'com', 'para', 'por', 'sob', 'sem'}
        if not isinstance(nome, str): return nome
        palavras = nome.split()
        return ' '.join([
            palavra.lower() if palavra.lower() in preps and i != 0 else palavra.capitalize()
            for i, palavra in enumerate(palavras)
        ])

    data['NOME'] = data['NOME'].apply(formatar_nome)
    data = data.sort_values(by='NOME', key=lambda col: col.str.lower())

    if len(data.columns) < 4:
        print("Planilha com colunas insuficientes.")
        return None

    quarta_coluna = data.columns[3]
    seletor_id = "paisSelect"
    seletor_label = "Todos os Países"
    data_attr = "pais"

    html = f"""
<!-- COMECA ATUALIZAR DAQUI -->
<div class="p-2 mr-2" id="count">
<p><b>Total de organizações:</b> {len(data)}</p>
</div>
<table class="table" id="organization_table">
<thead>
<tr>
<th scope="col"><p>Organização</p></th>
<th scope="col"><select id="{seletor_id}" onchange="filterTable()"><option value="">{seletor_label}</option></select></th>
<th scope="col"><select id="categoriaSelect" onchange="filterTable()"><option value="">Todas Categorias</option></select></th>
</tr>
</thead>
<tbody>
"""
    for _, row in data.iterrows():
        nome = row.get('NOME', '').strip()
        link = row.get('LINK', '').strip()
        if not link.startswith(('http://', 'https://')):
            link = 'http://' + link
        pais = row.get(quarta_coluna, '').strip()
        categoria = row.get('CATEGORIA', '').strip()
        conteudo_balao = row.get('CONTEÚDO BALÃO', '').strip()

        html += f"""
<tr class="organizationRow" data-{data_attr}="{pais}" data-categoria="{categoria}">
<td scope="row">
<span data-bs-placement="bottom" data-bs-toggle="tooltip" title="{conteudo_balao}">
<a href="{link}" rel="noopener noreferrer" target="_blank">{nome}</a>
</span>
</td>
<td>{pais}</td>
<td>{categoria}</td>
</tr>
"""
    html += """
</tbody>
</table>
<script src="https://code.jquery.com/jquery-3.6.0.min.js"></script>

<script>
function populateSelects() {
    let paisSet = new Set();
    let categoriaSet = new Set();
    $("#organization_table tbody tr").each(function() {
        let pais = $(this).data("pais");
        let categoria = $(this).data("categoria");
        if (pais) paisSet.add(pais);
        if (categoria) categoriaSet.add(categoria);
    });
    paisSet.forEach(p => { $("#paisSelect").append(new Option(p, p)); });
    categoriaSet.forEach(c => { $("#categoriaSelect").append(new Option(c, c)); });
}

function filterTable() {
    let pais = ($("#paisSelect").val() || "").toLowerCase();
    let categoria = ($("#categoriaSelect").val() || "").toLowerCase();

    $("#organization_table tbody tr").filter(function() {
        let p = ($(this).data("pais") || "").toLowerCase();
        let c = ($(this).data("categoria") || "").toLowerCase();
        $(this).toggle((!pais || p === pais) && (!categoria || c === categoria));
    });
}

$(document).ready(function() {
    populateSelects();
    $("#search").on("keyup", function() {
        var value = $(this).val().toLowerCase();
        $("#organization_table tr.organizationRow").filter(function() {
            $(this).toggle($(this).text().toLowerCase().indexOf(value) > -1)
        });
    });
});
</script>

"""
    try:
        os.makedirs(output_directory, exist_ok=True)
        with open(os.path.join(output_directory, f"{aba}.html"), "w", encoding="utf-8") as f:
            f.write(html)
        pyperclip.copy(html)
        print(f"HTML da aba '{aba}' gerado com sucesso.")
    except Exception as e:
        print(f"Erro ao salvar ou copiar HTML: {e}")

    return html

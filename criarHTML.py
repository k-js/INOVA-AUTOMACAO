import pandas as pd
import os
import pyperclip
from datetime import datetime
import gspread
import gspread.exceptions # Importa exceções específicas do gspread

# Assumindo que 'client' vem de 'conexao_api' e é um objeto gspread.Client autenticado
# Certifique-se de que conexao_api.py configura um cliente gspread.Client para Sheets API
from conexao_api import client 

def safe_str(val, default=''):
    if pd.isna(val) or val is None:
        return default
    return str(val).strip()


# Função auxiliar para converter número de coluna para letra (ex: 1 -> A, 26 -> Z, 27 -> AA)
def numero_para_coluna(n):
    resultado = ''
    while n:
        n, r = divmod(n - 1, 26)
        resultado = chr(65 + r) + resultado
    return resultado

# Função principal para processar a aba da planilha e gerar o HTML
def processa_aba_gera_html(aba,
                           output_directory=r"C:\Users\marco\OneDrive\Área de Trabalho\Economia\INOVA\tabelas-atualizadas"):
    try:
        # Abre a planilha pelo nome
        planilha = client.open("PORTAL DA INOVAÇÃO E STARTUPS")
        # Obtém a aba de origem (a aba que está sendo processada)
        aba_origem = planilha.worksheet(aba) 
        
        # Tenta obter a aba "HISTÓRICO". Se não existir, cria uma nova.
        try:
            aba_historico = planilha.worksheet("HISTÓRICO")
        except gspread.exceptions.WorksheetNotFound:
            # Cria a aba "HISTÓRICO" com algumas linhas e colunas iniciais. 
            # O número de colunas pode ser ajustado para ser mais dinâmico,
            # mas este é um bom ponto de partida.
            aba_historico = planilha.add_worksheet("HISTÓRICO", rows=1, cols=10) 
            print("Aba 'HISTÓRICO' criada.")


        # Obtém todos os valores da aba de origem como uma lista de listas
        dados_origem_raw = aba_origem.get_all_values()
        
        # Se a aba de origem estiver vazia, imprime uma mensagem e retorna um DataFrame vazio para o HTML
        if not dados_origem_raw:
            print(f"A aba '{aba}' está vazia. Nenhuma operação de histórico será realizada.")
            data = pd.DataFrame()
            # Pula o processamento histórico e vai direto para a geração HTML
            return _generate_html_and_save(data, aba, output_directory)

        # Extrai o cabeçalho da primeira linha dos dados
        cabecalho = dados_origem_raw[0]
        
        # Verifica se a coluna 'STATUS' existe no cabeçalho
        if 'STATUS' not in cabecalho:
            print(f"A coluna 'STATUS' não foi encontrada na aba '{aba}'. A função de histórico não será executada.")
            # Se 'STATUS' não existe, cria um DataFrame com os dados existentes (sem a lógica de status)
            # e procede para a geração HTML
            data = pd.DataFrame(dados_origem_raw[1:], columns=cabecalho)
            return _generate_html_and_save(data, aba, output_directory)

        # Encontra o índice da coluna 'STATUS'
        status_index = cabecalho.index("STATUS")
        
        # Define as colunas desejadas para o registro no histórico
        coluna_identificador = "Organização" if "Organização" in cabecalho else "NOME"
        colunas_desejadas = [coluna_identificador, "CATEGORIA", "LINK", "CIDADE", "UF", "CONTEÚDO BALÃO"]
        # Encontra os índices das colunas desejadas que realmente existem no cabeçalho
        indices_colunas_desejadas = []
        colunas_desejadas_presentes = []
        for col in colunas_desejadas:
            if col in cabecalho:
                indices_colunas_desejadas.append(cabecalho.index(col))
                colunas_desejadas_presentes.append(col)
            else:
                print(f"Aviso: Coluna '{col}' não encontrada no cabeçalho da aba '{aba}'. Será ignorada para o histórico.")
                # Se a coluna não for encontrada, seu índice não é adicionado, e o 'dados_base' usará vazios.

        # Listas para armazenar as linhas que serão adicionadas ao histórico
        novas_linhas_saida = []
        novas_linhas_entrada = []
        # Lista para armazenar as linhas que permanecerão na aba de origem (incluindo o cabeçalho)
        novas_linhas_origem = [cabecalho] 

        # Itera sobre as linhas de dados (a partir da segunda linha, índice 1)
        for i in range(1, len(dados_origem_raw)):
            linha = dados_origem_raw[i]
            
            # Garante que a linha tem elementos suficientes para acessar a coluna STATUS
            if len(linha) <= status_index:
                novas_linhas_origem.append(linha) # Mantém a linha original se a coluna STATUS estiver faltando
                continue

            # Obtém o status da linha e converte para maiúsculas para comparação
            status = str(linha[status_index]).strip().upper() 

            # Extrai os dados base para o registro no histórico, garantindo que o índice existe na linha
            dados_base = []
            for idx in indices_colunas_desejadas:
                if idx < len(linha): # Verifica se o índice é válido para a linha atual
                    dados_base.append(linha[idx])
                else:
                    dados_base.append("") # Adiciona valor vazio se a linha não tiver a coluna

            # Lógica para processar as linhas com base no STATUS
            if status == "REMOVER":
                # Adiciona a linha à lista de saída com tipo de operação, aba, data e dados base
                novas_linhas_saida.append(["SAÍDA", aba, datetime.now().strftime("%d/%m/%Y %H:%M:%S")] + dados_base)
            elif status == "ADICIONAR AO SITE":
                # Adiciona a linha à lista de entrada com tipo de operação, aba, data e dados base
                novas_linhas_entrada.append(["ENTRADA", aba, datetime.now().strftime("%d/%m/%Y %H:%M:%S")] + dados_base)
                # Atualiza o status na linha original para ser gravada de volta na aba de origem
                linha_copia = list(linha) # Cria uma cópia da linha para modificar
                linha_copia[status_index] = "ADICIONADO AO SITE"
                novas_linhas_origem.append(linha_copia)
            elif status == "EDITAR":
                linha_copia = list(linha)
                linha_copia[status_index] = "ADICIONADO AO SITE"
                novas_linhas_origem.append(linha_copia)
            else:
                # Mantém a linha original se o status não for "REMOVER" ou "ADICIONAR AO SITE"
                novas_linhas_origem.append(linha)

        # --- Atualiza a aba de origem ---
        # Limpa todo o conteúdo da aba de origem
        aba_origem.clear() 
        # Se houver dados para escrever de volta, atualiza a aba de origem com as novas linhas
        if novas_linhas_origem:
            num_rows_origem = len(novas_linhas_origem)
            # Certifica-se de que há pelo menos uma linha para pegar o comprimento
            num_cols_origem = len(novas_linhas_origem[0]) if num_rows_origem > 0 else 0
            if num_rows_origem > 0 and num_cols_origem > 0:
                aba_origem.update(f"A1:{numero_para_coluna(num_cols_origem)}{num_rows_origem}", novas_linhas_origem)
                print(f"Aba '{aba}' atualizada com {num_rows_origem} linhas.")
            else:
                print(f"Não há dados para escrever de volta na aba '{aba}' (apenas cabeçalho ou vazia).")

        # --- Adiciona cabeçalho na aba histórico se estiver vazia ---
        # Define o cabeçalho completo para a aba de histórico
        historico_cabecalho_completo = ["TIPO OPERAÇÃO", "ABA", "DATA"] + colunas_desejadas_presentes
        
        # Verifica se a aba de histórico está vazia (sem nenhum valor, ou apenas vazia de conteúdo)
        if not aba_historico.get_all_values(): # Verifica se a aba está completamente vazia
            aba_historico.append_row(historico_cabecalho_completo)
            print("Cabeçalho adicionado à aba 'HISTÓRICO'.")

        # --- Insere novas entradas no histórico ---
        updates_to_historico = []
        if novas_linhas_saida:
            updates_to_historico.extend(novas_linhas_saida)
        if novas_linhas_entrada:
            updates_to_historico.extend(novas_linhas_entrada)
        
        # Se houver linhas para adicionar ao histórico, usa append_rows para maior eficiência
        if updates_to_historico:
            aba_historico.append_rows(updates_to_historico)
            print(f"Adicionadas {len(updates_to_historico)} entradas ao histórico.")
        else:
            print("Nenhuma linha nova para adicionar ao histórico.")


        print(f"Função de atualização de histórico (em Python) executada para aba '{aba}'.")

        # --- Recarrega os dados da aba de origem para a geração HTML (após todas as modificações) ---
        # get_all_records() lê os dados da planilha e os converte em uma lista de dicionários
        dados_para_html = aba_origem.get_all_records()
        data = pd.DataFrame(dados_para_html)
        
        # --- NOVO TRATAMENTO HÍBRIDO (CORRIGE O ERRO DE DATAFRAME VAZIO) ---
        # Procura qual variação da coluna existe sem alterar o nome das outras colunas da planilha
        coluna_identificada = None
        for col in data.columns:
            if str(col).strip().upper() in ["NOME", "ORGANIZAÇÃO", "ORGANIZACAO", "ORGANIZAÇAO"]:
                coluna_identificada = col
                break
        
        # Cria ou padroniza a coluna 'NOME' interna com base no que foi encontrado
        if coluna_identificada:
            data['NOME'] = data[coluna_identificada]
        elif 'NOME' not in data.columns:
            data['NOME'] = ''
        # ------------------------------------------------------------------



    except Exception as e:
        print(f"Erro ao processar aba '{aba}': {e}")
        return None


    # --- Lógica de Geração HTML e Salvamento ---
    # Se o DataFrame de dados estiver vazio, imprime mensagem e retorna
    if data.empty:
        print(f"Nenhum dado disponível para gerar o HTML da aba '{aba}'.")
        return None

    # Função interna para formatar nomes (primeira letra maiúscula, preposições em minúsculas)
    def formatar_nome(nome):
        preposicoes = {'de', 'da', 'do', 'das', 'dos', 'em', 'no', 'na', 'nos', 'nas', 'a', 'o', 'e', 'com', 'para', 'por', 'sob', 'sem'}
        if not isinstance(nome, str) or not nome:
            return nome
        palavras = nome.split()
        nome_formatado = []
        for i, palavra in enumerate(palavras):
            if palavra.lower() in preposicoes:
                nome_formatado.append(palavra.lower())
            elif i == 0:
                nome_formatado.append(palavra[0].upper() + palavra[1:] if palavra else '')
            else:
                nome_formatado.append(palavra)
        return ' '.join(nome_formatado)

    # Aplica a formatação de nome à coluna 'NOME' do DataFrame
    data['NOME'] = data['NOME'].apply(formatar_nome)
    data = data.sort_values(by='NOME', key=lambda col: col.str.lower())

    # Obtém a lista de colunas do DataFrame
    colunas = list(data.columns)
    # Verifica se há pelo menos 5 colunas
    if len(colunas) < 5:
        print("A planilha não tem pelo menos cinco colunas.")
        return None

    # Define o nome da quinta coluna e os IDs/rótulos dos seletores HTML com base nela
    quinta_coluna_nome = colunas[4]
    seletor_id = "cidadeSelect" if quinta_coluna_nome.upper() == "CIDADE" else "paisSelect"
    seletor_label = "Todas Cidades" if quinta_coluna_nome.upper() == "CIDADE" else "Todos os Países"
    data_attr = "cidade" if quinta_coluna_nome.upper() == "CIDADE" else "pais"

    # Função interna para gerar a tabela HTML com os dados da planilha
    def generate_html_table(data):
        html = f"""
<table class="table" id="organization_table">
<thead>
<tr>
<th scope="col"><p>Organização</p></th>
<th scope="col"><select id="ufSelect" onchange="filterTable()"><option value="">Todos Estados</option></select></th>
<th scope="col"><select id="{seletor_id}" onchange="filterTable()"><option value="">{seletor_label}</option></select></th>
<th scope="col"><select id="categoriaSelect" onchange="filterTable()"><option value="">Todas Categorias</option></select></th>
</tr>
</thead>
<tbody>
"""
        for _, row in data.iterrows():
            link = safe_str(row.get('LINK'), default='#')
            if not link.startswith(('http://', 'https://')):
                link = 'http://' + link

            nome = safe_str(row.get('NOME'), default='')
            uf = safe_str(row.get('UF'), default='')
            valor_quinta_coluna = safe_str(row.get(quinta_coluna_nome), default='')
            categoria = safe_str(row.get('CATEGORIA'), default='')
            conteudo_balao = safe_str(row.get('CONTEÚDO BALÃO'), default='')

            html += f"""
<tr class="organizationRow" data-uf="{uf}" data-{data_attr}="{valor_quinta_coluna}" data-categoria="{categoria}">
<td scope="row">
<span data-bs-placement="bottom" data-bs-toggle="tooltip" title="{conteudo_balao}">
<a href="{link}" rel="noopener noreferrer" target="_blank">{nome}</a>
</span>
</td>
<td>{uf}</td>
<td>{valor_quinta_coluna}</td>
<td>{categoria}</td>
</tr>
"""
        html += """
</tbody>
<script crossorigin="anonymous" integrity="sha384-I7E8VVD/ismYTF4hNIPjVp/Zjvgyol6VFvRkX/vR+Vc4jQkC+hVqc2pM8ODewa9r" src="https://cdn.jsdelivr.net/npm/@popperjs/core@2.11.8/dist/umd/popper.min.js"></script>
<script crossorigin="anonymous" integrity="sha384-BBtl+eGJRgqQAUMxJ7pMwbEyER4l1g+O15P+16Ep7Q9Q+zqX6gSbd85u4mG4QzX+" src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/js/bootstrap.min.js"></script>
<script src="https://code.jquery.com/jquery-3.6.0.min.js"></script>
<script>
    function populateSelects() {
        var ufSet = new Set();
        var cidadeSet = new Set();
        var categoriaSet = new Set();
        $("#organization_table tbody tr").each(function() {
            ufSet.add($(this).data("uf"));
            cidadeSet.add($(this).data("cidade"));
            categoriaSet.add($(this).data("categoria"));
        });
        
        // Ordena as opções de cada conjunto
        var ufArray = Array.from(ufSet).sort();
        var cidadeArray = Array.from(cidadeSet).sort();
        var categoriaArray = Array.from(categoriaSet).sort();

        // Adiciona as opções de estado ordenadas, ignorando vazios
        ufArray.forEach(function(uf) {
            if (uf) {
                $("#ufSelect").append(new Option(uf, uf));
            }
        });
        
        // Adiciona as opções de cidade ordenadas, ignorando vazios
        cidadeArray.forEach(function(cidade) {
            if (cidade) {
                $("#cidadeSelect").append(new Option(cidade, cidade));
            }
        });
        
        // Adiciona as opções de categoria ordenadas, ignorando vazios
        categoriaArray.forEach(function(categoria) {
            if (categoria) {
                $("#categoriaSelect").append(new Option(categoria, categoria));
            }
        });
    }

    function filterTable() {
        var ufFilter = $("#ufSelect").val().toLowerCase();
        var cidadeFilter = $("#cidadeSelect").val().toLowerCase();
        var categoriaFilter = $("#categoriaSelect").val().toLowerCase();
        
        $("#organization_table tbody tr").filter(function() {
            var ufText = $(this).data("uf").toLowerCase();
            var cidadeText = $(this).data("cidade").toLowerCase();
            var categoriaText = $(this).data("categoria").toLowerCase();
            
            if ((ufFilter === "" || ufText === ufFilter) &&
                (cidadeFilter === "" || cidadeText === cidadeFilter) &&
                (categoriaFilter === "" || categoriaText === categoriaFilter)) {
                $(this).show();
            } else {
                $(this).hide();
            }
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
</table>
"""
        return html

    # Gera a tabela HTML e calcula o total de organizações
    html_table = generate_html_table(data)
    total_organizacoes = len(data)

    # ESTA É A LINHA CORRIGIDA PARA O MARCADOR IMPORTANTE!
    html = f"""<!-- COMECA ATUALIZAR DAQUI -->
<div class="p-2 mr-2" id="count">
<p><b>Total de organizações:</b> {total_organizacoes}</p>
</div>
""" + html_table

    # Tenta criar o diretório de saída se não existir e salva o arquivo HTML
    try:
        if not os.path.exists(output_directory):
            os.makedirs(output_directory)
        output_path = os.path.join(output_directory, f"{aba}.html")
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html)
        print(f"Arquivo HTML '{output_path}' criado com sucesso.")
    except Exception as e:
        print(f"Erro ao escrever o arquivo HTML: {e}")

    # Tenta copiar o código HTML para a área de transferência
    try:
        pyperclip.copy(str(html))
        print("Código HTML copiado para a área de transferência.")
    except Exception as e:
        print(f"Erro ao copiar para área de transferência: {e}")

    return html

import os
import sys
import tkinter as tk
from tkinter import messagebox

# Os módulos do projeto ficam em src/. Isso os torna importáveis
# independentemente de onde o script é chamado.
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))

import pandas as pd
from criarHTML import processa_aba_gera_html
from atualizador_WP import atualizar_pagina_wp
from pitchs import gerar_html_pitchs_via_api
from criaHTMLPais import gerar_html_pais
from criarHTML_3col import gerar_html_3COL
import config

# Fonte dos links: usa o config.py (mesma fonte que a publicação automática).
# Antes lia de links_startups.xlsx, um arquivo que não existe no repositório —
# a interface quebrava logo ao abrir, com FileNotFoundError. Se o arquivo
# existir localmente, ele tem prioridade, para não mudar o fluxo de quem o usa.
ARQUIVO_LINKS = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             "links_startups.xlsx")

if os.path.exists(ARQUIVO_LINKS):
    links_df = pd.read_excel(ARQUIVO_LINKS)
    abas_links = dict(zip(links_df['ABA'], links_df['LINK']))
    print(f"Links carregados de {ARQUIVO_LINKS}")
else:
    abas_links = dict(config.ABAS_LINKS)
    print("Links carregados de src/config.py")

# Lista de abas que devem usar criaHTMLPais.py
abas_pais = [
    "ASSOCIAÇÕES EMPRESARIAIS",
    "FINANCIAMENTO A INOVAÇÃO",
    "HUBS E ECOSSISTEMAS",
    # CORRIGIDO: o nome antigo ("INSTITUTOS E GRUPOS DE PESQUISA") não batia com o nome
    # real da aba na planilha nem com a chave usada em links_startups.xlsx. A aba foi
    # renomeada para "INSTITUTOS DE PESQUISA E CENTROS DE T&I" — use esse nome também
    # na coluna ABA da planilha links_startups.xlsx.
    "INSTITUTOS DE PESQUISA E CENTROS DE T&I",
    "POLÍTICAS DE INOVAÇÃO",
    "PROPRIEDADE INTELECTUAL", "TESTE"
]

# Abas sem relação geográfica (Estado/Cidade/País): o filtro correspondente é
# removido inteiramente do HTML gerado para essas abas.
ABAS_SEM_GEOGRAFIA = [
    "PERIÓDICOS CIENTÍFICOS",
    "PROPRIEDADE INTELECTUAL",
    "POLÍTICAS DE INOVAÇÃO",
]

# Cria a janela principal
root = tk.Tk()
root.title("Atualizar Páginas de Startups")
root.geometry("550x600") # Janela mais larga

tk.Label(root, text="QUAIS ABAS DESEJA ATUALIZAR?", font=("Arial", 12)).pack(pady=10)

# Frame para conter os checkboxes
checkbox_frame = tk.Frame(root)
checkbox_frame.pack()

# Dicionário para armazenar variáveis de estado dos checkboxes
checkbox_vars = {}

# Número de colunas desejado
num_colunas = 2
abas = list(abas_links.keys())
num_linhas = (len(abas) + num_colunas - 1) // num_colunas

# Cria os checkboxes organizados em colunas
for i, aba in enumerate(abas):
    var = tk.BooleanVar()
    checkbox = tk.Checkbutton(checkbox_frame, text=aba, variable=var, anchor='w', width=25)
    checkbox.grid(row=i % num_linhas, column=i // num_linhas, sticky='w')
    checkbox_vars[aba] = var

def on_submit():
    selecionadas = [aba for aba, var in checkbox_vars.items() if var.get()]

    if not selecionadas:
        messagebox.showwarning("Aviso", "Selecione ao menos uma aba.")
        return

    erros = []
    for aba in selecionadas:
        try:
            print(f"\n➡️ Processando aba: {aba}")

            incluir_geografia = aba.strip().upper() not in [a.upper() for a in ABAS_SEM_GEOGRAFIA]

            if aba.strip().upper() == "PITCHS DE STARTUPS":
                print("Usando função: gerar_html_pitchs_via_api")
                html = gerar_html_pitchs_via_api()
            elif aba.strip().upper() == "VÍDEOS E PODCASTS":
                print("Usando função: gerar_html_simples (3 colunas)")
                html = gerar_html_3COL(aba)
            elif aba.upper() in [a.upper() for a in abas_pais]:
                print("Usando função: gerar_html_pais")
                html = gerar_html_pais(aba, incluir_geografia=incluir_geografia)
            else:
                print("Usando função: processa_aba_gera_html")
                html = processa_aba_gera_html(aba, incluir_geografia=incluir_geografia)

            if html is None:
                print(f"❌ HTML retornado como None para aba: {aba}")
                erros.append(f"{aba}: Erro ao gerar HTML.")
                continue

            print(f"✅ HTML gerado com sucesso ({len(html)} caracteres)")
            print("🔗 Link da página:", abas_links[aba])

            resposta = atualizar_pagina_wp(abas_links[aba], html)

            if resposta is not True:
                print(f"❌ Falha ao atualizar página: {abas_links[aba]}")
                erros.append(f"{aba}: Falha ao atualizar a página.")
            else:
                print(f"✅ Página atualizada com sucesso: {abas_links[aba]}")

        except Exception as e:
            erros.append(f"{aba}: {str(e)}")

    if not erros:
        messagebox.showinfo("Sucesso", "Todas as abas selecionadas foram atualizadas com sucesso.")
    else:
        mensagem = "Alguns erros ocorreram:\n" + "\n".join(erros)
        messagebox.showerror("Erros encontrados", mensagem)

# Botão de executar
tk.Button(root, text="Executar Selecionadas", command=on_submit).pack(pady=20)

root.mainloop()

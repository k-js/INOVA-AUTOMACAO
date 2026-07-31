import os
import sys
import json
import time

# O console do Windows costuma usar uma codificação legada (cp1252) que não
# consegue imprimir emoji nem acento, e derruba o script com
# UnicodeEncodeError. Força UTF-8 na saída antes de qualquer print.
for _fluxo in (sys.stdout, sys.stderr):
    try:
        _fluxo.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

# Os módulos do projeto ficam em src/. Isso os torna importáveis
# independentemente de onde o script é chamado.
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))

import rede  # noqa: F401  força IPv4 (runners do GitHub não têm IPv6)
import gspread
from google.oauth2.service_account import Credentials
from criarHTML import processa_aba_gera_html
from atualizador_WP import atualizar_pagina_wp
from pitchs import gerar_html_pitchs_via_api
from criaHTMLPais import gerar_html_pais
from criarHTML_3col import gerar_html_3COL
import config

# =========================================
# Configuração e Autenticação
# =========================================
google_json = os.environ.get("GOOGLE_JSON")
if not google_json:
    raise ValueError("❌ O secret GOOGLE_JSON não está definido!")

GSHEET_KEY = os.environ.get("GSHEETS_KEY")
if not GSHEET_KEY:
    raise ValueError("❌ O secret GSHEETS_KEY não está definido!")

print(f"🔑 ID da planilha: {GSHEET_KEY}")

try:
    # Carrega credenciais
    creds_dict = json.loads(google_json)
    
    # Define escopos
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive",
        "https://www.googleapis.com/auth/spreadsheets"
    ]
    
    # Autenticação correta
    creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
    client = gspread.authorize(creds)
    
    print("✅ Autenticação com Google Sheets realizada com sucesso!")
    
except Exception as e:
    raise Exception(f"❌ Erro na autenticação: {e}")

# =========================================
# Acesso à Planilha (com verificações)
# =========================================
def com_retentativa(descricao, funcao, tentativas=5, espera=45):
    """
    Executa uma chamada ao Google Sheets, repetindo quando a cota estoura.

    A API permite 60 leituras por minuto por usuário. Quando os passos
    anteriores do workflow (validação, backup) já consumiram parte da cota, a
    publicação começa recebendo HTTP 429. Como a cota se renova a cada minuto,
    esperar e repetir resolve — falhar de imediato só adia o trabalho para a
    execução seguinte.
    """
    for tentativa in range(1, tentativas + 1):
        try:
            return funcao()
        except gspread.exceptions.APIError as e:
            if "429" not in str(e) or tentativa == tentativas:
                raise
            print(f"⏳ Cota da API do Sheets atingida em '{descricao}'. "
                  f"Aguardando {espera}s (tentativa {tentativa}/{tentativas - 1})...")
            time.sleep(espera)


try:
    # Abre a planilha
    spreadsheet = com_retentativa(
        "abrir planilha", lambda: client.open_by_key(GSHEET_KEY)
    )
    print(f"✅ Planilha encontrada: {spreadsheet.title}")

    # Lista todas as worksheets disponíveis
    todas_worksheets = [
        ws.title for ws in com_retentativa(
            "listar abas", lambda: spreadsheet.worksheets()
        )
    ]
    print(f"📋 Worksheets disponíveis: {todas_worksheets}")

    # Verifica se a worksheet "CHECAR ABAS" existe
    if config.ABA_CONTROLE not in todas_worksheets:
        raise Exception(f"Worksheet '{config.ABA_CONTROLE}' não encontrada. "
                        f"Worksheets disponíveis: {todas_worksheets}")

    # Acessa a worksheet
    sheet = com_retentativa(
        "acessar CHECAR ABAS",
        lambda: spreadsheet.worksheet(config.ABA_CONTROLE),
    )
    print(f"✅ Worksheet '{config.ABA_CONTROLE}' acessada com sucesso!")

except gspread.exceptions.SpreadsheetNotFound:
    print("1. 🔗 A chave GSHEETS_KEY está correta?")
    print("2. 👥 A planilha foi compartilhada com o service account?")
    print(f"3. 📧 E-mail do service account: {creds_dict.get('client_email', '?')}")
    raise Exception("❌ Planilha não encontrada!")
except Exception as e:
    raise Exception(f"❌ Erro ao acessar planilha: {e}")

# =========================================
# Leitura das Abas Selecionadas
# =========================================
# ABAS_FORCADAS permite republicar abas sem depender do STATUS na planilha.
#
# Necessário porque a publicação marca as linhas como "ADICIONADO AO SITE" ao
# terminar: depois disso a aba some de CHECAR ABAS, e republicar exigiria
# marcar STATUS de novo, linha por linha. Quando a correção está no CÓDIGO
# (e não nos dados), isso é trabalho manual desnecessário.
#
# Uso: variável de ambiente com os nomes separados por vírgula.
#   ABAS_FORCADAS="POLÍTICAS DE INOVAÇÃO,PROPRIEDADE INTELECTUAL"
_forcadas = os.environ.get("ABAS_FORCADAS", "").strip()
abas_forcadas = [a.strip() for a in _forcadas.split(",") if a.strip()] if _forcadas else []

try:
    # Pega valores da coluna A a partir da linha 2
    abas_selecionadas = sheet.col_values(1)[1:]  # ignora a primeira linha (cabeçalho)
    abas_selecionadas = [aba.strip() for aba in abas_selecionadas if aba.strip()]

    if abas_forcadas:
        print(f"🔁 Abas forçadas por ABAS_FORCADAS: {abas_forcadas}")
        # Acrescenta sem duplicar as que já vieram de CHECAR ABAS.
        ja_listadas = {a.upper() for a in abas_selecionadas}
        for aba in abas_forcadas:
            if aba.upper() not in ja_listadas:
                abas_selecionadas.append(aba)

    print(f"✅ Abas que serão atualizadas: {abas_selecionadas}")

    if not abas_selecionadas:
        print("⚠️  Nenhuma aba selecionada para atualização!")
        print("   Marque STATUS na planilha e rode checarAbasComStatus, ou use")
        print("   ABAS_FORCADAS para republicar sem mexer no STATUS.")
        exit(0)

except Exception as e:
    raise Exception(f"❌ Erro ao ler abas selecionadas: {e}")

# =========================================
# Mapeamento de Links
# =========================================
# Fonte única: src/config.py. Antes este dicionário era repetido aqui e no
# config.py, e o de src/config.py alimentava validar.py e interface.py. Editar
# um e esquecer o outro fazia a publicação divergir da validação — a origem dos
# erros de "Link não mapeado".
abas_links = config.ABAS_LINKS

# Abas cuja coluna geográfica é PAÍS (e não CIDADE) — vem do config.py.
abas_pais = config.ABAS_PAIS

# Abas que não têm relação com Estado/Cidade/País (ex.: periódicos científicos,
# propriedade intelectual, políticas de inovação são temas nacionais/institucionais,
# não organizações localizáveis por UF/país). Para essas abas o filtro de
# Estado/Cidade/País é removido inteiramente do HTML gerado.
#
# CORRIGIDO: a lista local trazia "PERIÓDICOS CIENTÍFICOS" (acento no O), mas a
# aba na planilha se chama "PERÍODICOS CIENTÍFICOS" (acento no I). A comparação
# nunca batia, então o filtro geográfico continuava aparecendo nessa aba.
ABAS_SEM_GEOGRAFIA = config.ABAS_SEM_GEOGRAFIA

# =========================================
# Processamento em Lotes (com melhor tratamento de erros)
# =========================================
tamanho_lote = 5
erros = []
sucessos = []

for i in range(0, len(abas_selecionadas), tamanho_lote):
    lote = abas_selecionadas[i:i+tamanho_lote]
    print(f"\n➡️ Processando lote {i//tamanho_lote + 1}: {lote}")

    for aba in lote:
        try:
            print(f"\n🔄 Processando aba: {aba}")
            
            # Verifica se a aba existe no mapeamento
            if aba not in abas_links:
                print(f"❌ Aba '{aba}' não encontrada no mapeamento de links!")
                erros.append(f"{aba}: Link não mapeado")
                continue

            # Gera HTML baseado no tipo de aba
            incluir_geografia = aba.upper() not in [a.upper() for a in ABAS_SEM_GEOGRAFIA]

            if aba.upper() == "PITCHS DE STARTUPS":
                html = gerar_html_pitchs_via_api()
            elif aba.upper() == "VÍDEOS E PODCASTS":
                html = gerar_html_3COL(aba)
            elif aba.upper() in [a.upper() for a in abas_pais]:
                html = gerar_html_pais(aba, incluir_geografia=incluir_geografia)
            else:
                html = processa_aba_gera_html(aba, incluir_geografia=incluir_geografia)

            if html is None:
                print(f"❌ HTML retornado como None para aba: {aba}")
                erros.append(f"{aba}: Erro ao gerar HTML")
                continue

            # Atualiza página WordPress
            resposta = atualizar_pagina_wp(abas_links[aba], html)

            if not resposta:
                print(f"❌ Falha ao atualizar página: {abas_links[aba]}")
                erros.append(f"{aba}: Falha ao atualizar página WordPress")
            else:
                print(f"✅ Página atualizada com sucesso: {abas_links[aba]}")
                sucessos.append(aba)

        except Exception as e:
            error_msg = f"{aba}: {str(e)}"
            print(f"❌ Erro inesperado: {error_msg}")
            erros.append(error_msg)

    # Pausa entre lotes (se não for o último lote)
    if i + tamanho_lote < len(abas_selecionadas):
        print(f"\n⏱️  Pausa de 60 segundos antes do próximo lote...")
        time.sleep(60)

# =========================================
# Relatório Final
# =========================================
print(f"\n{'='*50}")
print("📊 RELATÓRIO DE EXECUÇÃO")
print(f"{'='*50}")
print(f"✅ Sucessos: {len(sucessos)}")
print(f"❌ Erros: {len(erros)}")
print(f"📋 Total processado: {len(abas_selecionadas)}")

if sucessos:
    print(f"\n✅ Abas atualizadas com sucesso: {sucessos}")

if erros:
    print(f"\n❌ Erros encontrados:")
    for e in erros:
        print(f"   - {e}")

if not erros:
    print("\n🎉 Todas as abas selecionadas foram atualizadas com sucesso!")
else:
    print(f"\n⚠️  {len(erros)} erro(s) ocorreram durante o processamento.")

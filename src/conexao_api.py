# -*- coding: utf-8 -*-
"""
Cliente autenticado do Google Sheets, compartilhado pelos geradores de HTML.

Uso:
    from conexao_api import client
    planilha = client.open(config.NOME_PLANILHA)
"""

import os
import json

import gspread
from google.oauth2.service_account import Credentials
from dotenv import load_dotenv

# Raiz do projeto (este arquivo está em src/).
RAIZ_PROJETO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Caminho absoluto: com caminho relativo, o .env só era encontrado quando o
# script rodava a partir da raiz do projeto.
load_dotenv(os.path.join(RAIZ_PROJETO, "credenciais", ".env"))

google_json = os.environ.get("GOOGLE_JSON")
if not google_json:
    raise ValueError(
        "❌ GOOGLE_JSON não está definido.\n"
        "   Na GitHub Action ele vem dos Secrets do repositório.\n"
        "   Localmente, crie credenciais/.env com a linha GOOGLE_JSON={...}"
    )

try:
    creds_dict = json.loads(google_json)
except json.JSONDecodeError as e:
    raise ValueError(
        f"❌ GOOGLE_JSON não é um JSON válido: {e}\n"
        "   O valor deve ser o conteúdo do arquivo da service account, em uma "
        "única linha. Use src/converter_json.py para gerá-lo."
    )

# MIGRADO de oauth2client (descontinuado desde 2018) para google-auth, que já
# era usado em main.py. O projeto tinha duas formas diferentes de autenticar.
ESCOPOS = [
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/spreadsheets",
]

creds = Credentials.from_service_account_info(creds_dict, scopes=ESCOPOS)

# Cliente pronto para uso pelos demais módulos.
client = gspread.authorize(creds)

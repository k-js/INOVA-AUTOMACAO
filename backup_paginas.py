# -*- coding: utf-8 -*-
"""
Salva o conteúdo atual das páginas antes de a publicação reescrevê-las.

O main.py substitui, em cada página, tudo entre o marcador
<!-- COMECA ATUALIZAR DAQUI --> e o </table> seguinte. Se o HTML gerado sair
errado, o conteúdo anterior se perde — e são páginas publicadas do site.

Este script guarda uma cópia antes. Rodado como passo da Action, o backup é
publicado como artefato e fica disponível para download.

Uso:
    python backup_paginas.py                       # todas as abas de CHECAR ABAS
    python backup_paginas.py --todas               # todas as abas de ABAS_LINKS
    python backup_paginas.py --listar
    python backup_paginas.py --restaurar backups/paginas-<data>/fintechs.json
"""

import os
import re
import sys
import json
import argparse
from datetime import datetime

for _fluxo in (sys.stdout, sys.stderr):
    try:
        _fluxo.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))

import rede  # noqa: F401  força IPv4 (runners do GitHub não têm IPv6)
import requests
from requests.auth import HTTPBasicAuth
from dotenv import load_dotenv
from urllib.parse import urlparse

import config

RAIZ = os.path.dirname(os.path.abspath(__file__))
DIR_BACKUPS = os.path.join(RAIZ, "backups")
load_dotenv(dotenv_path=os.path.join(RAIZ, "credenciais", ".env"))

API = "https://inova.ufpr.br/wp-json/wp/v2"
CABECALHOS = {"User-Agent": "Mozilla/5.0", "Content-Type": "application/json"}


def _auth():
    usuario = os.getenv("WP_USER")
    senha = os.getenv("WP_APP_PASSWORD")
    if not usuario or not senha:
        print("❌ WP_USER e WP_APP_PASSWORD não definidos.")
        sys.exit(1)
    return HTTPBasicAuth(usuario, senha)


def slug_da_url(url):
    """Último segmento do caminho da URL: o slug da página."""
    return urlparse(url).path.strip("/").split("/")[-1]


def abas_para_salvar(todas=False):
    """
    Quais abas terão a página salva.

    Por padrão, só as listadas em CHECAR ABAS — as que a publicação vai
    reescrever nesta execução. Salvar todas as 38 seria desperdício de tempo e
    de chamadas à API.
    """
    if todas:
        return sorted(config.ABAS_LINKS)

    google_json = os.environ.get("GOOGLE_JSON")
    gsheets_key = os.environ.get("GSHEETS_KEY")

    if not google_json or not gsheets_key:
        print("⚠️  Sem credenciais do Google; salvando todas as páginas mapeadas.")
        return sorted(config.ABAS_LINKS)

    import gspread
    from google.oauth2.service_account import Credentials

    escopos = [
        "https://www.googleapis.com/auth/drive",
        "https://www.googleapis.com/auth/spreadsheets",
    ]
    creds = Credentials.from_service_account_info(json.loads(google_json),
                                                  scopes=escopos)
    planilha = gspread.authorize(creds).open_by_key(gsheets_key)
    selecionadas = planilha.worksheet(config.ABA_CONTROLE).col_values(1)[1:]
    return [a.strip() for a in selecionadas if a.strip()]


def salvar(abas, pasta):
    """Salva o conteúdo bruto de cada página. Retorna quantas foram salvas."""
    os.makedirs(pasta, exist_ok=True)
    salvas = 0

    for aba in abas:
        url = config.ABAS_LINKS.get(aba)
        if not url:
            print(f"   ⏭️  {aba}: sem link mapeado")
            continue

        slug = slug_da_url(url)
        resposta = requests.get(
            f"{API}/pages",
            params={"slug": slug, "context": "edit"},
            auth=_auth(), headers=CABECALHOS, timeout=30,
        )

        if resposta.status_code != 200 or not resposta.json():
            print(f"   ⚠️  {aba}: página '{slug}' não encontrada")
            continue

        pagina = resposta.json()[0]
        conteudo = pagina.get("content", {}).get("raw", "")

        if not conteudo:
            print(f"   ⚠️  {aba}: conteúdo bruto vazio (permissão do usuário?)")
            continue

        caminho = os.path.join(pasta, f"{slug}.json")
        with open(caminho, "w", encoding="utf-8") as f:
            json.dump({
                "aba": aba,
                "slug": slug,
                "url": url,
                "pagina_id": pagina["id"],
                "salvo_em": datetime.now().isoformat(timespec="seconds"),
                "conteudo": conteudo,
            }, f, ensure_ascii=False, indent=1)

        print(f"   ✓ {aba}  ({len(conteudo)} chars)")
        salvas += 1

    return salvas


def restaurar(caminho, dry_run=False):
    """Devolve à página o conteúdo salvo em um backup."""
    with open(caminho, encoding="utf-8") as f:
        dados = json.load(f)

    if dry_run:
        return (f"restauraria '{dados['aba']}' ({dados['url']}) para o "
                f"conteúdo de {dados['salvo_em']}")

    resposta = requests.post(
        f"{API}/pages/{dados['pagina_id']}",
        auth=_auth(), headers=CABECALHOS,
        json={"content": dados["conteudo"]},
        timeout=30,
    )
    if resposta.status_code != 200:
        raise RuntimeError(f"falha ao restaurar (HTTP {resposta.status_code})")

    return f"'{dados['aba']}' restaurada para o estado de {dados['salvo_em']}"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--todas", action="store_true",
                        help="salva todas as páginas de ABAS_LINKS, e não só "
                             "as listadas em CHECAR ABAS")
    parser.add_argument("--listar", action="store_true",
                        help="lista os backups disponíveis e sai")
    parser.add_argument("--restaurar", metavar="ARQUIVO",
                        help="restaura uma página a partir de um backup")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if args.listar:
        if not os.path.isdir(DIR_BACKUPS):
            print("Nenhum backup salvo ainda.")
            return
        pastas = sorted((d for d in os.listdir(DIR_BACKUPS)
                         if d.startswith("paginas-")), reverse=True)
        if not pastas:
            print("Nenhum backup de páginas salvo ainda.")
            return
        print("Backups de páginas (mais recente primeiro):\n")
        for pasta in pastas:
            caminho = os.path.join(DIR_BACKUPS, pasta)
            arquivos = sorted(os.listdir(caminho))
            print(f"   backups/{pasta}/  ({len(arquivos)} páginas)")
            for a in arquivos:
                print(f"      {a}")
        return

    if args.restaurar:
        print(restaurar(args.restaurar, dry_run=args.dry_run))
        return

    print("=" * 64)
    print("💾 BACKUP DAS PÁGINAS ANTES DA PUBLICAÇÃO")
    print("=" * 64)

    abas = abas_para_salvar(todas=args.todas)
    if not abas:
        print("Nenhuma aba a salvar.")
        return

    print(f"{len(abas)} aba(s): {', '.join(abas)}\n")

    carimbo = datetime.now().strftime("%Y%m%d-%H%M%S")
    pasta = os.path.join(DIR_BACKUPS, f"paginas-{carimbo}")

    salvas = salvar(abas, pasta)

    print(f"\n💾 {salvas} página(s) salvas em backups/paginas-{carimbo}/")
    if salvas:
        print("\nPara desfazer uma delas:")
        print(f"   python backup_paginas.py --restaurar "
              f"backups/paginas-{carimbo}/<slug>.json")


if __name__ == "__main__":
    main()

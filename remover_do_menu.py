# -*- coding: utf-8 -*-
"""
Remove do menu do site os itens que apontam para páginas em rascunho.

Motivo: ao criar uma página como rascunho e já inseri-la no menu, o item pode
ficar VISÍVEL para o público mesmo com a página não publicada — depende do
tema. Quando isso acontece, o visitante clica e recebe 404.

Este script tira do menu os itens cujas páginas ainda não estão publicadas.
Quando a página for publicada, ela pode ser reinserida no menu.

Uso:
    python remover_do_menu.py --menu-id 7 --dry-run
    python remover_do_menu.py --menu-id 7
"""

import os
import sys
import argparse

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

RAIZ = os.path.dirname(os.path.abspath(__file__))
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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--menu-id", type=int, required=True)
    parser.add_argument("--dry-run", action="store_true",
                        help="mostra o que faria, sem remover nada")
    args = parser.parse_args()

    auth = _auth()

    resposta = requests.get(
        f"{API}/menu-items",
        params={"menus": args.menu_id, "per_page": 100},
        auth=auth, headers=CABECALHOS, timeout=30,
    )
    if resposta.status_code != 200:
        print(f"❌ Não consegui ler o menu {args.menu_id} (HTTP {resposta.status_code}).")
        sys.exit(1)

    itens = resposta.json()
    print(f"📋 {len(itens)} itens no menu {args.menu_id}")

    a_remover = []

    for item in itens:
        if item.get("object") != "page":
            continue

        pagina_id = item.get("object_id")
        pag = requests.get(
            f"{API}/pages/{pagina_id}",
            params={"context": "edit"},
            auth=auth, headers=CABECALHOS, timeout=30,
        )
        if pag.status_code != 200:
            continue

        dados = pag.json()
        if dados.get("status") != "publish":
            a_remover.append({
                "item_id": item["id"],
                "titulo": item.get("title", {}).get("rendered", "?"),
                "pagina_id": pagina_id,
                "status": dados.get("status"),
            })

    if not a_remover:
        print("\n✅ Nenhum item do menu aponta para página não publicada.")
        return

    print(f"\n⚠️  {len(a_remover)} item(ns) apontando para página NÃO publicada:")
    for r in a_remover:
        print(f"   - {r['titulo']}  (página {r['pagina_id']}, status: {r['status']})")

    if args.dry_run:
        print("\n(--dry-run: nada foi removido)")
        return

    print()
    for r in a_remover:
        # force=true: itens de menu não vão para a lixeira, são removidos direto.
        apagar = requests.delete(
            f"{API}/menu-items/{r['item_id']}",
            params={"force": "true"},
            auth=auth, headers=CABECALHOS, timeout=30,
        )
        if apagar.status_code in (200, 201):
            print(f"   ✓ removido do menu: {r['titulo']}")
        else:
            print(f"   ✗ falha em {r['titulo']} (HTTP {apagar.status_code})")

    print("\nAs páginas continuam existindo como rascunho — só saíram do menu.")
    print("Ao publicá-las, adicione-as ao menu novamente pelo painel do WordPress.")


if __name__ == "__main__":
    main()

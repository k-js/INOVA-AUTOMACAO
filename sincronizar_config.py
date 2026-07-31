# -*- coding: utf-8 -*-
"""
Mantém o src/config.py em sincronia com a planilha e com o site, sozinho.

Problema que resolve: quando alguém cria uma aba nova na planilha e a página
correspondente no WordPress, hoje é preciso editar o config.py à mão. Esquecer
esse passo faz a aba nunca ser publicada — em silêncio.

O que este script faz:

  1. Lê as abas reais da planilha (Google Sheets)
  2. Lê as páginas reais do site (API do WordPress)
  3. Casa uma coisa com a outra pelo nome, tolerando acento e caixa
  4. Reescreve ABAS_LINKS no src/config.py com o que descobriu

Quando roda na GitHub Action, o passo seguinte do workflow faz commit da
mudança — então o repositório se atualiza sozinho.

Modos de uso:

    python sincronizar_config.py            # aplica as mudanças no config.py
    python sincronizar_config.py --dry-run  # só mostra o que faria

Código de saída: 0 sempre que a sincronização em si funciona, mesmo que haja
abas sem página — essas viram aviso, não erro, para não bloquear a publicação
das demais.
"""

import os
import re
import sys
import json
import argparse

# Saída em UTF-8 antes de qualquer print (console legado do Windows derruba
# o script ao imprimir emoji/acento).
for _fluxo in (sys.stdout, sys.stderr):
    try:
        _fluxo.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))

import requests
import gspread
from google.oauth2.service_account import Credentials

import config
import criar_pagina_wp

CAMINHO_CONFIG = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              "src", "config.py")

SITE = "https://inova.ufpr.br"
API_PAGINAS = f"{SITE}/wp-json/wp/v2/pages"


# ---------------------------------------------------------------------
# Leitura das fontes
# ---------------------------------------------------------------------
def ler_abas_da_planilha():
    """Nomes das abas reais da planilha, na ordem em que aparecem."""
    google_json = os.environ.get("GOOGLE_JSON")
    gsheets_key = os.environ.get("GSHEETS_KEY")

    if not google_json or not gsheets_key:
        print("❌ GOOGLE_JSON e GSHEETS_KEY precisam estar definidos.")
        sys.exit(1)

    escopos = [
        "https://www.googleapis.com/auth/drive",
        "https://www.googleapis.com/auth/spreadsheets",
    ]
    creds = Credentials.from_service_account_info(json.loads(google_json),
                                                  scopes=escopos)
    planilha = gspread.authorize(creds).open_by_key(gsheets_key)
    return [ws.title for ws in planilha.worksheets()]


def ler_paginas_do_site():
    """
    Slugs das páginas publicadas no WordPress.

    Retorna {slug_normalizado: slug_real}. A API pagina em 100 por vez; o laço
    segue até acabar para não perder páginas se o site crescer.
    """
    paginas = {}
    pagina_atual = 1

    while True:
        resposta = requests.get(
            API_PAGINAS,
            params={"per_page": 100, "page": pagina_atual, "_fields": "slug"},
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=30,
        )
        if resposta.status_code != 200:
            break

        lote = resposta.json()
        if not lote:
            break

        for p in lote:
            slug = p.get("slug", "")
            if slug:
                paginas[config.normalizar(slug.replace("-", " "))] = slug

        total_paginas = int(resposta.headers.get("X-WP-TotalPages", 1))
        if pagina_atual >= total_paginas:
            break
        pagina_atual += 1

    return paginas


# ---------------------------------------------------------------------
# Casamento aba <-> página
# ---------------------------------------------------------------------
def procurar_pagina(nome_aba, paginas):
    """
    Acha o slug da página correspondente a uma aba, ou None.

    Testa as grafias mais prováveis. Não tenta adivinhar além disso: slugs como
    /biotechs/ para a aba DEEPTECHS ou /retailtechs-2/ para RETAILTECHS não são
    deriváveis do nome, e um palpite errado publicaria na página errada.
    """
    base = config.normalizar(nome_aba)

    candidatos = [
        base,                                    # "GAMETECHS"
        base.replace(" E ", " "),                # "LAWTECHS E LEGALTECHS"
        base.replace("TECHS", " TECHS").strip(),  # "PET TECHS"
    ]

    for candidato in candidatos:
        slug = paginas.get(candidato)
        if slug:
            return slug
    return None


# ---------------------------------------------------------------------
# Escrita do config.py
# ---------------------------------------------------------------------
def montar_bloco_abas_links(mapa):
    """Gera o texto do dicionário ABAS_LINKS, ordenado por nome de aba."""
    linhas = ["ABAS_LINKS = {"]
    for aba in sorted(mapa):
        linhas.append(f'    "{aba}": "{mapa[aba]}",')
    linhas.append("}")
    return "\n".join(linhas)


def reescrever_config(mapa):
    """
    Substitui o bloco ABAS_LINKS no src/config.py, preservando o resto do
    arquivo (comentários, demais constantes e funções).
    """
    with open(CAMINHO_CONFIG, encoding="utf-8") as f:
        texto = f.read()

    padrao = re.compile(r"^ABAS_LINKS = \{.*?^\}", re.S | re.M)
    if not padrao.search(texto):
        print("❌ Não encontrei o bloco ABAS_LINKS em src/config.py.")
        sys.exit(1)

    novo = padrao.sub(lambda _: montar_bloco_abas_links(mapa), texto, count=1)

    if novo == texto:
        return False

    with open(CAMINHO_CONFIG, "w", encoding="utf-8") as f:
        f.write(novo)
    return True


# ---------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true",
                        help="mostra o que faria, sem alterar nada")
    parser.add_argument("--criar-paginas", action="store_true",
                        help="cria no WordPress, como RASCUNHO, a página das "
                             "abas que ainda não têm uma")
    parser.add_argument("--publicar", metavar="ABA", nargs="+", default=None,
                        help="publica as páginas destas abas (só age sobre "
                             "páginas em rascunho). Use ABAS_AGUARDANDO_PAGINA "
                             "para publicar todas as que estão aguardando")
    parser.add_argument("--menu-id", type=int, default=None,
                        help="id do menu onde inserir as páginas criadas "
                             "(use --listar-menus para descobrir)")
    parser.add_argument("--listar-menus", action="store_true",
                        help="lista os menus de navegação do site e sai")
    args = parser.parse_args()

    if args.listar_menus:
        menus = criar_pagina_wp.listar_menus()
        if not menus:
            print("Nenhum menu acessível. Verifique WP_USER e WP_APP_PASSWORD,")
            print("e se o usuário tem permissão para gerenciar menus.")
            return
        print("Menus de navegação do site:\n")
        for m in menus:
            print(f"   id {m.get('id'):>4}   {m.get('name')}")
        print("\nUse: python sincronizar_config.py --criar-paginas --menu-id <id>")
        return

    if args.publicar is not None:
        # Atalho: publicar todas as que estão marcadas como aguardando.
        alvos = list(args.publicar)
        if len(alvos) == 1 and alvos[0].upper() == "ABAS_AGUARDANDO_PAGINA":
            alvos = sorted(getattr(config, "ABAS_AGUARDANDO_PAGINA", set()))

        if not alvos:
            print("Nenhuma aba a publicar.")
            return

        print("=" * 64)
        print("📤 PUBLICAÇÃO DE PÁGINAS")
        print("=" * 64)
        print(f"{len(alvos)} aba(s): {', '.join(alvos)}\n")

        publicadas = []
        for aba in alvos:
            try:
                url, situacao = criar_pagina_wp.publicar_pagina(
                    aba, dry_run=args.dry_run
                )
                marca = "✓" if url else "✗"
                print(f"   {marca} {aba}")
                print(f"     {situacao}")
                if url and "PUBLICADA" in situacao:
                    publicadas.append(aba)
            except Exception as e:
                print(f"   ✗ {aba}: {e}")

        if publicadas and not args.dry_run:
            print(f"\n✅ {len(publicadas)} página(s) publicada(s).")
            print("   Tire essas abas de ABAS_AGUARDANDO_PAGINA no src/config.py.")
        return

    print("=" * 64)
    print("🔄 SINCRONIZAÇÃO DO CONFIG")
    print("=" * 64)

    abas = ler_abas_da_planilha()
    print(f"📋 {len(abas)} abas na planilha")

    paginas = ler_paginas_do_site()
    print(f"🌐 {len(paginas)} páginas no site")

    if not paginas:
        print("❌ Não consegui ler as páginas do site. Nada foi alterado.")
        sys.exit(1)

    mapa = dict(config.ABAS_LINKS)
    novas = []
    sem_pagina = []

    for aba in abas:
        if aba in config.ABAS_IGNORADAS or aba in mapa:
            continue

        slug = procurar_pagina(aba, paginas)
        if slug:
            mapa[aba] = f"{SITE}/{slug}/"
            novas.append((aba, slug))
        else:
            sem_pagina.append(aba)

    # Abas que saíram da planilha continuam no config: removê-las
    # automaticamente apagaria a URL de uma aba renomeada, e a informação do
    # slug não é recuperável. O validador já sinaliza esse caso.
    sumiram = [a for a in mapa if a not in abas]

    print()
    if novas:
        print(f"✅ {len(novas)} aba(s) com página encontrada:")
        for aba, slug in novas:
            print(f"   + {aba}  →  {SITE}/{slug}/")
    else:
        print("Nenhuma aba nova com página correspondente.")

    if sem_pagina and args.criar_paginas:
        print(f"\n🆕 Criando página para {len(sem_pagina)} aba(s):")
        for aba in sem_pagina[:]:
            try:
                url, situacao = criar_pagina_wp.criar_pagina(aba, dry_run=args.dry_run)
                print(f"   + {aba}  →  {url}")
                print(f"     {situacao}")

                if args.menu_id:
                    msg = criar_pagina_wp.adicionar_ao_menu(
                        aba, args.menu_id, dry_run=args.dry_run
                    )
                    print(f"     menu: {msg}")

                if url and not args.dry_run:
                    mapa[aba] = url
                    novas.append((aba, url))
                    sem_pagina.remove(aba)

            except Exception as e:
                print(f"   ✗ {aba}: {e}")

        if not args.dry_run:
            print("\n   As páginas nasceram como RASCUNHO: já recebem conteúdo,")
            print("   mas só aparecem no site quando você clicar em Publicar.")

    elif sem_pagina:
        print(f"\n⚠️  {len(sem_pagina)} aba(s) sem página no site:")
        for aba in sem_pagina:
            sugestao = criar_pagina_wp.gerar_slug(aba)
            print(f"   - {aba}")
            print(f"     Crie a página (slug sugerido: /{sugestao}/) com o")
            print(f"     marcador <!-- COMECA ATUALIZAR DAQUI --> no conteúdo,")
            print(f"     ou rode com --criar-paginas para criá-la como rascunho.")

    if sumiram:
        print(f"\n⚠️  {len(sumiram)} aba(s) no config que não existem na planilha:")
        for aba in sumiram:
            print(f"   ? {aba}  (renomeada ou removida — confira manualmente)")

    if not novas:
        print("\nNada a atualizar em src/config.py.")
        return

    if args.dry_run:
        print("\n(--dry-run: nenhuma alteração gravada)")
        return

    if reescrever_config(mapa):
        print(f"\n✍️  src/config.py atualizado com {len(novas)} aba(s).")
    else:
        print("\nNada mudou em src/config.py.")


if __name__ == "__main__":
    main()

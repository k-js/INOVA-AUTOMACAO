# -*- coding: utf-8 -*-
"""
Sincroniza a grade de botões de /startups/ com as abas do config.py.

Problema que resolve: os botões dessa página são blocos escritos no conteúdo,
um a um. Toda aba nova exige editar a página à mão — e é por isso que hoje
faltam botões (FASHIONTECHS, GAMETECHS, INSURTECHS, TRAVELTECHS, RETAILTECHS).

Segurança:
  - O conteúdo atual é salvo em backups/ ANTES de qualquer escrita
  - As URLs dos botões existentes são preservadas como estão. Elas são
    inconsistentes (/home/agtechs/, /indtechs, /biotechs/) e reescrevê-las
    quebraria links que funcionam
  - Botões de páginas em rascunho não são adicionados: levariam a 404

Uso:
    python sincronizar_botoes.py --dry-run          # mostra o que faria
    python sincronizar_botoes.py                    # aplica
    python sincronizar_botoes.py --listar-backups
    python sincronizar_botoes.py --restaurar backups/startups-<data>.json
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

import config
import botoes_wp

# Página de índice e quais abas entram nela.
PAGINA_INDICE = "startups"

# Abas tratadas por este script.
#
# Escopo deliberadamente restrito às 4 abas novas. A página tem outras
# divergências (RETAILTECHS sem botão, PET TECHS vs PETTECHS, AGTECHS ignorada
# mas com botão) que estão registradas em docs/PENDENCIAS.md e devem ser
# resolvidas à parte — misturá-las aqui aumentaria o risco de uma mudança
# grande numa página publicada.
ABAS_ALVO = {
    "FASHIONTECHS",
    "GAMETECHS",
    "INSURTECHS",
    "TRAVELTECHS",
}


def pagina_publicada(url):
    """
    True se a URL aponta para uma página publicada.

    Evita criar botão para página em rascunho, que levaria o visitante a 404 —
    exatamente o que aconteceu ao inserir as 4 páginas novas no menu.
    """
    slug = url.rstrip("/").split("/")[-1]
    try:
        resposta = requests.get(
            f"{botoes_wp.API}/pages",
            params={"slug": slug},
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=20,
        )
        return resposta.status_code == 200 and bool(resposta.json())
    except Exception:
        return False


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true",
                        help="mostra o que faria, sem alterar a página")
    parser.add_argument("--pagina", default=PAGINA_INDICE,
                        help=f"slug da página de índice (padrão: {PAGINA_INDICE})")
    parser.add_argument("--listar-backups", action="store_true",
                        help="lista os backups disponíveis e sai")
    parser.add_argument("--restaurar", metavar="ARQUIVO",
                        help="restaura a página a partir de um backup")
    parser.add_argument("--incluir-rascunhos", action="store_true",
                        help="adiciona também botões de páginas em rascunho "
                             "(elas dão 404 até serem publicadas)")
    args = parser.parse_args()

    if args.listar_backups:
        backups = botoes_wp.listar_backups()
        if not backups:
            print("Nenhum backup salvo ainda.")
            return
        print("Backups disponíveis (mais recente primeiro):\n")
        for b in backups:
            print(f"   backups/{b}")
        print("\nPara desfazer:")
        print(f"   python sincronizar_botoes.py --restaurar backups/{backups[0]}")
        return

    if args.restaurar:
        print(botoes_wp.restaurar(args.restaurar, dry_run=args.dry_run))
        return

    print("=" * 64)
    print(f"🔘 SINCRONIZAÇÃO DOS BOTÕES DE /{args.pagina}/")
    print("=" * 64)

    pagina = botoes_wp.obter_pagina(args.pagina)
    if not pagina:
        print(f"❌ Página '{args.pagina}' não encontrada.")
        sys.exit(1)

    conteudo = pagina.get("content", {}).get("raw", "")
    existentes = botoes_wp.extrair_botoes(conteudo)
    print(f"📋 {len(existentes)} botões hoje na página")

    # Índice por nome normalizado, para casar botão com aba.
    por_nome = {botoes_wp._normalizar(r): (r, u) for r, u in existentes}

    botoes = list(existentes)
    adicionados = []
    pulados = []

    for aba in sorted(ABAS_ALVO):
        url = config.ABAS_LINKS.get(aba)
        if not url:
            print(f"   ! {aba} não está em ABAS_LINKS — pulando")
            continue
        if botoes_wp._normalizar(aba) in por_nome:
            continue

        if not args.incluir_rascunhos and not pagina_publicada(url):
            pulados.append(aba)
            continue

        botoes.append((aba, url))
        adicionados.append((aba, url))

    print()
    if adicionados:
        print(f"➕ {len(adicionados)} botão(ões) a acrescentar:")
        for rotulo, url in adicionados:
            print(f"   + {rotulo}  →  {url}")
    else:
        print("Nenhum botão novo a acrescentar.")

    if pulados:
        print(f"\n⏭️  {len(pulados)} aba(s) puladas (página não publicada):")
        for aba in pulados:
            print(f"   - {aba}")
        print("   Publique a página no WordPress e rode de novo.")

    if not adicionados:
        print("\nNada a fazer.")
        return

    print(f"\n🔤 A grade será reordenada alfabeticamente "
          f"({len(botoes)} botões no total).")

    mensagem, backup = botoes_wp.aplicar_botoes(
        args.pagina, botoes, dry_run=args.dry_run
    )
    print(f"\n{mensagem}")

    if not args.dry_run:
        print(f"💾 Backup do conteúdo anterior: {backup}")
        print(f"\nPara desfazer:")
        print(f"   python sincronizar_botoes.py --restaurar {backup}")


if __name__ == "__main__":
    main()

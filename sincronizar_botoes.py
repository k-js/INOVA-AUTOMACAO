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
        # line_buffering: fora de um terminal o Python segura a saída em
        # buffer, e o log da Action fica vazio até o processo terminar —
        # uma execução longa parece travada quando só está trabalhando.
        _fluxo.reconfigure(encoding="utf-8", errors="replace",
                           line_buffering=True)
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
# ⚠️ A grade de /startups/ NÃO espelha ABAS_LINKS, e não deve espelhar:
#
#   RETAILTECHS   é publicada e mapeada, mas fica FORA da grade — decisão de
#                 conteúdo, confirmada com a equipe em 13/08/2026.
#   AGTECHS       está na grade e NÃO é publicada por esta automação: a página
#                 dela leva a outro portfólio, alimentado por outra fonte.
#
# As duas são decisões, não falhas. Uma automação que igualasse as duas listas
# apagaria o botão da AGTECHS e criaria o da RETAILTECHS, desfazendo ambas —
# por isso a lista abaixo é explícita, e não derivada de ABAS_LINKS.
#
# As demais divergências (PET TECHS vs PETTECHS, prefixo /home/ nas URLs) estão
# em docs/PENDENCIAS.md e são tratadas à parte.
#
# A lista CRESCE a cada aba que ganha página. Ela não é "as abas novas desta
# vez": é o conjunto do que deve ter botão. Quem já tem é pulado sozinho, então
# manter os nomes antigos aqui não custa nada — e evita que a lista vire um
# registro de uma leva só, que foi o que aconteceu: ela ficou com as 4 de
# 30/07/2026 e não sabia das abas liberadas depois.
ABAS_ALVO = {
    "FASHIONTECHS",
    "GAMETECHS",
    "INSURTECHS",
    "TRAVELTECHS",
    # Liberada em 20/08/2026, a pedido do professor.
    "SECURITYTECHS",
    # PORTAIS DE NOTÍCIAS NÃO entra aqui: a página é de /portal-de-inovacao/,
    # não de /startups/ — portal de notícias não é startup. O botão dela vive
    # na grade do Portal de Inovação, que é editada à mão (não tem os
    # marcadores de automação, e a ordem lá é deliberada: STARTUPS vem primeiro).
    #
    # Se o nome voltar para esta lista, o botão reaparece em /startups/ na
    # execução seguinte, desfazendo a correção sem ninguém perceber.
}

# Correções de rótulo: {rótulo atual: rótulo correto}.
#
# Muda apenas o texto exibido no botão. A URL fica exatamente como está — a
# padronização de URLs é outro assunto, com riscos próprios (ver item 3 de
# docs/PENDENCIAS.md).
RENOMEAR_BOTOES = {
    # Na planilha a aba é PETTECHS, sem espaço.
    "PET TECHS": "PETTECHS",
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


def normalizar_urls(args):
    """
    Aponta cada botão direto para o destino final, sem redirecionamento.

    A grade acumulou caminhos que funcionam mas dão volta: onze botões usam o
    prefixo /home/, e três estão sem a barra final. O primeiro salto de cada um
    ainda passa por http:// antes de voltar para https://.

    Isto NÃO afeta quem já compartilhou uma URL antiga: o redirecionamento é do
    WordPress, e continua existindo. Só muda o destino de quem clica a partir
    desta página.

    O destino é perguntado ao site, não deduzido do rótulo — DEEPTECHS mora em
    /biotechs/ e HEALTHTECHS em /health-tech/, e deduzir daria errado.
    """
    print("=" * 64)
    print(f"🔗 URLS DOS BOTÕES DE /{args.pagina}/")
    print("=" * 64)

    pagina = botoes_wp.obter_pagina(args.pagina)
    if not pagina:
        print(f"❌ Página '{args.pagina}' não encontrada.")
        sys.exit(1)

    conteudo = pagina.get("content", {}).get("raw", "")
    if not conteudo:
        print("❌ não consegui ler o conteúdo bruto (verifique as permissões).")
        sys.exit(1)

    # Substituição cirúrgica de texto, e NÃO reconstrução da grade: o VOLTAR
    # usa <div class="wp-block-button"> sem a classe de largura, e remontar a
    # grade o reestilizaria para corrigir um redirecionamento. Assim ele entra
    # junto sem perder a aparência.
    novo, trocas = botoes_wp.normalizar_hrefs(conteudo)

    if not trocas:
        print("✅ Todos os endereços já apontam direto para o destino.")
        return

    curto = lambda u: u.replace("https://inova.ufpr.br", "")
    for antigo, canonico in trocas:
        print(f"   {curto(antigo):<38} -> {curto(canonico)}")

    problemas = botoes_wp.conferir_hrefs(conteudo, novo, trocas)
    if problemas:
        print(f"\n❌ não gravei: {'; '.join(problemas)}")
        sys.exit(1)

    print(f"\n{len(trocas)} endereço(s) a corrigir")
    if args.dry_run:
        print("(--dry-run: nada foi alterado)")
        return

    backup = botoes_wp.salvar_backup(args.pagina, pagina)
    resposta = botoes_wp.gravar_conteudo(pagina["id"], novo)
    if resposta != 200:
        print(f"\n❌ falha ao gravar (HTTP {resposta}). Backup: {backup}")
        sys.exit(1)

    print(f"\n✅ {len(trocas)} endereço(s) corrigido(s)")
    print(f"💾 Backup: {backup}")
    print("\nPara desfazer:")
    print(f"   python sincronizar_botoes.py --restaurar {backup}")


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
    parser.add_argument("--normalizar-urls", action="store_true",
                        help="aponta cada botão direto para o destino final, "
                             "sem passar por redirecionamento")
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

    if args.normalizar_urls:
        normalizar_urls(args)
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

    # Aplica as correções de rótulo, preservando a URL de cada botão.
    renomeados = []
    corrigidos = []
    for rotulo, url in existentes:
        novo_rotulo = RENOMEAR_BOTOES.get(rotulo.strip())
        if novo_rotulo:
            renomeados.append((rotulo.strip(), novo_rotulo, url))
            corrigidos.append((novo_rotulo, url))
        else:
            corrigidos.append((rotulo, url))

    existentes = corrigidos

    if renomeados:
        print(f"\n✏️  {len(renomeados)} rótulo(s) a corrigir:")
        for antigo, novo, url in renomeados:
            print(f"   {antigo}  →  {novo}")
            print(f"     URL mantida: {url}")

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

    if not adicionados and not renomeados:
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

# -*- coding: utf-8 -*-
"""
Move o botão de uma página de índice para outra, e ajusta o VOLTAR junto.

Nasceu de PORTAIS DE NOTÍCIAS: a página foi criada como categoria de startup e
não é uma — portal de notícias pertence ao Portal de Inovação, um nível acima.
Mover isso à mão são três edições em três páginas, e a terceira (o VOLTAR) é
justamente a que se esquece, porque não está na grade e sim no preâmbulo.

Por que não usa aplicar_botoes()
--------------------------------
Aquela função remonta a grade inteira: reordena tudo em ordem alfabética e
reescreve a marcação de cada botão. Em /startups/ tudo bem — a grade é gerada e
fica entre marcadores. Em /portal-de-inovacao/ não: ela foi feita à mão, não
tem marcadores, e a ordem é deliberada (STARTUPS vem primeiro, e não em ordem
alfabética). Remontar jogaria o STARTUPS para o meio da lista.

Aqui a edição é cirúrgica: um bloco entra ou sai, e o resto do conteúdo fica
byte a byte igual. O botão novo é um CLONE do vizinho, com endereço e texto
trocados — mesmo princípio de src/capa.py, copiar marcação que já funciona em
vez de adivinhar classes e estilos de uma página feita à mão.

Ordem das operações
-------------------
Acrescenta no destino ANTES de tirar da origem. Se algo falhar no meio, o botão
existe nas duas grades por um momento — feio, mas navegável. Na ordem inversa,
a falha deixaria a página inalcançável a partir de qualquer grade.

Uso:
    python mover_botao.py --dry-run
    python mover_botao.py
    python mover_botao.py --listar-backups
    python mover_botao.py --restaurar backups/<arquivo>.json
"""

import os
import sys
import argparse

for _fluxo in (sys.stdout, sys.stderr):
    try:
        _fluxo.reconfigure(encoding="utf-8", errors="replace",
                           line_buffering=True)
    except (AttributeError, ValueError):
        pass

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))

import rede  # noqa: F401  força IPv4 (runners do GitHub não têm IPv6)
import botoes_wp

SITE = botoes_wp.SITE

# Cada movimento é declarativo de propósito: quem ler daqui a um ano entende o
# que aconteceu sem precisar seguir o código.
MOVIMENTOS = [
    {
        "rotulo": "PORTAIS DE NOTÍCIAS",
        "de": "startups",
        "para": "portal-de-inovacao",
        # No destino a convenção de rótulo é outra: lá é "Aceleradoras e
        # Incubadoras", "Periódicos Científicos" — e não caixa alta.
        "rotulo_no_destino": "Portais de Notícias",
        # A grade do destino é alfabética depois do STARTUPS.
        "antes_de": "Propriedade Intelectual",
        "url": SITE + "/portais-de-noticias/",
        # A página que mudou de pai: o VOLTAR dela apontava para /startups/.
        "pagina_movida": "portais-de-noticias",
        "novo_voltar": SITE + "/portal-de-inovacao/",
    },
]


def _carregar(slug):
    """Página e conteúdo bruto, ou (None, None) com o motivo já impresso."""
    pagina = botoes_wp.obter_pagina(slug)
    if not pagina:
        print("   ❌ página '%s' não encontrada" % slug)
        return None, None

    conteudo = pagina.get("content", {}).get("raw", "")
    if not conteudo:
        print("   ❌ não li o conteúdo bruto de '%s' (permissões?)" % slug)
        return None, None

    return pagina, conteudo


def _gravar(slug, pagina, novo, dry_run):
    """Faz backup e grava. Devolve True se deu certo."""
    if dry_run:
        print("      (--dry-run: não gravei)")
        return True

    backup = botoes_wp.salvar_backup(slug, pagina)
    codigo = botoes_wp.gravar_conteudo(pagina["id"], novo)
    if codigo != 200:
        print("      ❌ falha ao gravar (HTTP %s). Backup: %s" % (codigo, backup))
        return False

    print("      ✅ gravado · backup: %s" % backup)
    return True


def mover(mov, dry_run=False):
    """Executa um movimento inteiro. Devolve True se tudo deu certo."""
    rotulo = mov["rotulo"]
    print("=" * 64)
    print("↔️  %s:  /%s/  ->  /%s/" % (rotulo, mov["de"], mov["para"]))
    print("=" * 64)

    # ---- 1. acrescenta no destino ----
    print("\n1. Acrescentar em /%s/" % mov["para"])
    pagina, conteudo = _carregar(mov["para"])
    if not pagina:
        return False

    ordem_antes = [b[4] for b in botoes_wp.listar_blocos_botao(conteudo)]
    print("   %d botão(ões) hoje · primeiro: %r" % (len(ordem_antes),
                                                    ordem_antes[0]))

    novo, problemas = botoes_wp.inserir_botao(
        conteudo, mov["rotulo_no_destino"], mov["url"], mov["antes_de"]
    )
    if problemas:
        if any("já tem um botão" in p for p in problemas):
            print("   ⏭️  já existe lá — nada a fazer")
        else:
            print("   ❌ %s" % "; ".join(problemas))
            return False
    else:
        ordem = [b[4] for b in botoes_wp.listar_blocos_botao(novo)]
        pos = ordem.index(mov["rotulo_no_destino"])
        print("   + %r na posição %d, antes de %r"
              % (mov["rotulo_no_destino"], pos, mov["antes_de"]))
        print("   ordem dos demais preservada · primeiro continua %r"
              % ordem[0])
        if not _gravar(mov["para"], pagina, novo, dry_run):
            return False

    # ---- 2. tira da origem ----
    print("\n2. Remover de /%s/" % mov["de"])
    pagina, conteudo = _carregar(mov["de"])
    if not pagina:
        return False

    novo, problemas = botoes_wp.remover_botao(conteudo, rotulo)
    if problemas:
        if any("não achei" in p for p in problemas):
            print("   ⏭️  já não está lá — nada a fazer")
        else:
            print("   ❌ %s" % "; ".join(problemas))
            return False
    else:
        print("   - %r removido (%d chars a menos)"
              % (rotulo, len(conteudo) - len(novo)))
        if not _gravar(mov["de"], pagina, novo, dry_run):
            return False

    # ---- 3. o VOLTAR da página que mudou de pai ----
    print("\n3. VOLTAR de /%s/" % mov["pagina_movida"])
    pagina, conteudo = _carregar(mov["pagina_movida"])
    if not pagina:
        return False

    novo, anterior, problemas = botoes_wp.trocar_voltar(conteudo,
                                                        mov["novo_voltar"])
    if problemas:
        print("   ❌ %s" % "; ".join(problemas))
        return False

    if novo is None:
        print("   ⏭️  já aponta para %s — nada a fazer" % anterior)
        return True

    print("   %s  ->  %s" % (anterior, mov["novo_voltar"]))
    return _gravar(mov["pagina_movida"], pagina, novo, dry_run)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true",
                        help="mostra o que faria, sem alterar nada")
    parser.add_argument("--listar-backups", action="store_true",
                        help="lista os backups disponíveis e sai")
    parser.add_argument("--restaurar", metavar="ARQUIVO",
                        help="devolve a uma página o conteúdo de um backup")
    args = parser.parse_args()

    if args.listar_backups:
        backups = botoes_wp.listar_backups()
        if not backups:
            print("Nenhum backup salvo ainda.")
            return
        print("Backups (mais recente primeiro):\n")
        for b in backups[:20]:
            print("   backups/%s" % b)
        return

    if args.restaurar:
        print(botoes_wp.restaurar(args.restaurar, dry_run=args.dry_run))
        return

    if args.dry_run:
        print("(--dry-run: nada será alterado)\n")

    falhas = 0
    for mov in MOVIMENTOS:
        if not mover(mov, dry_run=args.dry_run):
            falhas += 1
        print()

    if falhas:
        print("❌ %d movimento(s) com problema. "
              "Para desfazer: python mover_botao.py --listar-backups" % falhas)
        sys.exit(1)

    print("✅ Tudo certo.")
    if not args.dry_run:
        print("\nPara desfazer: python mover_botao.py --listar-backups")


if __name__ == "__main__":
    main()

# -*- coding: utf-8 -*-
"""
O preâmbulo das páginas: tudo que vem ANTES do marcador de publicação.

A publicação diária só reescreve do marcador <!-- COMECA ATUALIZAR DAQUI -->
até a última </table>. O que está antes disso nunca é tocado por ela — e é
justamente onde moram o CSS que centraliza as colunas, o campo de busca, o
botão VOLTAR e a imagem de capa.

O preâmbulo mistura duas naturezas bem diferentes:

    ESTRUTURA   igual em todas as páginas
                os blocos <style>, o botão VOLTAR e a abertura de
                <body>/<div> com o campo "Busque por uma organização"

    CONTEÚDO    de cada página
                o bloco wp:cover, com a imagem de capa e o título

Só a ESTRUTURA pode ser copiada de uma página para outra. Levar o conteúdo
junto põe a capa de uma página em todas as demais.

Este módulo é compartilhado por dois scripts, para que não se afastem:

    src/criar_pagina_wp.py   página nova já nasce com o preâmbulo certo
    corrigir_preambulo.py    conserta as páginas que estão erradas
"""

import re

MARCADOR = "<!-- COMECA ATUALIZAR DAQUI -->"

# Página cujo preâmbulo serve de referência para as demais.
ABA_MODELO = "INDTECHS"


def partir_conteudo(conteudo):
    """
    Divide o conteúdo da página em (preâmbulo, bloco, sufixo).

    preâmbulo  antes do marcador — CSS, campo de busca, botão VOLTAR, capa
    bloco      do marcador até o fim da ÚLTIMA </table> — a tabela
    sufixo     o que vem depois — fechamento das tags e os <script> de filtro

    Retorna None se a página não tiver o marcador.
    """
    i = conteudo.find(MARCADOR)
    if i == -1:
        return None

    fim_tabela = conteudo.rfind("</table>")
    if fim_tabela == -1 or fim_tabela < i:
        return None
    fim_tabela += len("</table>")

    return conteudo[:i], conteudo[i:fim_tabela], conteudo[fim_tabela:]


def tem_preambulo(conteudo):
    """True se há o campo de busca e o CSS que centraliza as colunas."""
    tem_busca = 'id="search"' in conteudo
    tem_css = re.search(r'#organization_table\s+td:nth-child\(\d\)\s*\{[^}]*'
                        r'text-align:\s*center', conteudo, re.S) is not None
    return tem_busca and tem_css


def conteudo_do_preambulo(preambulo):
    """
    O conteúdo editorial que vive no preâmbulo: capa e texto de apresentação.

    Retorna (imagens, texto). Ambos vazios quando só há estrutura.
    """
    corpo = re.sub(r"<head>.*?</head>", "", preambulo, flags=re.S | re.I)
    corpo = re.sub(r"<style>.*?</style>", "", corpo, flags=re.S | re.I)
    corpo = re.sub(r"<input\b[^>]*>", "", corpo, flags=re.I)

    imagens = tuple(re.findall(r"<img\b[^>]*?src=[\"']([^\"']+)[\"']", corpo, re.I))
    texto = re.sub(r"<[^>]+>", " ", corpo).replace("&nbsp;", " ")
    texto = re.sub(r"\s+", " ", texto).strip()

    return imagens, texto


def texto_editorial(preambulo):
    """
    O texto de apresentação do preâmbulo, sem o rótulo do botão VOLTAR.

    VOLTAR é navegação, igual em todas as páginas; a descrição do setor é
    conteúdo de cada uma. Separar os dois é o que permite copiar a estrutura
    sem levar a descrição junto.
    """
    _, texto = conteudo_do_preambulo(preambulo)
    return re.sub(r"\bVOLTAR\b", "", texto, flags=re.I).strip()


def descrever_conteudo(preambulo):
    """Lista legível do que há de editorial no preâmbulo (vazia se não houver)."""
    imagens, _ = conteudo_do_preambulo(preambulo)
    texto = texto_editorial(preambulo)
    achados = []
    if imagens:
        achados.append(f"{len(imagens)} imagem(ns)")
    if texto:
        achados.append(f"descrição ({texto[:60]!r})")
    return achados


def _remover_bloco(preambulo, nome, so_com_texto=False):
    """
    Tira do preâmbulo os blocos <!-- wp:nome --> ... <!-- /wp:nome -->.

    Com so_com_texto, preserva os blocos vazios — parágrafos vazios são
    espaçadores de layout, não conteúdo.
    """
    padrao = rf"<!--\s*wp:{nome}\b.*?<!--\s*/wp:{nome}\s*-->\s*"

    def descartar(casamento):
        if not so_com_texto:
            return ""
        texto = re.sub(r"<[^>]+>", " ", casamento.group(0))
        return "" if texto.strip() else casamento.group(0)

    return re.sub(padrao, descartar, preambulo, flags=re.S | re.I)


def preambulo_estrutural(preambulo):
    """
    O preâmbulo do modelo sem o que é conteúdo daquela página.

    Sai:  wp:cover      a imagem de capa e o título
          wp:paragraph  a descrição do setor (os vazios ficam, são espaçadores)
          wp:heading    títulos soltos

    Fica: os <style>, o botão VOLTAR e a abertura de <body>/<div> com o campo
          de busca — iguais em todas as páginas.

    A remoção é cirúrgica, e não uma remontagem por lista de permissão: a
    estrutura exata importa (são blocos do Gutenberg, e os <style> estão
    espalhados em mais de um <head>), e tentar remontá-la já derrubou o CSS da
    tabela uma vez. Confira o resultado com conferir_preambulo() antes de usar.
    """
    limpo = _remover_bloco(preambulo, "cover")
    limpo = _remover_bloco(limpo, "paragraph", so_com_texto=True)
    limpo = _remover_bloco(limpo, "heading", so_com_texto=True)
    return _remover_texto_solto(limpo)


def _remover_texto_solto(preambulo):
    """
    Rede de segurança: tira <p> e <h1>–<h6> com texto que sobraram.

    Nem todo conteúdo do WordPress está embrulhado em comentários de bloco —
    páginas antigas, ou trechos editados no modo HTML, guardam parágrafos
    soltos. Sem isto, a descrição do modelo escapa da limpeza.

    O botão VOLTAR não é afetado: ele mora num <a> dentro do bloco de botões,
    não num parágrafo. Elementos vazios ficam, são espaçadores de layout.
    """
    def descartar(casamento):
        texto = re.sub(r"<[^>]+>", " ", casamento.group(0)).replace("&nbsp;", " ")
        return "" if texto.strip() else casamento.group(0)

    return re.sub(r"<(p|h[1-6])\b[^>]*>.*?</\1>\s*", descartar,
                  preambulo, flags=re.S | re.I)


def conferir_preambulo(preambulo):
    """
    Confere o preâmbulo pronto antes de gravar. Lista os problemas achados.

    Três coisas já foram para o site erradas daqui: a capa do modelo em todas
    as páginas, o CSS da tabela sumindo numa remontagem, e a descrição do
    modelo sobrevivendo à remoção da capa. Cada uma virou uma checagem — melhor
    abortar do que descobrir depois, olhando o site.
    """
    problemas = []

    if not tem_preambulo(preambulo):
        problemas.append("o CSS de centralização ou o campo de busca não "
                         "sobreviveram à limpeza")

    imagens, _ = conteudo_do_preambulo(preambulo)
    if imagens:
        problemas.append(f"a capa do modelo continua aqui: {imagens[0][:80]}")

    texto = texto_editorial(preambulo)
    if texto:
        problemas.append(f"a descrição do modelo continua aqui: {texto[:70]!r}")

    return problemas


def herdou_do_modelo(preambulo_pagina, preambulo_modelo):
    """
    True se a página está exibindo a capa OU a descrição da página modelo.

    Serve para desfazer a cópia indevida sem tocar nas páginas que têm capa e
    descrição próprias: só reconhece o que for idêntico ao do modelo.

    As duas metades são testadas em separado de propósito. Uma correção antiga
    tirou a capa e deixou a descrição para trás — e um teste que exigisse as
    duas iguais não teria reconhecido essas páginas para consertá-las.
    """
    imagens_pagina, _ = conteudo_do_preambulo(preambulo_pagina)
    imagens_modelo, _ = conteudo_do_preambulo(preambulo_modelo)
    if imagens_pagina and imagens_pagina == imagens_modelo:
        return True

    # Contenção, e não igualdade: uma página pode ter ficado com só um pedaço
    # do que veio do modelo — foi o caso das que perderam a capa e mantiveram
    # a descrição. O mínimo de caracteres evita casar por acaso.
    texto_pagina = texto_editorial(preambulo_pagina)
    texto_modelo = texto_editorial(preambulo_modelo)
    if len(texto_pagina) < 20 or not texto_modelo:
        return False
    return texto_pagina in texto_modelo


_VOLTAR = re.compile(r'(<a[^>]*href=")([^"]*)("[^>]*>(?:<strong>)?\s*VOLTAR)',
                     re.I)


def destino_do_voltar(preambulo):
    """Para onde o botão VOLTAR desta página aponta, ou None."""
    achado = _VOLTAR.search(preambulo or "")
    return achado.group(2) if achado else None


def preservar_voltar(preambulo_novo, preambulo_atual):
    """
    Mantém, no preâmbulo novo, o destino de VOLTAR que a página já tinha.

    O preâmbulo do modelo traz o VOLTAR DELE, e por muito tempo isso não fez
    diferença: toda página de categoria era filha de /startups/, então copiar o
    modelo acertava por coincidência.

    Deixou de acertar em 20/08/2026, quando PORTAIS DE NOTÍCIAS passou de
    /startups/ para /portal-de-inovacao/. Aplicar o modelo mandaria o visitante
    de volta ao pai errado — e pior, em silêncio, porque a página continuaria
    parecendo certa.

    Preservar o que a página tem é melhor que uma lista de exceções: não há o
    que alguém esquecer de atualizar na próxima página que mudar de lugar.

    Devolve (preambulo, destino_preservado_ou_None).
    """
    atual = destino_do_voltar(preambulo_atual)
    if not atual:
        return preambulo_novo, None

    do_modelo = destino_do_voltar(preambulo_novo)
    if do_modelo is None or do_modelo == atual:
        return preambulo_novo, None

    novo = _VOLTAR.sub(lambda m: m.group(1) + atual + m.group(3),
                       preambulo_novo, count=1)

    # Se a troca não pegou, é melhor não gravar do que gravar o destino errado.
    if destino_do_voltar(novo) != atual:
        return preambulo_novo, None

    return novo, atual

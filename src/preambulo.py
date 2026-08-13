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


def descrever_conteudo(preambulo):
    """Lista legível do que há de editorial no preâmbulo (vazia se não houver)."""
    imagens, texto = conteudo_do_preambulo(preambulo)
    achados = []
    if imagens:
        achados.append(f"{len(imagens)} imagem(ns)")
    if texto:
        achados.append(f"texto ({texto[:60]!r})")
    return achados


def preambulo_estrutural(preambulo):
    """
    O preâmbulo do modelo sem a capa — tudo o mais é mantido como está.

    Do preâmbulo, só o bloco de capa (wp:cover, com a imagem e o título) é
    conteúdo daquela página. Os <style>, o botão VOLTAR e a abertura de
    <body>/<div> com o campo de busca são iguais em todas e ficam.

    A remoção é cirúrgica, e não uma remontagem por lista de permissão: a
    estrutura exata importa (são blocos do Gutenberg, e os <style> estão
    espalhados em mais de um <head>), e tentar remontá-la já derrubou o CSS da
    tabela uma vez. Confira o resultado com conferir_preambulo() antes de usar.
    """
    return re.sub(r"<!--\s*wp:cover\b.*?<!--\s*/wp:cover\s*-->\s*", "",
                  preambulo, flags=re.S | re.I)


def conferir_preambulo(preambulo):
    """
    Confere o preâmbulo pronto antes de gravar. Lista os problemas achados.

    Duas coisas já foram para o site erradas daqui: a capa do modelo em todas
    as páginas, e o CSS da tabela sumindo numa remontagem. Cada uma virou uma
    checagem — melhor abortar do que descobrir depois, olhando o site.
    """
    problemas = []

    if not tem_preambulo(preambulo):
        problemas.append("o CSS de centralização ou o campo de busca não "
                         "sobreviveram à limpeza")

    imagens, _ = conteudo_do_preambulo(preambulo)
    if imagens:
        problemas.append(f"a capa do modelo continua aqui: {imagens[0][:80]}")

    return problemas


def herdou_do_modelo(preambulo_pagina, preambulo_modelo):
    """
    True se a página está exibindo a capa e o texto da página modelo.

    Serve para desfazer a cópia indevida sem tocar nas páginas que têm capa e
    descrição próprias: só reconhece quando o conteúdo é idêntico ao do modelo.
    """
    da_pagina = conteudo_do_preambulo(preambulo_pagina)
    if da_pagina == ((), ""):
        return False
    return da_pagina == conteudo_do_preambulo(preambulo_modelo)

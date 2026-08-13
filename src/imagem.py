# -*- coding: utf-8 -*-
"""
Padroniza a imagem de capa: recorte 3:1, até 2400×800, sem ampliar.

O bloco wp:cover das páginas usa min-height de 300px e deixa o navegador
recortar. Como as capas atuais vão de 1.5 a 3.49 de proporção, cada página
recorta de um jeito — e a FINTECHS, com 293px de altura, é esticada.

A proporção é o que de fato padroniza; a resolução é um teto:

    proporção   3:1, sempre
    resolução   até 2400×800, NUNCA ampliando

2400px é o dobro da coluna de conteúdo (~1200px), para telas retina, e fica
abaixo dos 2560px em que o WordPress reescala o arquivo sozinho. Quem não tem
pixel suficiente fica no máximo que couber, em 3:1 — o recorte melhora mesmo
assim, porque corrige a proporção.
"""

import io

PROPORCAO = 3.0
LARGURA_ALVO = 2400
QUALIDADE = 85

# Altura mínima do bloco de capa. Abaixo disso a imagem é esticada pelo
# navegador, que é o defeito que a FINTECHS tem hoje.
ALTURA_MINIMA_UTIL = 300


def maior_recorte(largura, altura, proporcao=PROPORCAO):
    """Maior recorte na proporção pedida que cabe na imagem. Devolve (l, a)."""
    if largura <= 0 or altura <= 0:
        return 0, 0
    if largura / altura >= proporcao:
        return int(altura * proporcao), altura      # sobra largura: corta nas laterais
    return largura, int(largura / proporcao)        # sobra altura: corta em cima/embaixo


def avaliar(largura, altura, largura_alvo=LARGURA_ALVO):
    """
    O que dá para fazer com uma imagem desse tamanho, sem ampliar.

    Devolve (largura_final, altura_final, aviso). aviso é None quando o
    resultado atinge o alvo cheio.
    """
    corte_l, corte_a = maior_recorte(largura, altura)
    if corte_l == 0:
        return 0, 0, "não consegui ler as dimensões"

    final_l = min(corte_l, largura_alvo)
    final_a = round(final_l / PROPORCAO)

    if final_a < ALTURA_MINIMA_UTIL:
        return final_l, final_a, (
            f"pequena demais: {final_l}x{final_a} fica abaixo dos "
            f"{ALTURA_MINIMA_UTIL}px do bloco e seria esticada"
        )
    if final_l < largura_alvo:
        return final_l, final_a, f"abaixo do alvo: máximo sem ampliar é {final_l}x{final_a}"
    return final_l, final_a, None


def padronizar(dados, largura_alvo=LARGURA_ALVO):
    """
    Recorta e recomprime a imagem. Devolve (bytes_jpeg, largura, altura).

    O recorte é central e determinístico — sempre dá o mesmo resultado para a
    mesma entrada, o que torna a operação auditável e repetível.

    O EXIF é descartado: tira geolocalização e dados de câmera, e reduz o
    arquivo. A orientação gravada no EXIF é aplicada ANTES de descartá-lo, para
    a foto não sair deitada.
    """
    from PIL import Image, ImageOps

    imagem = Image.open(io.BytesIO(dados))
    imagem = ImageOps.exif_transpose(imagem)
    if imagem.mode != "RGB":
        imagem = imagem.convert("RGB")

    largura, altura = imagem.size
    corte_l, corte_a = maior_recorte(largura, altura)
    esquerda = (largura - corte_l) // 2
    topo = (altura - corte_a) // 2
    imagem = imagem.crop((esquerda, topo, esquerda + corte_l, topo + corte_a))

    # Só reduz. Ampliar deixaria a imagem borrada — melhor uma capa menor e
    # nítida do que uma grande e mole.
    if imagem.width > largura_alvo:
        imagem = imagem.resize(
            (largura_alvo, round(largura_alvo / PROPORCAO)), Image.LANCZOS
        )

    saida = io.BytesIO()
    imagem.save(saida, "JPEG", quality=QUALIDADE, optimize=True, progressive=True)
    return saida.getvalue(), imagem.width, imagem.height


def saturacao_media(dados, lado=256):
    """
    Saturação média da imagem, de 0 a 255. Zero é preto e branco.

    Serve para recusar fotos dessaturadas: uma capa em preto e branco no meio
    de 36 coloridas destoa, e isso nenhuma medida de semelhança semântica pega
    — o CLIP achou ótima a foto em P&B escolhida para GAMETECHS.

    A imagem é reduzida antes da conta: a média não muda de forma relevante e
    o cálculo fica instantâneo.
    """
    from PIL import Image

    imagem = Image.open(io.BytesIO(dados))
    if imagem.mode != "RGB":
        imagem = imagem.convert("RGB")
    imagem.thumbnail((lado, lado))

    canal_s = imagem.convert("HSV").getchannel("S")
    histograma = canal_s.histogram()
    total = sum(histograma)
    if not total:
        return 0.0
    return sum(valor * n for valor, n in enumerate(histograma)) / total


def nome_do_arquivo(slug):
    """Nome previsível, ao contrário do acervo atual."""
    return f"capa-{slug}.jpg"

# -*- coding: utf-8 -*-
"""
Analisa os pixels da imagem antes de ela virar capa.

Os modelos que a chave da Groq alcança são todos de texto — nenhum enxerga
imagem. Então a análise roda AQUI, dentro do próprio Action: sem chave, sem
cota, sem custo. E, ao contrário de julgar pela legenda que o banco de imagens
fornece, isto olha a foto.

São três verificações, com papéis diferentes:

    CLIP        mede o quanto a imagem corresponde ao termo buscado, e o
                quanto ela parece marca d'água / colagem / captura de tela.
                É o que ordena as candidatas.

    rostos      detecta pessoas identificáveis. Não reprova sozinho, mas
                desempata a favor de quem não tem: a licença do Pexels
                restringe o uso de pessoas reconhecíveis, e uma escolha
                automática erra mais feio quando há gente na foto.

    NSFW        reprova conteúdo adulto. É uma rede de segurança, não uma
                garantia — classificadores erram.

O que isto NÃO faz: julgar bom gosto. CLIP mede semelhança semântica. Uma foto
datada, clichê ou que destoe das outras 33 capas passa por aqui sem alarme.

As dependências (torch, transformers, opencv) são pesadas e ficam num
requirements próprio, instalado só no workflow das capas — a publicação diária
não carrega esse peso.
"""

import io

MODELO_CLIP = "openai/clip-vit-base-patch32"
MODELO_NSFW = "Falconsai/nsfw_image_detection"

# Acima disto a imagem é reprovada por conteúdo adulto.
LIMITE_NSFW = 0.30

# Abaixo disto a imagem não tem relação suficiente com o termo buscado.
# Pontuação do CLIP é relativa: serve para ordenar, e como piso grosseiro.
RELEVANCIA_MINIMA = 0.15

# Termos negativos: o que atrapalha uma capa mesmo sendo "relevante".
RUIDOS = [
    "a watermark or stock photo logo over the image",
    "a screenshot of a computer interface",
    "a collage of several photos",
    "a plain text banner",
]

_modelos = {}


def disponivel():
    """True se as dependências de visão estão instaladas."""
    try:
        import torch  # noqa: F401
        import transformers  # noqa: F401
        import cv2  # noqa: F401
        return True
    except ImportError:
        return False


def _carregar():
    """Carrega os modelos uma vez só — cada carga custa segundos."""
    if _modelos:
        return _modelos
    from transformers import CLIPModel, CLIPProcessor, pipeline
    _modelos["clip"] = CLIPModel.from_pretrained(MODELO_CLIP)
    _modelos["clip_proc"] = CLIPProcessor.from_pretrained(MODELO_CLIP)
    _modelos["nsfw"] = pipeline("image-classification", model=MODELO_NSFW)
    return _modelos


def _imagem(dados):
    from PIL import Image
    return Image.open(io.BytesIO(dados)).convert("RGB")


def contar_rostos(dados):
    """Quantos rostos frontais a imagem tem. Aproximado, mas barato."""
    import cv2
    import numpy as np

    matriz = cv2.imdecode(np.frombuffer(dados, np.uint8), cv2.IMREAD_COLOR)
    if matriz is None:
        return 0
    cinza = cv2.cvtColor(matriz, cv2.COLOR_BGR2GRAY)
    detector = cv2.CascadeClassifier(
        cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    )
    return len(detector.detectMultiScale(cinza, scaleFactor=1.1, minNeighbors=6,
                                         minSize=(60, 60)))


def pontuar_nsfw(dados):
    """Probabilidade de conteúdo adulto, de 0 a 1."""
    modelos = _carregar()
    for item in modelos["nsfw"](_imagem(dados)):
        if item["label"].lower().startswith("nsfw"):
            return float(item["score"])
    return 0.0


def pontuar_relevancia(dados, consulta):
    """
    O quanto a imagem corresponde à consulta, descontando ruído visual.

    A consulta disputa com os termos de RUIDOS no mesmo softmax: uma captura
    de tela com marca d'água perde para si mesma, ainda que o assunto bata.
    """
    import torch

    modelos = _carregar()
    textos = [f"a photo of {consulta}"] + RUIDOS
    entradas = modelos["clip_proc"](
        text=textos, images=_imagem(dados), return_tensors="pt",
        padding=True, truncation=True,
    )
    with torch.no_grad():
        saida = modelos["clip"](**entradas)
    probabilidades = saida.logits_per_image.softmax(dim=1)[0]
    return float(probabilidades[0])


def analisar(dados, consulta):
    """
    Roda as três verificações. Devolve um dicionário com as notas e o veredito.

    'reprovada' traz o motivo quando a imagem não pode ser usada; vem None
    quando ela está liberada.
    """
    resultado = {"rostos": 0, "nsfw": 0.0, "relevancia": 0.0, "reprovada": None}

    resultado["nsfw"] = pontuar_nsfw(dados)
    if resultado["nsfw"] > LIMITE_NSFW:
        resultado["reprovada"] = f"conteúdo adulto ({resultado['nsfw']:.2f})"
        return resultado

    resultado["relevancia"] = pontuar_relevancia(dados, consulta)
    if resultado["relevancia"] < RELEVANCIA_MINIMA:
        resultado["reprovada"] = (
            f"pouca relação com '{consulta}' ({resultado['relevancia']:.2f})"
        )
        return resultado

    resultado["rostos"] = contar_rostos(dados)
    return resultado


def ordenar(analisadas):
    """
    Ordena as aprovadas: sem rosto primeiro, depois por relevância.

    Preferir foto sem pessoa identificável é a regra de menor risco numa
    escolha que ninguém vai revisar — e conversa com a restrição da própria
    licença sobre pessoas reconhecíveis.
    """
    return sorted(
        analisadas,
        key=lambda item: (item["analise"]["rostos"] > 0,
                          -item["analise"]["relevancia"]),
    )

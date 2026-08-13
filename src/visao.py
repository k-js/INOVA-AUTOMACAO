# -*- coding: utf-8 -*-
"""
Analisa os pixels da imagem antes de ela virar capa.

Os modelos que a chave da Groq alcança são todos de texto — nenhum enxerga
imagem. Então a análise roda AQUI, dentro do próprio Action: sem chave, sem
cota, sem custo. E, ao contrário de julgar pela legenda que o banco de imagens
fornece, isto olha a foto.

São três verificações, com papéis diferentes:

    relevância  portão: a imagem é uma foto do assunto, e não marca d'água,
                colagem ou captura de tela? Reprova; não ordena.

    similaridade  o quanto a imagem se parece com o termo. É o que ORDENA —
                não satura, ao contrário do portão.

    pessoas     estima se há gente em destaque. Não reprova sozinho, mas
                desempata a favor de quem não tem: a licença do Pexels
                restringe o uso de pessoas reconhecíveis, e uma escolha
                automática erra mais feio quando há gente na foto.

    NSFW        reprova conteúdo adulto. É uma rede de segurança, não uma
                garantia — classificadores erram.

O que isto NÃO faz: julgar bom gosto. CLIP mede semelhança semântica. Uma foto
datada, clichê ou que destoe das outras 33 capas passa por aqui sem alarme.

As dependências (torch, transformers) são pesadas e ficam num
requirements próprio, instalado só no workflow das capas — a publicação diária
não carrega esse peso.
"""

import io

MODELO_CLIP = "openai/clip-vit-base-patch32"
MODELO_NSFW = "Falconsai/nsfw_image_detection"

# Acima disto a imagem é reprovada por conteúdo adulto.
LIMITE_NSFW = 0.30

# Acima disto consideramos que há gente em destaque na foto.
LIMITE_PESSOAS = 0.5

# Abaixo disto o PORTÃO reprova: a imagem parece mais ruído que assunto.
# Quem ordena é a similaridade, não isto.
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


def _comparar(dados, textos):
    """Distribui a imagem entre os textos dados. Devolve a lista de probabilidades."""
    import torch

    modelos = _carregar()
    entradas = modelos["clip_proc"](
        text=textos, images=_imagem(dados), return_tensors="pt",
        padding=True, truncation=True,
    )
    with torch.no_grad():
        saida = modelos["clip"](**entradas)
    return saida.logits_per_image.softmax(dim=1)[0].tolist()


def pontuar_pessoas(dados):
    """
    O quanto a imagem mostra pessoas identificáveis, de 0 a 1.

    Feito com o CLIP, que já está carregado, e não com um detector de rostos.
    O OpenCV entrava aqui só por isto e se mostrou frágil no runner — e o sinal
    é usado apenas como desempate, então não precisa da precisão de um
    detector: basta separar "tem gente em destaque" de "não tem".
    """
    probabilidades = _comparar(dados, [
        "a photo showing people, with faces clearly visible",
        "a photo of objects, a place or a landscape, with no people in it",
    ])
    return float(probabilidades[0])


def pontuar_nsfw(dados):
    """Probabilidade de conteúdo adulto, de 0 a 1."""
    modelos = _carregar()
    for item in modelos["nsfw"](_imagem(dados)):
        if item["label"].lower().startswith("nsfw"):
            return float(item["score"])
    return 0.0


def pontuar_relevancia(dados, consulta):
    """
    PORTÃO: a imagem é uma foto do assunto, e não marca d'água ou captura?

    A consulta disputa com os termos de RUIDOS no mesmo softmax. Serve para
    reprovar, não para ordenar: contra distratores fracos, qualquer foto normal
    ganha de lavada e a nota satura em 1,00 — na primeira execução sete de oito
    candidatas empataram assim, e a escolha acabou caindo na ordem em que o
    Pexels devolveu.
    """
    return float(_comparar(dados, [f"a photo of {consulta}"] + RUIDOS)[0])


def pontuar_similaridade(dados, consulta):
    """
    ORDENAÇÃO: o quanto a imagem se parece com a consulta, sem disputa.

    É o cosseno entre a imagem e o texto, do próprio CLIP. Diferente do portão
    acima, não satura: fica tipicamente entre 0,15 e 0,35, e distingue uma foto
    que é exatamente o assunto de outra que só passa perto.
    """
    import torch

    modelos = _carregar()
    entradas = modelos["clip_proc"](
        text=[f"a photo of {consulta}"], images=_imagem(dados),
        return_tensors="pt", padding=True, truncation=True,
    )
    with torch.no_grad():
        saida = modelos["clip"](**entradas)
        imagem = saida.image_embeds / saida.image_embeds.norm(dim=-1, keepdim=True)
        texto = saida.text_embeds / saida.text_embeds.norm(dim=-1, keepdim=True)
    return float((imagem @ texto.T)[0, 0])


def analisar(dados, consulta):
    """
    Roda as três verificações. Devolve um dicionário com as notas e o veredito.

    'reprovada' traz o motivo quando a imagem não pode ser usada; vem None
    quando ela está liberada.
    """
    resultado = {"pessoas": 0.0, "nsfw": 0.0, "relevancia": 0.0,
                 "similaridade": 0.0, "reprovada": None}

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

    resultado["similaridade"] = pontuar_similaridade(dados, consulta)
    resultado["pessoas"] = pontuar_pessoas(dados)
    return resultado


def ordenar(analisadas):
    """
    Ordena as aprovadas: sem pessoas primeiro, depois por similaridade.

    Por SIMILARIDADE, e não pela relevância: aquela é o portão e satura em
    1,00, deixando o desempate cair na ordem do Pexels.

    Preferir foto sem pessoa em destaque é a regra de menor risco numa
    escolha que ninguém vai revisar — e conversa com a restrição da própria
    licença sobre pessoas reconhecíveis.
    """
    return sorted(
        analisadas,
        key=lambda item: (item["analise"]["pessoas"] > LIMITE_PESSOAS,
                          -item["analise"]["similaridade"]),
    )

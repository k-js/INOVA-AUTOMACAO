# -*- coding: utf-8 -*-
"""
Busca imagens de capa no Pexels.

Por que o Pexels: a licença dispensa atribuição — "Attribution is not
required. Giving credit to the photographer or Pexels is not necessary but
always appreciated" — e libera uso comercial. As proibições dela (não vender
cópias inalteradas, não sugerir endosso, não redistribuir em outro banco, não
usar como marca) não alcançam o uso aqui, que é ilustrar o cabeçalho de uma
página.

O Pixabay serve igual e fica como alternativa. O Unsplash NÃO serve: a licença
dispensa atribuição, mas as diretrizes da API dizem que aplicações que a usam
"must attribute Unsplash, the Unsplash photographer, and contain a link back
to their Unsplash profile" — obrigatório, e é o nosso caso.

Nada aqui decide qual imagem usar. Isto só devolve candidatas; quem julga é
src/visao.py, olhando os pixels.
"""

import os

API_PEXELS = "https://api.pexels.com/v1/search"

# Quantas candidatas pedir. Folga para os filtros descartarem sem sobrar zero.
QUANTIDADE = 15

# Uma candidata só serve se, depois do recorte 3:1, ainda alcançar o alvo.
# Guardar isso aqui evita baixar imagem que já se sabe pequena demais.
LARGURA_UTIL_MINIMA = 2400


def util_apos_recorte(largura, altura):
    """Largura que sobra depois do recorte 3:1 — o que de fato importa."""
    return min(largura, altura * 3)


def buscar(consulta, chave, quantidade=QUANTIDADE, requests_=None):
    """
    Candidatas do Pexels para a consulta. Devolve lista de dicionários.

    Cada candidata traz o que o registro de procedência precisa: origem,
    licença, autor e a URL da página no Pexels. Sem isso não haveria como
    responder, daqui a dois anos, de onde veio a foto.
    """
    import requests as _requests
    requests_ = requests_ or _requests

    resposta = requests_.get(
        API_PEXELS,
        headers={"Authorization": chave},
        params={
            "query": consulta,
            "orientation": "landscape",   # capa é faixa larga
            "size": "large",
            "per_page": quantidade,
        },
        timeout=45,
    )
    if resposta.status_code != 200:
        raise RuntimeError(f"Pexels HTTP {resposta.status_code}: {resposta.text[:160]}")

    candidatas = []
    for foto in resposta.json().get("photos", []):
        largura, altura = foto.get("width", 0), foto.get("height", 0)
        candidatas.append({
            "id": foto.get("id"),
            "largura": largura,
            "altura": altura,
            "util": util_apos_recorte(largura, altura),
            "url_arquivo": foto.get("src", {}).get("original", ""),
            "url_pagina": foto.get("url", ""),
            "autor": foto.get("photographer", ""),
            "legenda": foto.get("alt") or "",
            "origem": "Pexels",
            "licenca": "Pexels License (uso comercial, sem atribuição obrigatória)",
        })
    return candidatas


def grandes_o_bastante(candidatas, minimo=LARGURA_UTIL_MINIMA):
    """Só as que sobrevivem ao recorte 3:1 sem precisar de ampliação."""
    return [c for c in candidatas if c["util"] >= minimo]


def baixar(candidata, requests_=None, limite_bytes=25 * 1024 * 1024):
    """
    Baixa o arquivo da candidata.

    O limite existe porque o original do Pexels pode passar de 20 MB, e o
    runner não precisa carregar isso na memória sem teto.
    """
    import requests as _requests
    requests_ = requests_ or _requests

    resposta = requests_.get(candidata["url_arquivo"], timeout=90, stream=True)
    if resposta.status_code != 200:
        raise RuntimeError(f"download HTTP {resposta.status_code}")

    pedacos, total = [], 0
    for pedaco in resposta.iter_content(chunk_size=65536):
        total += len(pedaco)
        if total > limite_bytes:
            raise RuntimeError(f"arquivo passou de {limite_bytes // 1024 // 1024} MB")
        pedacos.append(pedaco)
    return b"".join(pedacos)


def chave():
    """Chave da API do Pexels, dos Secrets ou do .env."""
    valor = os.getenv("PEXELS_API_KEY")
    if not valor:
        raise RuntimeError(
            "PEXELS_API_KEY não definida.\n"
            "   Na Action vem dos Secrets; localmente, de credenciais/.env\n"
            "   Crie a chave em https://www.pexels.com/api/"
        )
    return valor

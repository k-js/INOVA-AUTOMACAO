# -*- coding: utf-8 -*-
"""
Envia a capa para a biblioteca de mídia e monta o bloco wp:cover.

O bloco NÃO é escrito de cabeça: ele é copiado de uma página que já funciona e
tem a imagem trocada. A estrutura exata importa — são blocos do Gutenberg, com
o mesmo dado repetido no comentário e no HTML — e tentar remontá-la já quebrou
o preâmbulo uma vez. Copiar e substituir é verificável: dá para conferir que a
imagem velha sumiu e a nova entrou.
"""

import re

CABECALHOS_JSON = {"User-Agent": "Mozilla/5.0", "Content-Type": "application/json"}


def enviar_para_biblioteca(api, dados, nome, alt, titulo, auth, requests_=None):
    """
    Sobe o arquivo para a biblioteca de mídia. Devolve (id, url).

    O alt vai numa segunda chamada: o upload aceita o binário puro, não um
    corpo JSON com metadados junto.
    """
    import requests as _requests
    requests_ = requests_ or _requests

    resposta = requests_.post(
        f"{api}/media",
        auth=auth,
        headers={
            "User-Agent": "Mozilla/5.0",
            "Content-Type": "image/jpeg",
            "Content-Disposition": f'attachment; filename="{nome}"',
        },
        data=dados,
        timeout=120,
    )
    if resposta.status_code not in (200, 201):
        raise RuntimeError(f"upload HTTP {resposta.status_code}: {resposta.text[:180]}")

    midia = resposta.json()
    media_id, url = midia["id"], midia["source_url"]

    # Todas as 33 capas do site têm alt vazio. Preencher aqui é o que evita
    # repetir a lacuna de acessibilidade nas novas.
    requests_.post(
        f"{api}/media/{media_id}",
        auth=auth, headers=CABECALHOS_JSON,
        json={"alt_text": alt, "title": titulo},
        timeout=60,
    )
    return media_id, url


def extrair_bloco_modelo(preambulo_modelo):
    """O bloco wp:cover da página modelo, ou None."""
    achado = re.search(r"<!--\s*wp:cover\b.*?<!--\s*/wp:cover\s*-->",
                       preambulo_modelo, re.S | re.I)
    return achado.group(0) if achado else None


def montar_bloco(bloco_modelo, url, media_id, alt):
    """
    O bloco do modelo com a imagem trocada. Devolve (bloco, problemas).

    A mesma imagem aparece em três lugares: na URL e no id dentro do comentário
    do bloco, e na classe wp-image-N do <img>. Todos precisam apontar para a
    nova — um deles fora de sincronia deixa o WordPress mostrando uma coisa e
    referenciando outra.
    """
    urls_antigas = re.findall(r"https?://[^\"'\s\\]+?\.(?:jpe?g|png|webp)",
                              bloco_modelo, re.I)
    ids_antigos = re.findall(r"wp-image-(\d+)", bloco_modelo)
    if not urls_antigas or not ids_antigos:
        return None, ["não achei imagem no bloco do modelo"]

    id_antigo = ids_antigos[0]
    bloco = bloco_modelo
    for antiga in set(urls_antigas):
        bloco = bloco.replace(antiga, url)
    bloco = bloco.replace(f"wp-image-{id_antigo}", f"wp-image-{media_id}")
    bloco = re.sub(rf'"id"\s*:\s*{id_antigo}\b', f'"id":{media_id}', bloco)

    # O srcset é gerado pelo WordPress na exibição; se vier junto do modelo,
    # aponta para os tamanhos da imagem ANTIGA.
    bloco = re.sub(r'\s(?:srcset|sizes)="[^"]*"', "", bloco)

    escapado = alt.replace('"', "&quot;")
    bloco, trocas = re.subn(r'alt="[^"]*"', f'alt="{escapado}"', bloco, count=1)
    if not trocas:
        return None, ["não achei o atributo alt no bloco do modelo"]

    return bloco, conferir_bloco(bloco, url, media_id, id_antigo, urls_antigas)


def conferir_bloco(bloco, url, media_id, id_antigo, urls_antigas):
    """Confere o bloco montado antes de ele ir para a página."""
    problemas = []

    if url not in bloco:
        problemas.append("a URL da nova imagem não entrou")
    if f"wp-image-{media_id}" not in bloco:
        problemas.append("a classe wp-image não aponta para a nova mídia")
    if re.search(rf"\bwp-image-{id_antigo}\b", bloco):
        problemas.append(f"sobrou referência à mídia antiga ({id_antigo})")
    for antiga in set(urls_antigas):
        if antiga != url and antiga in bloco:
            problemas.append(f"sobrou a URL antiga: {antiga[:60]}")
    if len(re.findall(r"<img\b", bloco)) != 1:
        problemas.append("o bloco ficou com um número inesperado de imagens")

    return problemas


def inserir_capa(preambulo, bloco):
    """
    Põe a capa no começo do preâmbulo, que é onde ela fica nas outras páginas:
    antes do botão VOLTAR, da descrição e do <head> com o CSS.
    """
    return bloco + "\n\n" + preambulo.lstrip("\n")

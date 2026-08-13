# -*- coding: utf-8 -*-
"""
Gera a descrição de uma aba a partir das categorias que ela já tem.

A descrição é a frase que aparece embaixo da capa, acima da tabela:

    GREENTECHS são empresas que desenvolvem tecnologias sustentáveis para
    minimizar o impacto ambiental e promover a preservação dos recursos
    naturais.

O modelo NÃO é consultado sobre o que é o setor. Ele recebe as categorias
reais das organizações daquela aba — a coluna CATEGORIA da planilha, que já
está publicada na tabela da página — e as reescreve no tom das descrições que
já existem no site. É reformulação de dado que você tem, não conhecimento
próprio do modelo, e por isso o resultado é conferível: dá para comparar a
frase com as categorias.

O que sai daqui é uma PROPOSTA. Quem grava no site é o gerar_descricoes.py, e
só depois de alguém ler.
"""

import os
import re
import json
from collections import Counter

# API compatível com o formato da OpenAI — dá para usar requests direto, sem
# acrescentar dependência ao projeto.
API_GROQ = "https://api.groq.com/openai/v1"

# Padrão inicial. O catálogo gratuito da Groq muda com alguma frequência:
# confira o que a sua chave alcança com `python gerar_descricoes.py
# --listar-modelos` e troque aqui (ou pela variável de ambiente GROQ_MODELO).
MODELO_PADRAO = os.getenv("GROQ_MODELO", "llama-3.3-70b-versatile")

# Limites tirados das 33 descrições que já estão no site: a mais curta tem 47
# caracteres, a mediana 157, a mais longa 576. A faixa aceita é folgada nas
# pontas, para recusar só o que destoa de verdade.
MIN_CARACTERES = 60
MAX_CARACTERES = 400


def categorias_da_pagina(html):
    """
    Conta as categorias das organizações listadas na tabela da página.

    A categoria é sempre a última coluna. Retorna um Counter, do mais comum
    para o menos comum.
    """
    contagem = Counter()
    for linha in re.findall(r'<tr class="organizationRow".*?</tr>', html, re.S):
        colunas = re.findall(r"<td[^>]*>(.*?)</td>", linha, re.S)
        if len(colunas) >= 2:
            categoria = re.sub(r"<[^>]+>", "", colunas[-1]).strip()
            if categoria:
                contagem[categoria] += 1
    return contagem


def montar_mensagens(aba, categorias, exemplos):
    """
    Monta a conversa enviada ao modelo.

    As categorias entram como a ÚNICA fonte sobre o setor, e os exemplos como
    referência de estilo. A instrução é explícita quanto a isso: sem inventar
    número de empresas, cidade, ano ou qualquer fato que não esteja ali.
    """
    lista_categorias = "\n".join(
        f"  - {nome} ({n} organizações)" for nome, n in categorias.most_common(10)
    )
    lista_exemplos = "\n\n".join(f"  {t}" for t in exemplos)

    sistema = (
        "Você escreve descrições curtas para as páginas do portal de inovação "
        "da UFPR. Cada página lista organizações de um setor.\n\n"
        "Regras:\n"
        "- Uma ou duas frases, entre 60 e 400 caracteres.\n"
        "- Comece pelo nome do setor em maiúsculas, seguido de 'são empresas "
        "que' ou 'são startups que'.\n"
        "- Descreva o setor APENAS a partir das categorias fornecidas. Não "
        "acrescente fatos que não estejam nelas: nada de números, datas, "
        "cidades, nomes de empresas ou afirmações de mercado.\n"
        "- Português do Brasil, tom institucional e sóbrio.\n"
        "- Responda com a frase e nada mais: sem aspas, sem markdown, sem "
        "comentários."
    )

    usuario = (
        f"Setor: {aba}\n\n"
        f"Categorias das organizações listadas nesta página:\n{lista_categorias}\n\n"
        f"Descrições de outras páginas do mesmo portal, como referência de "
        f"estilo:\n\n{lista_exemplos}\n\n"
        f"Escreva a descrição de {aba}."
    )

    return [
        {"role": "system", "content": sistema},
        {"role": "user", "content": usuario},
    ]


def conferir(aba, texto):
    """
    Confere a frase proposta. Retorna a lista de problemas (vazia se estiver boa).

    A conferência existe porque o texto vai para um site institucional: é mais
    barato recusar e pedir de novo do que revisar no ar.
    """
    problemas = []

    if not texto:
        return ["o modelo não devolveu texto"]

    if len(texto) < MIN_CARACTERES:
        problemas.append(f"curta demais ({len(texto)} caracteres)")
    if len(texto) > MAX_CARACTERES:
        problemas.append(f"longa demais ({len(texto)} caracteres)")

    # Sem o nome do setor, a frase não se sustenta sozinha embaixo da capa.
    raiz = re.split(r"\s+E\s+|\s+", aba.upper())[0]
    if raiz not in texto.upper():
        problemas.append(f"não menciona '{raiz}'")

    if re.search(r"[*_#`]|^\s*[-–]\s", texto, re.M):
        problemas.append("veio com marcação (markdown) em vez de texto puro")

    if texto.count(".") > 3:
        problemas.append("mais de três frases")

    return problemas


def gerar(aba, categorias, exemplos, chave, modelo=None, requests_=None):
    """
    Pede a frase ao modelo e devolve (texto, problemas).

    texto vem vazio se não houver nada aproveitável. Uma segunda tentativa é
    feita quando a primeira não passa na conferência, com o motivo anexado ao
    pedido — costuma bastar para corrigir tamanho ou formato.
    """
    import requests as _requests
    requests_ = requests_ or _requests
    modelo = modelo or MODELO_PADRAO

    mensagens = montar_mensagens(aba, categorias, exemplos)

    for tentativa in (1, 2):
        resposta = requests_.post(
            f"{API_GROQ}/chat/completions",
            headers={"Authorization": f"Bearer {chave}",
                     "Content-Type": "application/json"},
            json={
                "model": modelo,
                "messages": mensagens,
                # Baixa, mas não zero: o texto precisa fluir, não variar.
                "temperature": 0.3,
                "max_tokens": 300,
            },
            timeout=60,
        )

        if resposta.status_code != 200:
            return "", [f"HTTP {resposta.status_code}: {resposta.text[:160]}"]

        texto = resposta.json()["choices"][0]["message"]["content"].strip()
        texto = texto.strip('"').strip()

        problemas = conferir(aba, texto)
        if not problemas or tentativa == 2:
            return (texto, problemas) if problemas else (texto, [])

        mensagens = mensagens + [
            {"role": "assistant", "content": texto},
            {"role": "user",
             "content": f"Isso não serve: {'; '.join(problemas)}. "
                        f"Reescreva corrigindo, respondendo só com a frase."},
        ]

    return "", ["não passou na conferência em duas tentativas"]


def _completar(mensagens, chave, modelo=None, max_tokens=120, requests_=None):
    """Uma chamada ao modelo, devolvendo só o texto. Levanta em caso de erro."""
    import requests as _requests
    requests_ = requests_ or _requests

    resposta = requests_.post(
        f"{API_GROQ}/chat/completions",
        headers={"Authorization": f"Bearer {chave}",
                 "Content-Type": "application/json"},
        json={"model": modelo or MODELO_PADRAO, "messages": mensagens,
              "temperature": 0.2, "max_tokens": max_tokens},
        timeout=60,
    )
    if resposta.status_code != 200:
        raise RuntimeError(f"HTTP {resposta.status_code}: {resposta.text[:160]}")
    return resposta.json()["choices"][0]["message"]["content"].strip().strip('"')


def termo_de_busca(aba, categorias, chave, modelo=None, requests_=None):
    """
    Termo em inglês para procurar a capa, montado a partir das categorias.

    Em inglês de propósito: é o idioma em que tanto o Pexels quanto o CLIP
    funcionam melhor, e o MESMO termo alimenta os dois — a busca e a medição
    de relevância. Se fossem termos diferentes, o CLIP estaria pontuando
    contra algo que não foi o que se pediu ao banco de imagens.
    """
    lista = ", ".join(nome for nome, _ in categorias.most_common(6))
    mensagens = [
        {"role": "system", "content":
            "Você devolve termos de busca para bancos de imagem. Responda com "
            "2 a 5 palavras em INGLÊS, descrevendo uma cena fotografável. "
            "Nada de nomes de empresa, marca, texto na imagem ou termo "
            "abstrato. Responda só com o termo."},
        {"role": "user", "content":
            f"Setor: {aba}\nCategorias das organizações: {lista}\n\n"
            f"Termo de busca para a foto de capa dessa página:"},
    ]
    termo = _completar(mensagens, chave, modelo, max_tokens=30, requests_=requests_)
    return re.sub(r"[^A-Za-z0-9 \-]", "", termo).strip().lower()[:60]


def texto_alternativo(legenda, aba, chave, modelo=None, requests_=None):
    """
    Texto alternativo em português, a partir da legenda da própria foto.

    A base é a legenda que o banco de imagens fornece — uma descrição do que
    a foto mostra. O modelo traduz e enxuga; não inventa o conteúdo da imagem,
    que ele não vê.

    Todas as 33 capas do site hoje têm alt vazio. Como a automação já está
    escrevendo texto, preencher isto sai de graça e melhora a acessibilidade
    em vez de repetir a lacuna.
    """
    if not legenda:
        return ""
    mensagens = [
        {"role": "system", "content":
            "Você escreve texto alternativo (alt) para imagens, em português "
            "do Brasil. Uma frase curta, até 120 caracteres, descrevendo o que "
            "a imagem mostra. Não comece com 'imagem de' ou 'foto de'. "
            "Responda só com a frase."},
        {"role": "user", "content":
            f"Descrição da foto (em inglês): {legenda}\n"
            f"Ela ilustra a página do setor {aba}.\n\nTexto alternativo:"},
    ]
    alt = _completar(mensagens, chave, modelo, max_tokens=80, requests_=requests_)
    return alt.strip()[:140]


def listar_modelos(chave, requests_=None):
    """Modelos que esta chave alcança, do catálogo atual da Groq."""
    import requests as _requests
    requests_ = requests_ or _requests
    resposta = requests_.get(
        f"{API_GROQ}/models",
        headers={"Authorization": f"Bearer {chave}"},
        timeout=30,
    )
    if resposta.status_code != 200:
        raise RuntimeError(f"HTTP {resposta.status_code}: {resposta.text[:200]}")
    return sorted(m["id"] for m in resposta.json().get("data", []))

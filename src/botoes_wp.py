# -*- coding: utf-8 -*-
"""
Regenera a grade de botões de uma página de índice do site (ex.: /startups/).

Os botões dessas páginas não vêm do menu do WordPress: são blocos Gutenberg
escritos no conteúdo da própria página. Mantê-los à mão significa que toda aba
nova exige editar a página, e é por isso que faltam botões hoje.

Segurança: antes de qualquer escrita, o conteúdo atual é salvo em
backups/ com data e hora. Para desfazer, use restaurar(). O WordPress também
mantém revisões próprias da página.
"""

import os
import re
import json
import unicodedata
from datetime import datetime

import rede
import requests
from requests.auth import HTTPBasicAuth
from dotenv import load_dotenv

RAIZ_PROJETO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CAMINHO_ENV = os.path.join(RAIZ_PROJETO, "credenciais", ".env")
DIR_BACKUPS = os.path.join(RAIZ_PROJETO, "backups")

SITE = "https://inova.ufpr.br"
API = f"{SITE}/wp-json/wp/v2"
CABECALHOS = {"User-Agent": "Mozilla/5.0", "Content-Type": "application/json"}

# Marcadores que delimitam a área gerada automaticamente. Só o que está entre
# eles é reescrito — o resto da página (capa, título, botão VOLTAR) fica
# intocado.
INICIO = "<!-- BOTOES AUTOMATICOS: NAO EDITAR MANUALMENTE -->"
FIM = "<!-- FIM BOTOES AUTOMATICOS -->"

# Classes copiadas dos botões já existentes na página, para que os gerados
# tenham exatamente a mesma aparência.
CLASSE_BOTAO = ("wp-block-button has-custom-width wp-block-button__width-50 "
                "is-style-default")
CLASSE_LINK = ("wp-block-button__link has-neve-text-color-color "
               "has-nv-site-bg-background-color has-text-color has-background "
               "wp-element-button")


def _auth():
    load_dotenv(dotenv_path=CAMINHO_ENV)
    usuario = os.getenv("WP_USER")
    senha = os.getenv("WP_APP_PASSWORD")
    if not usuario or not senha:
        raise RuntimeError("WP_USER e WP_APP_PASSWORD não definidos.")
    return HTTPBasicAuth(usuario, senha)


def _normalizar(texto):
    texto = unicodedata.normalize("NFKD", str(texto).strip().upper())
    return texto.encode("ASCII", "ignore").decode("ASCII")


# ---------------------------------------------------------------------
# Leitura da página
# ---------------------------------------------------------------------
def obter_pagina(slug):
    """Dados completos da página (com content.raw), ou None."""
    resposta = rede.com_retentativa(
        lambda: requests.get(
            f"{API}/pages",
            params={"slug": slug, "context": "edit", "status": "publish,draft"},
            auth=_auth(), headers=CABECALHOS, timeout=30,
        ),
        descricao=f"obter página '{slug}'",
    )
    if resposta.status_code != 200:
        return None
    paginas = resposta.json()
    return paginas[0] if paginas else None


def _achar_grade(conteudo):
    """
    Localiza a grade de botões dentro do conteúdo da página.

    Retorna (inicio, fim) como posições no texto, ou None.

    Lida com os dois formatos possíveis:

    - Conteúdo bruto do Gutenberg, em que cada bloco vem delimitado por
      comentários <!-- wp:buttons --> ... <!-- /wp:buttons -->
    - HTML puro, sem os comentários de bloco

    A grade é identificada por conter botões de largura 50
    (wp-block-button__width-50) — é o que a distingue do bloco isolado do
    botão VOLTAR, que tem largura padrão.
    """
    marcador_largura = "wp-block-button__width-50"

    # Formato Gutenberg: usa os comentários de bloco como fronteira, para que
    # a substituição não corte o bloco pela metade.
    for m in re.finditer(r"<!--\s*wp:buttons\b", conteudo):
        fechamento = conteudo.find("<!-- /wp:buttons -->", m.end())
        if fechamento == -1:
            continue
        fim = fechamento + len("<!-- /wp:buttons -->")
        if marcador_largura in conteudo[m.start():fim]:
            return m.start(), fim

    # HTML puro: delimita pela div do bloco de botões.
    for m in re.finditer(r'<div class="wp-block-buttons[^"]*">', conteudo):
        # Avança até fechar a div correspondente, contando aninhamentos.
        profundidade = 0
        pos = m.start()
        for div in re.finditer(r"<div\b|</div>", conteudo[m.start():]):
            profundidade += 1 if div.group(0).startswith("<div") else -1
            if profundidade == 0:
                pos = m.start() + div.end()
                break
        if pos > m.start() and marcador_largura in conteudo[m.start():pos]:
            return m.start(), pos

    return None


def extrair_botoes(html):
    """
    Lê os botões da grade já presentes no conteúdo.

    Retorna [(rotulo, url)]. Usado para preservar as URLs atuais: elas são
    inconsistentes (/home/agtechs/, /indtechs, /biotechs/) e não podem ser
    derivadas do nome — reescrevê-las quebraria links que funcionam.
    """
    padrao = (r'<div class="wp-block-button has-custom-width[^"]*">'
              r'<a[^>]+href="([^"]+)"[^>]*>(?:<strong>)?([^<]+?)(?:</strong>)?</a>'
              r'</div>')
    return [(rotulo.strip(), url) for url, rotulo in re.findall(padrao, html)]


# ---------------------------------------------------------------------
# Backup e restauração
# ---------------------------------------------------------------------
def salvar_backup(slug, pagina):
    """
    Grava o conteúdo atual da página em backups/, com data e hora no nome.

    Feito ANTES de qualquer escrita. Retorna o caminho do arquivo.
    """
    os.makedirs(DIR_BACKUPS, exist_ok=True)
    carimbo = datetime.now().strftime("%Y%m%d-%H%M%S")
    caminho = os.path.join(DIR_BACKUPS, f"{slug}-{carimbo}.json")

    with open(caminho, "w", encoding="utf-8") as f:
        json.dump({
            "slug": slug,
            "pagina_id": pagina["id"],
            "salvo_em": datetime.now().isoformat(timespec="seconds"),
            "conteudo": pagina.get("content", {}).get("raw", ""),
        }, f, ensure_ascii=False, indent=1)

    return caminho


def restaurar(caminho_backup, dry_run=False):
    """
    Devolve à página o conteúdo salvo em um backup.

    Uso:
        python -c "import sys; sys.path.insert(0,'src'); import botoes_wp; \
                   botoes_wp.restaurar('backups/startups-20260730-215500.json')"
    """
    with open(caminho_backup, encoding="utf-8") as f:
        dados = json.load(f)

    if dry_run:
        return (f"restauraria a página {dados['pagina_id']} ({dados['slug']}) "
                f"para o conteúdo de {dados['salvo_em']}")

    resposta = rede.com_retentativa(
        lambda: requests.post(
            f"{API}/pages/{dados['pagina_id']}",
            auth=_auth(), headers=CABECALHOS,
            json={"content": dados["conteudo"]},
            timeout=30,
        ),
        descricao="restaurar página",
    )
    if resposta.status_code != 200:
        raise RuntimeError(f"falha ao restaurar (HTTP {resposta.status_code})")

    return (f"página {dados['slug']} restaurada para o estado de "
            f"{dados['salvo_em']}")


def listar_backups(slug=None):
    """Backups disponíveis, do mais recente para o mais antigo."""
    if not os.path.isdir(DIR_BACKUPS):
        return []
    arquivos = [f for f in os.listdir(DIR_BACKUPS) if f.endswith(".json")]
    if slug:
        arquivos = [f for f in arquivos if f.startswith(slug + "-")]
    return sorted(arquivos, reverse=True)


# ---------------------------------------------------------------------
# Geração dos botões
# ---------------------------------------------------------------------
def montar_html_botoes(botoes):
    """
    Monta o HTML da grade a partir de [(rotulo, url)], em ordem alfabética.

    A grade tem 2 colunas preenchidas por COLUNA, não por linha: a primeira
    metade da lista vai à esquerda, a segunda à direita. Como os blocos são
    dispostos em sequência, eles precisam ser intercalados
    (esquerda[0], direita[0], esquerda[1], direita[1], ...).
    """
    ordenados = sorted(botoes, key=lambda b: _normalizar(b[0]))

    metade = (len(ordenados) + 1) // 2
    esquerda = ordenados[:metade]
    direita = ordenados[metade:]

    intercalados = []
    for i in range(metade):
        intercalados.append(esquerda[i])
        if i < len(direita):
            intercalados.append(direita[i])

    # Formato de bloco do Gutenberg: os comentários <!-- wp:... --> são o que
    # faz o editor reconhecer isto como blocos editáveis. Sem eles, o conteúdo
    # aparece como "bloco clássico" e o editor visual deixa de funcionar direito.
    linhas = [
        INICIO,
        '<!-- wp:buttons {"layout":{"type":"flex",'
        '"justifyContent":"center"}} -->',
        '<div class="wp-block-buttons">',
    ]

    for rotulo, url in intercalados:
        linhas.append(
            '<!-- wp:button {"width":50,"className":"is-style-default"} -->'
        )
        linhas.append(
            f'<div class="{CLASSE_BOTAO}">'
            f'<a class="{CLASSE_LINK}" href="{url}" style="border-radius:0px">'
            f'{rotulo}</a></div>'
        )
        linhas.append("<!-- /wp:button -->")

    linhas.append("</div>")
    linhas.append("<!-- /wp:buttons -->")
    linhas.append(FIM)
    return "\n".join(linhas)


def aplicar_botoes(slug, botoes, dry_run=False):
    """
    Reescreve a grade de botões da página.

    Faz backup antes de escrever. Se a página ainda não tiver os marcadores,
    a área gerada substitui o primeiro bloco de botões de largura 50 que
    encontrar — a partir daí os marcadores passam a delimitar a região.

    Retorna (mensagem, caminho_do_backup).
    """
    pagina = obter_pagina(slug)
    if not pagina:
        raise RuntimeError(f"página '{slug}' não encontrada")

    conteudo = pagina.get("content", {}).get("raw", "")
    if not conteudo:
        raise RuntimeError("não consegui ler o conteúdo bruto da página "
                           "(verifique as permissões do usuário)")

    backup = salvar_backup(slug, pagina) if not dry_run else "(dry-run)"
    novo_bloco = montar_html_botoes(botoes)

    if INICIO in conteudo and FIM in conteudo:
        novo_conteudo = re.sub(
            re.escape(INICIO) + r".*?" + re.escape(FIM),
            lambda _: novo_bloco,
            conteudo,
            flags=re.S,
        )
    else:
        # Primeira execução: envolve a grade de botões existente.
        #
        # O conteúdo bruto do Gutenberg não é o HTML renderizado: cada bloco
        # vem entre comentários <!-- wp:buttons --> ... <!-- /wp:buttons -->.
        # A grade é o bloco de botões que contém os de largura 50 (os da
        # grade), e não o bloco isolado do botão VOLTAR.
        m = _achar_grade(conteudo)
        if not m:
            raise RuntimeError(
                "não localizei a grade de botões no conteúdo da página.\n"
                f"Como contornar: abra /{slug}/ no editor do WordPress, entre "
                f"no modo de edição de código (⋮ → Editor de código) e "
                f"coloque as linhas\n\n  {INICIO}\n\ne\n\n  {FIM}\n\n"
                "logo antes e logo depois do bloco de botões da grade."
            )
        inicio, fim = m
        novo_conteudo = conteudo[:inicio] + novo_bloco + conteudo[fim:]

    if novo_conteudo == conteudo:
        return "nada mudou na página", backup

    if dry_run:
        return (f"reescreveria {len(botoes)} botões "
                f"(conteúdo de {len(conteudo)} para {len(novo_conteudo)} chars)"), backup

    resposta = rede.com_retentativa(
        lambda: requests.post(
            f"{API}/pages/{pagina['id']}",
            auth=_auth(), headers=CABECALHOS,
            json={"content": novo_conteudo},
            timeout=30,
        ),
        descricao=f"gravar botões em /{slug}/",
    )
    if resposta.status_code != 200:
        raise RuntimeError(
            f"falha ao atualizar a página (HTTP {resposta.status_code}). "
            f"O conteúdo anterior está em {backup}"
        )

    return f"{len(botoes)} botões aplicados em /{slug}/", backup

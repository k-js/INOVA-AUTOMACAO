# -*- coding: utf-8 -*-
"""
Cria no WordPress a página de uma aba que ainda não tem página no site.

A página nasce como RASCUNHO: existe, já traz o marcador que a publicação
procura e já pode receber conteúdo, mas só aparece para o público quando
alguém clicar em "Publicar" no WordPress. Assim uma aba criada por engano na
planilha nunca vira página pública do site da UFPR.

Também insere a página no menu de navegação, se um menu for indicado.

Usado por sincronizar_config.py; não costuma ser chamado diretamente.
"""

import os
import re
import unicodedata

import rede
import requests
from requests.auth import HTTPBasicAuth
from dotenv import load_dotenv

import config
import preambulo

RAIZ_PROJETO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CAMINHO_ENV = os.path.join(RAIZ_PROJETO, "credenciais", ".env")

SITE = "https://inova.ufpr.br"
API = f"{SITE}/wp-json/wp/v2"

CABECALHOS = {
    "User-Agent": "Mozilla/5.0",
    "Content-Type": "application/json",
}

# Conteúdo inicial da página — usado apenas como RESERVA.
#
# O preâmbulo (tudo antes do marcador) normalmente é lido da página modelo no
# site, por conteudo_de_pagina_nova(). Esta cópia só entra em cena se essa
# leitura falhar, e por isso ela envelhece: já esteve sem o <style> que
# centraliza as colunas, sem o campo de busca e sem o botão VOLTAR.
#
# Quando ela for usada, o log avisa — e corrigir_preambulo.py conserta a
# página depois.
#
# O marcador é obrigatório em qualquer caso: atualizador_WP.py substitui tudo
# entre ele e o </table> seguinte. Sem o marcador, a publicação falha.
CONTEUDO_INICIAL = """<head>
<style>
/* Estilização da tooltip */
.tooltip-inner {
  max-width: 200px;
  background-color: #f0f0f0;
  color: #333;
  padding: 10px;
  border-radius: 5px;
  white-space: pre-wrap;
}

/* Primeira coluna: nome da organização, alinhado à esquerda */
#organization_table td:first-child {
  width: 600px;
  height: 25.19px;
}

/* Demais colunas: centralizadas */
#organization_table td:nth-child(2) {
  text-align: center;
  width: 55px;
}

#organization_table td:nth-child(3) {
  text-align: center;
}

#organization_table td:nth-child(4) {
  text-align: center;
}

/* Cabeçalho */
#organization_table th:first-child {
  width: 300px;
  height: 40px;
  background-color: #f4f8fb;
  text-align: left;
  font-weight: bold;
}

#organization_table th:nth-child(2) {
  text-align: center;
  width: 55px;
}

#organization_table th:nth-child(3) {
  text-align: center;
  width: 150px;
}

#organization_table th:nth-child(4) {
  text-align: center;
  width: 200px;
  max-width: 200px;
}

#categoriaSelect {
  width: 170px;
}
</style>
</head>

<body>
<div>
<input class="form-control" id="search" placeholder="Busque por uma organização" type="text"/>
<!-- COMECA ATUALIZAR DAQUI -->
<div class="p-2 mr-2" id="count"><p><b>Total de organizações:</b> 0</p></div>
<table class="table" id="organization_table">
<thead>
<tr><th scope="col"><p>Organização</p></th></tr>
</thead>
<tbody>
</tbody>
</table>
</div>
</body>"""


def _credenciais():
    """Usuário e senha de aplicativo do WordPress, dos Secrets ou do .env."""
    load_dotenv(dotenv_path=CAMINHO_ENV)
    usuario = os.getenv("WP_USER")
    senha = os.getenv("WP_APP_PASSWORD")
    if not usuario or not senha:
        raise RuntimeError(
            "WP_USER e WP_APP_PASSWORD não definidos. "
            "Na Action vêm dos Secrets; localmente, de credenciais/.env"
        )
    return HTTPBasicAuth(usuario, senha)


def gerar_slug(nome_aba):
    """
    Converte o nome de uma aba no slug de URL correspondente.

    'PARQUES CIENTÍFICOS' -> 'parques-cientificos'

    Atenção: nem toda página do site segue esta regra — DEEPTECHS aponta para
    /biotechs/ e RETAILTECHS para /retailtechs-2/. Por isso o slug gerado aqui
    só é usado para páginas NOVAS; as existentes são descobertas por busca.
    """
    texto = unicodedata.normalize("NFKD", str(nome_aba).strip())
    texto = texto.encode("ASCII", "ignore").decode("ASCII").lower()
    texto = re.sub(r"[^a-z0-9]+", "-", texto)
    return texto.strip("-")


def gerar_titulo(nome_aba):
    """
    Título legível a partir do nome da aba, que vem todo em maiúsculas.

    'HUBS E ECOSSISTEMAS' -> 'Hubs e Ecossistemas'
    """
    conectores = {"e", "de", "da", "do", "das", "dos", "a", "o", "em", "para"}
    palavras = str(nome_aba).strip().lower().split()
    saida = []
    for i, palavra in enumerate(palavras):
        if i > 0 and palavra in conectores:
            saida.append(palavra)
        else:
            saida.append(palavra.capitalize())
    return " ".join(saida)


def _preambulo_do_modelo():
    """
    Lê no site o preâmbulo da página modelo, já sem a capa dela.

    Ler em vez de guardar uma cópia no código evita que a cópia envelheça: se
    alguém ajustar o CSS, o botão VOLTAR ou o campo de busca no WordPress, a
    próxima página criada já nasce com o ajuste.

    Retorna None se qualquer coisa não bater — o chamador cai na reserva.
    """
    url = config.ABAS_LINKS.get(preambulo.ABA_MODELO)
    if not url:
        print(f"   ⚠️  aba modelo '{preambulo.ABA_MODELO}' não está em ABAS_LINKS")
        return None
    slug = url.rstrip("/").rsplit("/", 1)[-1]

    try:
        resposta = rede.com_retentativa(
            lambda: requests.get(
                f"{API}/pages",
                params={"slug": slug, "context": "edit"},
                auth=_credenciais(),
                headers=CABECALHOS,
                timeout=30,
            ),
            descricao=f"ler preâmbulo do modelo '{slug}'",
        )
    except Exception as erro:
        print(f"   ⚠️  não consegui ler a página modelo: {erro}")
        return None

    if resposta.status_code != 200 or not resposta.json():
        print(f"   ⚠️  página modelo '{slug}' não encontrada "
              f"(HTTP {resposta.status_code})")
        return None

    partes = preambulo.partir_conteudo(
        resposta.json()[0].get("content", {}).get("raw", "")
    )
    if not partes:
        print(f"   ⚠️  a página modelo '{slug}' não tem o marcador")
        return None

    limpo = preambulo.preambulo_estrutural(partes[0])

    # Mesma conferência do corrigir_preambulo.py: melhor nascer com a reserva
    # do que nascer com a capa do modelo ou sem o CSS da tabela.
    problemas = preambulo.conferir_preambulo(limpo)
    if problemas:
        print(f"   ⚠️  preâmbulo do modelo reprovado: {'; '.join(problemas)}")
        return None

    return limpo


def conteudo_de_pagina_nova():
    """Conteúdo com que a página nasce: preâmbulo do site + tabela vazia."""
    partes = preambulo.partir_conteudo(CONTEUDO_INICIAL)
    do_modelo = _preambulo_do_modelo()

    if do_modelo and partes:
        _, bloco, sufixo = partes
        return do_modelo + bloco + sufixo

    print("   ⚠️  usando o preâmbulo de reserva do código. Rode "
          "corrigir_preambulo.py depois para padronizar a página.")
    return CONTEUDO_INICIAL


def buscar_pagina_por_slug(slug):
    """Retorna os dados da página com esse slug, ou None."""
    resposta = requests.get(
        f"{API}/pages",
        params={"slug": slug, "status": "publish,draft,pending,private"},
        auth=_credenciais(),
        headers=CABECALHOS,
        timeout=30,
    )
    if resposta.status_code != 200:
        return None
    paginas = resposta.json()
    return paginas[0] if paginas else None


def criar_pagina(nome_aba, dry_run=False):
    """
    Cria a página da aba como rascunho.

    Retorna (url, mensagem). url é None se nada foi criado.
    """
    slug = gerar_slug(nome_aba)
    titulo = gerar_titulo(nome_aba)

    existente = buscar_pagina_por_slug(slug)
    if existente:
        return (
            f"{SITE}/{slug}/",
            f"já existia (status: {existente.get('status')}, id {existente.get('id')})",
        )

    if dry_run:
        return f"{SITE}/{slug}/", "seria criada como rascunho (--dry-run)"

    resposta = requests.post(
        f"{API}/pages",
        auth=_credenciais(),
        headers=CABECALHOS,
        json={
            "title": titulo,
            "slug": slug,
            "content": conteudo_de_pagina_nova(),
            # Rascunho: só vai ao ar quando alguém publicar manualmente.
            "status": "draft",
            # Página na raiz do site, como todas as demais páginas de techs:
            # /gametechs/ e não /startups/gametechs/. Com um ascendente, a URL
            # mudaria e deixaria de bater com a registrada em ABAS_LINKS,
            # fazendo a publicação não encontrar a página.
            "parent": 0,
        },
        timeout=30,
    )

    if resposta.status_code not in (200, 201):
        detalhe = resposta.text[:200]
        raise RuntimeError(f"falha ao criar '{titulo}' (HTTP {resposta.status_code}): {detalhe}")

    dados = resposta.json()
    return f"{SITE}/{slug}/", f"criada como RASCUNHO (id {dados.get('id')})"


def publicar_pagina(nome_aba, dry_run=False):
    """
    Passa a página da aba de rascunho para publicada.

    Só age sobre páginas em rascunho: uma página já publicada não é tocada, e
    outros status (privada, pendente, lixeira) são recusados para que a
    automação não desfaça uma decisão editorial sem querer.

    Retorna (url, mensagem). url é None se nada foi publicado.
    """
    slug = gerar_slug(nome_aba)
    pagina = buscar_pagina_por_slug(slug)

    if not pagina:
        return None, "página não encontrada"

    status = pagina.get("status")

    if status == "publish":
        return f"{SITE}/{slug}/", "já estava publicada"

    if status != "draft":
        return None, (f"status é '{status}', não 'draft' — não vou mexer. "
                      f"Publique manualmente se for o caso.")

    if dry_run:
        return f"{SITE}/{slug}/", "seria publicada (--dry-run)"

    resposta = requests.post(
        f"{API}/pages/{pagina['id']}",
        auth=_credenciais(),
        headers=CABECALHOS,
        json={"status": "publish"},
        timeout=30,
    )

    if resposta.status_code != 200:
        raise RuntimeError(
            f"falha ao publicar '{nome_aba}' (HTTP {resposta.status_code}): "
            f"{resposta.text[:200]}"
        )

    # A URL real pode diferir da esperada se a página tiver um ascendente
    # (ex.: /startups/gametechs/ em vez de /gametechs/). Nesse caso a
    # publicação não encontraria a página pelo link em ABAS_LINKS.
    dados = resposta.json()
    url_real = dados.get("link", "")
    url_esperada = f"{SITE}/{slug}/"

    if url_real and url_real.rstrip("/") != url_esperada.rstrip("/"):
        return url_real, (
            f"PUBLICADA (id {pagina['id']}), mas a URL ficou {url_real} "
            f"em vez de {url_esperada}.\n"
            f"     Atualize ABAS_LINKS no src/config.py, ou tire o ascendente "
            f"da página no WordPress."
        )

    return url_esperada, f"PUBLICADA (id {pagina['id']})"


# ---------------------------------------------------------------------
# Menu de navegação
# ---------------------------------------------------------------------
def listar_menus():
    """Menus de navegação do site: [{id, name, slug}]. Lista vazia se indisponível."""
    resposta = requests.get(
        f"{API}/menus", auth=_credenciais(), headers=CABECALHOS, timeout=30
    )
    if resposta.status_code != 200:
        return []
    return resposta.json()


def item_ja_no_menu(menu_id, pagina_id):
    """True se a página já está nesse menu."""
    resposta = requests.get(
        f"{API}/menu-items",
        params={"menus": menu_id, "per_page": 100},
        auth=_credenciais(),
        headers=CABECALHOS,
        timeout=30,
    )
    if resposta.status_code != 200:
        return False
    return any(str(i.get("object_id")) == str(pagina_id) for i in resposta.json())


def adicionar_ao_menu(nome_aba, menu_id, pai_id=None, dry_run=False):
    """
    Adiciona a página da aba a um menu de navegação.

    ⚠️ Só adiciona páginas PUBLICADAS. Um item de menu apontando para rascunho
    fica visível ao público em vários temas — inclusive no tema deste site — e
    leva o visitante a um 404. Publique a página primeiro.

    Retorna uma mensagem descrevendo o que aconteceu.
    """
    slug = gerar_slug(nome_aba)
    pagina = buscar_pagina_por_slug(slug)
    if not pagina:
        return "página não encontrada — nada a fazer no menu"

    if pagina.get("status") != "publish":
        return (f"não adicionada: a página está como '{pagina.get('status')}'. "
                f"Um item de menu apontando para rascunho aparece no site e dá "
                f"404 ao ser clicado. Publique a página e adicione ao menu depois.")

    if item_ja_no_menu(menu_id, pagina["id"]):
        return "já estava no menu"

    if dry_run:
        return f"seria adicionada ao menu {menu_id} (--dry-run)"

    corpo = {
        "title": gerar_titulo(nome_aba),
        "menus": menu_id,
        "object": "page",
        "object_id": pagina["id"],
        "type": "post_type",
        "status": "publish",
    }
    if pai_id:
        corpo["parent"] = pai_id

    resposta = requests.post(
        f"{API}/menu-items",
        auth=_credenciais(),
        headers=CABECALHOS,
        json=corpo,
        timeout=30,
    )

    if resposta.status_code not in (200, 201):
        return f"falha ao adicionar ao menu (HTTP {resposta.status_code})"

    return f"adicionada ao menu (item {resposta.json().get('id')})"

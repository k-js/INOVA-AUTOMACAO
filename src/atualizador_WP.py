import requests
from urllib.parse import urlparse
from dotenv import load_dotenv
import os
import re
from requests.auth import HTTPBasicAuth

# Raiz do projeto (este arquivo está em src/).
RAIZ_PROJETO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CAMINHO_ENV = os.path.join(RAIZ_PROJETO, "credenciais", ".env")

def atualizar_pagina_wp(pagina_url, nova_tabela_html):
    slug = urlparse(pagina_url).path.strip('/')

    search_url = "https://inova.ufpr.br/wp-json/wp/v2/pages"
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Content-Type": "application/json"
    }

    # Buscar a página pelo slug
    resp = requests.get(search_url, params={'slug': slug}, headers=headers)
    print("Código de status da busca:", resp.status_code)
    if resp.status_code != 200:
        print("Erro ao buscar página:", resp.text)
        return False

    pages = resp.json()
    if not pages:
        print(f"Nenhuma página encontrada com slug '{slug}'")
        return False

    page_id = pages[0]['id']
    print(f"ID da página encontrada: {page_id}")

    page_url = f"https://inova.ufpr.br/wp-json/wp/v2/pages/{page_id}?context=edit"

    # Caminho absoluto: com caminho relativo, o .env só era encontrado quando o
    # script rodava a partir da raiz do projeto.
    load_dotenv(dotenv_path=CAMINHO_ENV)
    WP_USER = os.getenv("WP_USER")
    WP_APP_PASSWORD = os.getenv("WP_APP_PASSWORD")

    if not WP_USER or not WP_APP_PASSWORD:
        print("❌ WP_USER ou WP_APP_PASSWORD não definidos — impossível autenticar.")
        print("   Na Action vêm dos Secrets; localmente, de credenciais/.env")
        return False

    # Obter conteúdo com contexto de edição
    resp_get = requests.get(
        page_url,
        auth=HTTPBasicAuth(WP_USER, WP_APP_PASSWORD),
        headers=headers
    )

    if resp_get.status_code != 200:
        print("Erro ao obter conteúdo:", resp_get.text)
        return False

    page_data = resp_get.json()
    conteudo = page_data.get("content", {}).get("raw")

    if not conteudo:
        print("Conteúdo 'raw' não encontrado. Verifique permissões do usuário.")
        return False

    # Substitui do marcador até o fim do último </table>, incluindo os blocos
    # de <script> que venham logo depois.
    #
    # O padrão anterior era '.*?</table>' — não-guloso, parava no primeiro
    # </table>. Como o HTML gerado põe os scripts DENTRO da tabela, isso
    # funcionava na maior parte dos casos; mas quando uma versão anterior da
    # página tinha scripts FORA dela, esses sobreviviam à substituição e se
    # acumulavam a cada publicação.
    #
    # O efeito era invisível no HTML e quebrava a página: cada carga extra do
    # jQuery substitui a instância e descarta os handlers já registrados,
    # inclusive o document.ready que popula os filtros. Os selects apareciam
    # vazios. /periodicos-cientificos/ tinha 2 cópias do jQuery e
    # /cursos-e-podcasts-de-empreendedorismo/ chegou a 9.
    pattern = (
        r'<!-- COMECA ATUALIZAR DAQUI -->'
        r'.*</table>'              # guloso: vai até o ÚLTIMO </table>
        r'(?:\s*<script[\s\S]*?</script>)*'  # e os scripts que sobraram depois
    )
    novo_conteudo, count = re.subn(
        pattern,
        lambda _: nova_tabela_html,   # lambda: evita interpretar \1, \g<> etc.
        conteudo,
        flags=re.DOTALL
    )

    if count == 0:
        print("Aviso: não foi encontrado o marcador '<!-- COMECA ATUALIZAR DAQUI -->' com tabela associada.")
        return False

    # Rede de segurança: o padrão é guloso e vai até o ÚLTIMO </table> da
    # página. Se alguém acrescentar outra tabela DEPOIS do bloco automático,
    # ela seria engolida pela substituição.
    #
    # Hoje nenhuma página tem tabela extra, mas isso pode mudar a qualquer
    # edição manual. Melhor recusar a publicação do que apagar conteúdo que
    # alguém escreveu — o conteúdo perdido não seria recuperável pelo log.
    trecho_antigo = re.search(pattern, conteudo, flags=re.DOTALL).group(0)
    tabelas_removidas = len(re.findall(r'<table', trecho_antigo))

    if tabelas_removidas > 1:
        print(f"❌ A área a substituir contém {tabelas_removidas} tabelas, e a "
              f"automação gera apenas uma.")
        print("   Isso indica conteúdo manual depois do bloco automático, que "
              "seria apagado.")
        print("   Publicação cancelada. Revise a página no WordPress: o bloco "
              "automático deve ser o último elemento antes do rodapé.")
        return False

    data = {"content": novo_conteudo}
    resp_update = requests.post(
        f"https://inova.ufpr.br/wp-json/wp/v2/pages/{page_id}",
        auth=HTTPBasicAuth(WP_USER, WP_APP_PASSWORD),
        headers=headers,
        json=data
    )

    print("Código de status da atualização:", resp_update.status_code)
    try:
        print("Resposta da atualização:")
        print(resp_update.json())
    except Exception:
        print("Erro ao interpretar JSON da atualização:", resp_update.text)

    return resp_update.status_code == 200

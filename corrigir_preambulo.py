# -*- coding: utf-8 -*-
"""
Copia o preâmbulo de uma página modelo para as páginas que estão sem ele.

O preâmbulo é tudo que vem ANTES do marcador <!-- COMECA ATUALIZAR DAQUI -->:
o bloco <style> que centraliza as colunas da tabela e o campo "Busque por uma
organização". Ele não é gerado pela automação — fica no conteúdo da página, e
por isso as páginas criadas pelo criar_pagina_wp.py nasceram sem ele.

Sintomas de uma página sem preâmbulo:
  - colunas UF/Cidade/Categoria alinhadas à esquerda, e não centralizadas
  - campo de busca ausente

Segurança: o conteúdo atual é salvo em backups/ antes de qualquer escrita.

Uso:
    python corrigir_preambulo.py --dry-run
    python corrigir_preambulo.py
    python corrigir_preambulo.py --modelo INDTECHS
"""

import os
import re
import sys
import json
import argparse
from datetime import datetime

for _fluxo in (sys.stdout, sys.stderr):
    try:
        _fluxo.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))

import rede  # noqa: F401  força IPv4 (runners do GitHub não têm IPv6)
import requests
from requests.auth import HTTPBasicAuth
from dotenv import load_dotenv
from urllib.parse import urlparse

import config

RAIZ = os.path.dirname(os.path.abspath(__file__))
DIR_BACKUPS = os.path.join(RAIZ, "backups")
load_dotenv(dotenv_path=os.path.join(RAIZ, "credenciais", ".env"))

API = "https://inova.ufpr.br/wp-json/wp/v2"
CABECALHOS = {"User-Agent": "Mozilla/5.0", "Content-Type": "application/json"}

MARCADOR = "<!-- COMECA ATUALIZAR DAQUI -->"

# Página cujo preâmbulo serve de referência. Precisa ter o CSS e o campo de
# busca no formato desejado.
MODELO_PADRAO = "INDTECHS"


def _auth():
    usuario = os.getenv("WP_USER")
    senha = os.getenv("WP_APP_PASSWORD")
    if not usuario or not senha:
        print("❌ WP_USER e WP_APP_PASSWORD não definidos.")
        sys.exit(1)
    return HTTPBasicAuth(usuario, senha)


def slug_da_url(url):
    return urlparse(url).path.strip("/").split("/")[-1]


def obter_pagina(slug):
    """Página completa, com content.raw."""
    resposta = rede.com_retentativa(
        lambda: requests.get(
            f"{API}/pages",
            params={"slug": slug, "context": "edit"},
            auth=_auth(), headers=CABECALHOS, timeout=30,
        ),
        descricao=f"obter página '{slug}'",
    )
    if resposta.status_code != 200:
        return None
    paginas = resposta.json()
    return paginas[0] if paginas else None


def partir_conteudo(conteudo):
    """
    Divide o conteúdo em (preâmbulo, bloco, sufixo).

    preâmbulo = antes do marcador (CSS + campo de busca)
    bloco     = do marcador até o fim da última </table>
    sufixo    = o que vem depois (fechamento de div/body)

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
    """True se a página já tem o campo de busca e o CSS de centralização."""
    tem_busca = 'id="search"' in conteudo
    tem_css = re.search(r'#organization_table\s+td:nth-child\(\d\)\s*\{[^}]*'
                        r'text-align:\s*center', conteudo, re.S) is not None
    return tem_busca and tem_css


def salvar_backup(slug, pagina, pasta):
    os.makedirs(pasta, exist_ok=True)
    caminho = os.path.join(pasta, f"{slug}.json")
    with open(caminho, "w", encoding="utf-8") as f:
        json.dump({
            "slug": slug,
            "pagina_id": pagina["id"],
            "salvo_em": datetime.now().isoformat(timespec="seconds"),
            "conteudo": pagina.get("content", {}).get("raw", ""),
        }, f, ensure_ascii=False, indent=1)
    return caminho


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true",
                        help="mostra o que faria, sem alterar as páginas")
    parser.add_argument("--modelo", default=MODELO_PADRAO,
                        help=f"aba cuja página serve de modelo (padrão: {MODELO_PADRAO})")
    args = parser.parse_args()

    print("=" * 64)
    print("🎨 PREÂMBULO DAS PÁGINAS (CSS + campo de busca)")
    print("=" * 64)

    # --- Lê o modelo ---
    url_modelo = config.ABAS_LINKS.get(args.modelo)
    if not url_modelo:
        print(f"❌ Aba modelo '{args.modelo}' não está em ABAS_LINKS.")
        sys.exit(1)

    pagina_modelo = obter_pagina(slug_da_url(url_modelo))
    if not pagina_modelo:
        print(f"❌ Página modelo '{args.modelo}' não encontrada.")
        sys.exit(1)

    conteudo_modelo = pagina_modelo.get("content", {}).get("raw", "")
    partes = partir_conteudo(conteudo_modelo)
    if not partes:
        print(f"❌ A página modelo não tem o marcador {MARCADOR}.")
        sys.exit(1)

    preambulo, _, sufixo = partes

    if not tem_preambulo(conteudo_modelo):
        print(f"❌ A página modelo '{args.modelo}' não tem o CSS e o campo de "
              f"busca esperados. Escolha outra com --modelo.")
        sys.exit(1)

    print(f"📄 Modelo: {args.modelo}")
    print(f"   preâmbulo: {len(preambulo)} chars | sufixo: {len(sufixo)} chars")

    # --- Verifica cada página ---
    carimbo = datetime.now().strftime("%Y%m%d-%H%M%S")
    pasta_backup = os.path.join(DIR_BACKUPS, f"preambulo-{carimbo}")

    sem_preambulo = []
    ok = 0

    print("\n🔍 Verificando páginas...")
    for aba, url in sorted(config.ABAS_LINKS.items()):
        if aba == args.modelo:
            continue

        # Abas com layout próprio não seguem este preâmbulo.
        if aba in (config.ABA_PITCHS, config.ABA_VIDEOS):
            continue

        slug = slug_da_url(url)
        pagina = obter_pagina(slug)
        if not pagina:
            print(f"   ⚠️  {aba}: página não encontrada")
            continue

        conteudo = pagina.get("content", {}).get("raw", "")
        if tem_preambulo(conteudo):
            ok += 1
            continue

        sem_preambulo.append((aba, slug, pagina, conteudo))

    print(f"   {ok} página(s) já com o preâmbulo correto")

    if not sem_preambulo:
        print("\n✅ Todas as páginas já estão padronizadas.")
        return

    print(f"\n🎯 {len(sem_preambulo)} página(s) a corrigir:")
    for aba, slug, _, _ in sem_preambulo:
        print(f"   - {aba}  (/{slug}/)")

    if args.dry_run:
        print("\n(--dry-run: nada foi alterado)")
        return

    print()
    for aba, slug, pagina, conteudo in sem_preambulo:
        partes = partir_conteudo(conteudo)
        if not partes:
            print(f"   ✗ {aba}: sem o marcador, pulando")
            continue

        _, bloco, _ = partes
        novo_conteudo = preambulo + bloco + sufixo

        backup = salvar_backup(slug, pagina, pasta_backup)

        resposta = rede.com_retentativa(
            lambda: requests.post(
                f"{API}/pages/{pagina['id']}",
                auth=_auth(), headers=CABECALHOS,
                json={"content": novo_conteudo},
                timeout=30,
            ),
            descricao=f"gravar preâmbulo em /{slug}/",
        )

        if resposta.status_code == 200:
            print(f"   ✓ {aba}: preâmbulo aplicado")
        else:
            print(f"   ✗ {aba}: falha (HTTP {resposta.status_code}). "
                  f"Backup em {backup}")

    print(f"\n💾 Backups em backups/preambulo-{carimbo}/")
    print("\nPara desfazer uma página:")
    print(f"   python backup_paginas.py --restaurar "
          f"backups/preambulo-{carimbo}/<slug>.json")


if __name__ == "__main__":
    main()

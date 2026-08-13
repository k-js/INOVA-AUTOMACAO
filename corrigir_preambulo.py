# -*- coding: utf-8 -*-
"""
Padroniza o preâmbulo das páginas a partir de uma página modelo.

O preâmbulo é tudo que vem ANTES do marcador <!-- COMECA ATUALIZAR DAQUI -->.
Ele não é gerado pela automação — fica no conteúdo da página, fora do alcance
da publicação diária —, e mistura duas coisas bem diferentes:

  ESTRUTURA (igual em todas): o <style> que centraliza as colunas da tabela
             e o campo "Busque por uma organização"
  CONTEÚDO  (de cada página): a imagem de capa e o texto de apresentação

Só a ESTRUTURA é copiada do modelo. Levar o conteúdo junto põe a capa e a
descrição do modelo em todas as outras páginas.

Duas situações são corrigidas:
  - página sem o CSS/campo de busca (colunas à esquerda, sem busca)
  - página exibindo a capa e o texto do modelo, por cópia indevida anterior

Uma página com capa e descrição PRÓPRIAS é listada e pulada, para não perder
conteúdo editorial. Use --forcar para sobrescrever mesmo assim.

Segurança: o conteúdo atual é salvo em backups/ antes de qualquer escrita.

Uso:
    python corrigir_preambulo.py --dry-run
    python corrigir_preambulo.py
    python corrigir_preambulo.py --modelo INDTECHS
"""

import os
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
# Mesmas funções usadas por criar_pagina_wp.py, para que página nova e página
# corrigida nasçam do mesmo entendimento do que é o preâmbulo.
from preambulo import (
    MARCADOR,
    ABA_MODELO,
    partir_conteudo,
    tem_preambulo,
    descrever_conteudo,
    preambulo_estrutural,
    conferir_preambulo,
    herdou_do_modelo,
)

RAIZ = os.path.dirname(os.path.abspath(__file__))
DIR_BACKUPS = os.path.join(RAIZ, "backups")
load_dotenv(dotenv_path=os.path.join(RAIZ, "credenciais", ".env"))

API = "https://inova.ufpr.br/wp-json/wp/v2"
CABECALHOS = {"User-Agent": "Mozilla/5.0", "Content-Type": "application/json"}


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
    parser.add_argument("--modelo", default=ABA_MODELO,
                        help=f"aba cuja página serve de modelo (padrão: {ABA_MODELO})")
    parser.add_argument("--forcar", action="store_true",
                        help="corrige mesmo as páginas cujo preâmbulo tem "
                             "conteúdo próprio (capa/descrição) — ele será perdido")
    parser.add_argument("--mostrar-modelo", action="store_true",
                        help="imprime o preâmbulo que seria aplicado, para conferência")
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

    if not tem_preambulo(conteudo_modelo):
        print(f"❌ A página modelo '{args.modelo}' não tem o CSS e o campo de "
              f"busca esperados. Escolha outra com --modelo.")
        sys.exit(1)

    # Do preâmbulo do modelo tira-se só a capa. O resto (os <style>, o botão
    # VOLTAR, o campo de busca) é igual em todas as páginas e vai junto.
    #
    # A tabela e o que vem depois dela (fechamento das tags e os <script> de
    # filtro) continuam sendo os de cada página: a correção mexe só no pedaço
    # que está errado.
    preambulo_modelo = partes[0]
    preambulo = preambulo_estrutural(preambulo_modelo)

    print(f"📄 Modelo: {args.modelo}")
    print(f"   preâmbulo do modelo: {len(preambulo_modelo)} chars")
    print(f"   capa removida:       {len(preambulo_modelo) - len(preambulo)} chars")
    print(f"   a aplicar:           {len(preambulo)} chars")

    if args.mostrar_modelo:
        print("\n--- preâmbulo a aplicar ---")
        print(preambulo)
        print("--- fim ---\n")

    problemas = conferir_preambulo(preambulo)
    if problemas:
        print(f"\n❌ O preâmbulo de '{args.modelo}' não passou na conferência:")
        for p in problemas:
            print(f"   - {p}")
        # O preâmbulo vai para o log mesmo sem --mostrar-modelo: sem ver o
        # HTML não dá para descobrir por que a limpeza não deu conta.
        if not args.mostrar_modelo:
            print("\n--- preâmbulo que seria aplicado ---")
            print(preambulo)
            print("--- fim ---")
        print("\n   Nada foi alterado.")
        sys.exit(1)

    # --- Verifica cada página ---
    carimbo = datetime.now().strftime("%Y%m%d-%H%M%S")
    pasta_backup = os.path.join(DIR_BACKUPS, f"preambulo-{carimbo}")

    # (aba, slug, pagina, conteudo, motivo, proprio)
    #   motivo  = por que precisa de correção
    #   proprio = conteúdo editorial da própria página que seria perdido
    a_corrigir = []
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
        partes_pagina = partir_conteudo(conteudo)
        pre_pagina = partes_pagina[0] if partes_pagina else ""

        # Página exibindo a capa e o texto do modelo: cópia indevida a desfazer.
        if herdou_do_modelo(pre_pagina, preambulo_modelo):
            a_corrigir.append((aba, slug, pagina, conteudo,
                               f"exibindo capa/texto de {args.modelo}", []))
            continue

        if tem_preambulo(conteudo):
            ok += 1
            continue

        a_corrigir.append((aba, slug, pagina, conteudo,
                           "sem CSS/campo de busca", descrever_conteudo(pre_pagina)))

    print(f"   {ok} página(s) já com o preâmbulo correto")

    if not a_corrigir:
        print("\n✅ Todas as páginas já estão padronizadas.")
        return

    print(f"\n🎯 {len(a_corrigir)} página(s) a corrigir:")
    for aba, slug, _, _, motivo, proprio in a_corrigir:
        marca = f"  ⚠️  perderia: {', '.join(proprio)}" if proprio else ""
        print(f"   - {aba}  (/{slug}/)  — {motivo}{marca}")

    if any(proprio for *_, proprio in a_corrigir) and not args.forcar:
        print("\n⚠️  As páginas marcadas têm conteúdo próprio antes da tabela "
              "(capa ou descrição).\n"
              "   Trocar o preâmbulo apagaria esse conteúdo, então elas serão "
              "puladas.\n"
              "   Use --forcar se quiser sobrescrever mesmo assim.")

    if args.dry_run:
        print("\n(--dry-run: nada foi alterado)")
        return

    print()
    for aba, slug, pagina, conteudo, motivo, proprio in a_corrigir:
        if proprio and not args.forcar:
            print(f"   ⏭️  {aba}: pulada (perderia {', '.join(proprio)})")
            continue

        partes = partir_conteudo(conteudo)
        if not partes:
            print(f"   ✗ {aba}: sem o marcador, pulando")
            continue

        # sufixo da PRÓPRIA página: preserva os <script> de filtro dela.
        _, bloco, sufixo = partes
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

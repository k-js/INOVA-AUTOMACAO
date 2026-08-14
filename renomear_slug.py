# -*- coding: utf-8 -*-
"""
Padroniza o slug das páginas cujo endereço não bate com o nome da categoria.

    /biotechs/     ->  /deeptechs/     (a página já se chama "Deeptechs")
    /health-tech/  ->  /healthtechs/
    /pet-techs/    ->  /pettechs/

Por que isto é diferente de trocar a URL de um botão
----------------------------------------------------
Renomear o slug de uma página publicada faz o endereço ANTIGO deixar de
existir. Quem já compartilhou o link, e o Google, apontam para o endereço
antigo. Se ele passar a dar 404, o estrago não se desfaz renomeando de volta:
quem clicou no meio do caminho já levou o 404, e a reindexação leva semanas.

O que salva é o redirecionamento. O WordPress guarda o slug anterior em
_wp_old_slug ao renomear e responde 301 do antigo para o novo — mas este site
NÃO tem plugin de redirecionamento (verificado em /wp-json/: nenhum Redirection,
Rank Math ou Yoast), então tudo depende desse comportamento nativo, que não dá
para provar sem antes renomear alguma coisa.

Por isso cada renome aqui se confere e se desfaz sozinho:

    1. guarda um backup com id, slug e título
    2. renomeia
    3. confere que a página responde no endereço novo
    4. confere que o endereço ANTIGO responde 301 para o novo
    5. se 3 ou 4 falharem, desfaz na hora e para -- as páginas seguintes
       nem chegam a ser tocadas

A janela de exposição é de segundos, e não "até alguém reparar". Se o
_wp_old_slug não funcionar neste site, descobrimos na primeira página, com ela
já restaurada.

A conferência do endereço antigo usa um parâmetro aleatório na URL para furar
cache: uma página servida do cache responderia 200 e esconderia um 404.

Uso:
    python renomear_slug.py --dry-run        # mostra o que faria
    python renomear_slug.py                  # aplica, com conferência
    python renomear_slug.py --apenas biotechs
    python renomear_slug.py --listar-backups
    python renomear_slug.py --desfazer backups/slug-biotechs-<data>.json
"""

import os
import re
import sys
import json
import time
import random
import argparse
from datetime import datetime

for _fluxo in (sys.stdout, sys.stderr):
    try:
        _fluxo.reconfigure(encoding="utf-8", errors="replace",
                           line_buffering=True)
    except (AttributeError, ValueError):
        pass

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))

import rede  # noqa: F401  força IPv4 (runners do GitHub não têm IPv6)
import requests

import botoes_wp

SITE = botoes_wp.SITE
API = botoes_wp.API
CAMINHO_CONFIG = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              "src", "config.py")

# (slug atual, slug novo, aba em ABAS_LINKS)
#
# Levantados em docs/PENDENCIAS.md, item 3, Caso B. Os títulos das páginas
# foram conferidos na API antes de entrar aqui: a de /biotechs/ já se chama
# "Deeptechs", ou seja o slug é resíduo de uma renomeação antiga da categoria,
# e não uma página sobre outro assunto.
RENOMES = [
    ("biotechs", "deeptechs", "DEEPTECHS"),
    ("health-tech", "healthtechs", "HEALTHTECHS"),
    ("pet-techs", "pettechs", "PETTECHS"),
]

# Quanto esperar entre renomear e conferir. O WordPress grava o _wp_old_slug na
# mesma transação, mas o site tem Wordfence na frente e uma folga evita ler um
# estado intermediário.
ESPERA_ANTES_DE_CONFERIR = 3


# ---------------------------------------------------------------------
# Conferências
# ---------------------------------------------------------------------
def _sem_cache(url):
    """Acrescenta um parâmetro aleatório, para não ler uma resposta de cache."""
    separador = "&" if "?" in url else "?"
    return f"{url}{separador}_cb={random.randint(100000, 999999)}"


def responde_ok(slug):
    """True se a página responde 200 no endereço informado."""
    try:
        resposta = requests.get(
            _sem_cache(f"{SITE}/{slug}/"), timeout=30, allow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0"},
        )
        return resposta.status_code == 200
    except Exception as erro:
        print(f"      ! falha ao consultar /{slug}/: {erro}")
        return False


def redireciona_para(slug_antigo, slug_novo):
    """
    Confere que o endereço antigo responde 301/302 apontando para o novo.

    Devolve (ok, descrição). A descrição entra no relato quando falha, porque
    é ela que diz se o problema foi 404 (o redirecionamento não existe) ou 200
    (o cache está mascarando o estado real).
    """
    url = _sem_cache(f"{SITE}/{slug_antigo}/")
    try:
        resposta = requests.get(
            url, timeout=30, allow_redirects=False,
            headers={"User-Agent": "Mozilla/5.0"},
        )
    except Exception as erro:
        return False, f"falha ao consultar: {erro}"

    codigo = resposta.status_code
    destino = resposta.headers.get("Location", "")

    if codigo in (301, 302, 307, 308):
        if f"/{slug_novo}" in destino:
            return True, f"{codigo} -> {destino}"
        return False, f"{codigo}, mas para {destino or '(sem Location)'}"

    if codigo == 404:
        return False, "404 — o endereço antigo deixou de existir"

    return False, f"HTTP {codigo} (esperava um redirecionamento)"


# ---------------------------------------------------------------------
# Escrita
# ---------------------------------------------------------------------
def gravar_slug(pagina_id, slug):
    """Grava o slug da página. Devolve (codigo_http, slug_resultante)."""
    resposta = rede.com_retentativa(
        lambda: requests.post(
            f"{API}/pages/{pagina_id}",
            auth=botoes_wp._auth(), headers=botoes_wp.CABECALHOS,
            json={"slug": slug}, timeout=30,
        ),
        descricao=f"gravar slug '{slug}' na página {pagina_id}",
    )
    resultante = ""
    try:
        resultante = resposta.json().get("slug", "")
    except Exception:
        pass
    return resposta.status_code, resultante


def salvar_backup(pagina, slug_novo):
    """Guarda o que é preciso para desfazer. Devolve o caminho."""
    os.makedirs(botoes_wp.DIR_BACKUPS, exist_ok=True)
    carimbo = datetime.now().strftime("%Y%m%d-%H%M%S")
    caminho = os.path.join(botoes_wp.DIR_BACKUPS,
                           f"slug-{pagina['slug']}-{carimbo}.json")

    with open(caminho, "w", encoding="utf-8") as f:
        json.dump({
            "pagina_id": pagina["id"],
            "slug_anterior": pagina["slug"],
            "slug_novo": slug_novo,
            "titulo": pagina.get("title", {}).get("raw")
                      or pagina.get("title", {}).get("rendered", ""),
            "link_anterior": pagina.get("link", ""),
            "salvo_em": datetime.now().isoformat(timespec="seconds"),
        }, f, ensure_ascii=False, indent=1)

    return caminho


def atualizar_config(aba, url_nova):
    """
    Troca a URL da aba em ABAS_LINKS, sem remontar o bloco inteiro.

    Substituição pontual de propósito: reescrever ABAS_LINKS todo apagaria os
    comentários que explicam cada exceção.
    """
    with open(CAMINHO_CONFIG, encoding="utf-8") as f:
        texto = f.read()

    padrao = re.compile(rf'("{re.escape(aba)}":\s*)"[^"]*"')
    if not padrao.search(texto):
        return False, f"não achei \"{aba}\" em ABAS_LINKS"

    novo = padrao.sub(lambda m: f'{m.group(1)}"{url_nova}"', texto, count=1)
    if novo == texto:
        return False, "a URL já estava atualizada"

    with open(CAMINHO_CONFIG, "w", encoding="utf-8") as f:
        f.write(novo)
    return True, ""


# ---------------------------------------------------------------------
# Operação
# ---------------------------------------------------------------------
def renomear(slug_antigo, slug_novo, aba, dry_run=False):
    """
    Renomeia uma página e confere o resultado, desfazendo se algo não bater.

    Devolve True se a página ficou no endereço novo com o antigo redirecionando.
    """
    print(f"\n/{slug_antigo}/  ->  /{slug_novo}/   ({aba})")

    pagina = botoes_wp.obter_pagina(slug_antigo)
    if not pagina:
        print(f"   ❌ página '{slug_antigo}' não encontrada — pulando")
        return False

    if pagina.get("status") != "publish":
        print(f"   ❌ a página está como '{pagina.get('status')}' — pulando")
        return False

    titulo = (pagina.get("title", {}).get("raw")
              or pagina.get("title", {}).get("rendered", ""))
    print(f"   id {pagina['id']} · \"{titulo}\"")

    # Slug ocupado seria pior que não fazer nada: o WordPress aceitaria a
    # escrita e resolveria o conflito sozinho, criando /deeptechs-2/.
    if botoes_wp.obter_pagina(slug_novo):
        print(f"   ❌ já existe uma página em /{slug_novo}/ — pulando")
        return False

    if dry_run:
        print("   (--dry-run: nada foi alterado)")
        return True

    backup = salvar_backup(pagina, slug_novo)
    print(f"   💾 {backup}")

    codigo, resultante = gravar_slug(pagina["id"], slug_novo)
    if codigo != 200:
        print(f"   ❌ falha ao gravar (HTTP {codigo}) — nada mudou")
        return False

    if resultante != slug_novo:
        # O WordPress desambigua sozinho quando o slug colide. Aceitar isso em
        # silêncio deixaria a página em /deeptechs-2/ com o config apontando
        # para /deeptechs/.
        print(f"   ❌ o WordPress gravou '{resultante}', não '{slug_novo}'")
        print("      desfazendo...")
        gravar_slug(pagina["id"], slug_antigo)
        return False

    time.sleep(ESPERA_ANTES_DE_CONFERIR)

    # --- Conferência 1: a página responde no endereço novo ---
    if not responde_ok(slug_novo):
        print(f"   ❌ /{slug_novo}/ não respondeu 200 — desfazendo...")
        gravar_slug(pagina["id"], slug_antigo)
        print(f"   ↩️  de volta em /{slug_antigo}/")
        return False

    print(f"   ✅ /{slug_novo}/ responde")

    # --- Conferência 2: o endereço antigo redireciona (a que importa) ---
    ok, detalhe = redireciona_para(slug_antigo, slug_novo)
    if not ok:
        print(f"   ❌ /{slug_antigo}/ NÃO redireciona: {detalhe}")
        print("      link já compartilhado quebraria — desfazendo...")
        gravar_slug(pagina["id"], slug_antigo)
        time.sleep(ESPERA_ANTES_DE_CONFERIR)
        print(f"   ↩️  de volta em /{slug_antigo}/ "
              f"({'responde' if responde_ok(slug_antigo) else 'CONFERIR À MÃO'})")
        return False

    print(f"   ✅ /{slug_antigo}/ redireciona: {detalhe}")

    alterou, erro = atualizar_config(aba, f"{SITE}/{slug_novo}/")
    print(f"   {'✅ src/config.py atualizado' if alterou else f'⚠️  config: {erro}'}")

    return True


def desfazer(caminho_backup):
    """Devolve a página ao slug anterior."""
    with open(caminho_backup, encoding="utf-8") as f:
        dados = json.load(f)

    print(f"Devolvendo a página {dados['pagina_id']} para "
          f"/{dados['slug_anterior']}/ ...")

    codigo, resultante = gravar_slug(dados["pagina_id"], dados["slug_anterior"])
    if codigo != 200:
        print(f"❌ falha (HTTP {codigo})")
        sys.exit(1)

    print(f"✅ agora em /{resultante}/")
    print("\n⚠️  src/config.py NÃO foi alterado por esta operação. "
          "Confira a URL da aba correspondente em ABAS_LINKS.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true",
                        help="mostra o que faria, sem alterar nada")
    parser.add_argument("--apenas", metavar="SLUG",
                        help="renomeia só a página deste slug atual")
    parser.add_argument("--listar-backups", action="store_true",
                        help="lista os backups de renomeação e sai")
    parser.add_argument("--desfazer", metavar="ARQUIVO",
                        help="devolve a página ao slug anterior")
    args = parser.parse_args()

    if args.listar_backups:
        arquivos = [b for b in botoes_wp.listar_backups()
                    if b.startswith("slug-")]
        if not arquivos:
            print("Nenhuma renomeação registrada ainda.")
            return
        print("Renomeações (mais recente primeiro):\n")
        for b in arquivos:
            print(f"   backups/{b}")
        print("\nPara desfazer:")
        print(f"   python renomear_slug.py --desfazer backups/{arquivos[0]}")
        return

    if args.desfazer:
        desfazer(args.desfazer)
        return

    print("=" * 64)
    print("🔗 PADRONIZAÇÃO DOS SLUGS DIVERGENTES")
    print("=" * 64)

    alvos = RENOMES
    if args.apenas:
        alvos = [r for r in RENOMES if r[0] == args.apenas]
        if not alvos:
            print(f"❌ '{args.apenas}' não está na lista. Slugs tratados: "
                  + ", ".join(r[0] for r in RENOMES))
            sys.exit(1)

    if args.dry_run:
        print("\n(--dry-run: nada será alterado)")

    feitos = []
    for slug_antigo, slug_novo, aba in alvos:
        if renomear(slug_antigo, slug_novo, aba, dry_run=args.dry_run):
            feitos.append((slug_antigo, slug_novo))
            continue

        # Para na primeira falha, de propósito. Se o redirecionamento nativo
        # não funcionar neste site, ele não vai funcionar na página seguinte —
        # e insistir só multiplicaria o estrago.
        if not args.dry_run:
            print("\n" + "=" * 64)
            print(f"⛔ PAREI em /{slug_antigo}/. As páginas seguintes não "
                  "foram tocadas.")
            if feitos:
                print("\nJá renomeadas e conferidas nesta execução:")
                for a, n in feitos:
                    print(f"   /{a}/ -> /{n}/")
                print("\nElas estão íntegras (endereço novo respondendo, "
                      "antigo redirecionando).")
                print("Para reverter mesmo assim: "
                      "python renomear_slug.py --listar-backups")
            sys.exit(1)

    print("\n" + "=" * 64)
    if args.dry_run:
        print(f"{len(feitos)} página(s) seriam renomeadas.")
        return

    print(f"✅ {len(feitos)} página(s) renomeadas e conferidas")
    for a, n in feitos:
        print(f"   /{a}/ -> /{n}/   (antigo redirecionando)")

    if feitos:
        print("\nFalta apontar os botões de /startups/ para os endereços novos:")
        print("   python sincronizar_botoes.py --normalizar-urls")
        print("\nPara reverter:")
        print("   python renomear_slug.py --listar-backups")


if __name__ == "__main__":
    main()

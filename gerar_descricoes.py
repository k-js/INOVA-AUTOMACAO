# -*- coding: utf-8 -*-
"""
Propõe e aplica as descrições das páginas que estão sem.

A descrição é a frase embaixo da capa, acima da tabela. Ela é escrita a partir
das categorias que a própria página já lista — não do conhecimento do modelo
sobre o setor. Veja src/descricao.py.

Há dois modos de uso.

AUTOMÁTICO — é o que roda no dia a dia, no fim do "Atualizar INOVA":

    python gerar_descricoes.py --auto

    Gera e grava na mesma execução. Nenhuma revisão humana. Roda depois da
    publicação porque as categorias saem da tabela da página, que só existe
    depois que a publicação a preencheu — na criação a página está vazia.

    Sem ninguém lendo antes, o que segura a qualidade é:
      - a frase só pode usar as categorias daquela página (src/descricao.py)
      - conferir() recusa frase fora do padrão, e tenta de novo
      - página que JÁ tem descrição nunca é sobrescrita — inclusive uma
        corrigida à mão, que portanto prevalece para sempre
      - backup do conteúdo anterior antes de cada escrita

REVISADO — para rodar em lote ou quando quiser conferir antes:

    1. python gerar_descricoes.py --propor    grava descricoes.json, não
                                              toca no site
    2. (você lê o arquivo e corrige o que quiser)
    3. python gerar_descricoes.py --aplicar   copia o arquivo para o site,
                                              sem gerar nada

Precisa de GROQ_API_KEY (Secret na Action, ou credenciais/.env) para gerar.
O --aplicar sozinho não fala com o modelo.

    python gerar_descricoes.py --listar-modelos
"""

import os
import re
import sys
import json
import html
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

import config
import descricao
import preambulo as P

RAIZ = os.path.dirname(os.path.abspath(__file__))
DIR_BACKUPS = os.path.join(RAIZ, "backups")
ARQUIVO = os.path.join(RAIZ, "descricoes.json")
load_dotenv(dotenv_path=os.path.join(RAIZ, "credenciais", ".env"))

API = "https://inova.ufpr.br/wp-json/wp/v2"
CABECALHOS = {"User-Agent": "Mozilla/5.0", "Content-Type": "application/json"}

# Quantas descrições existentes mandar ao modelo como referência de estilo.
QUANTOS_EXEMPLOS = 6

# Abas com layout próprio, que não seguem este formato de página.
ABAS_FORA = {config.ABA_PITCHS, config.ABA_VIDEOS}


def _auth():
    usuario, senha = os.getenv("WP_USER"), os.getenv("WP_APP_PASSWORD")
    if not usuario or not senha:
        print("❌ WP_USER e WP_APP_PASSWORD não definidos.")
        sys.exit(1)
    return HTTPBasicAuth(usuario, senha)


def _chave_groq():
    chave = os.getenv("GROQ_API_KEY")
    if not chave:
        print("❌ GROQ_API_KEY não definida.\n"
              "   Na Action vem dos Secrets; localmente, de credenciais/.env\n"
              "   Crie a chave em https://console.groq.com → API Keys")
        sys.exit(1)
    return chave


def obter_pagina(slug):
    """Página com content.raw, ou None."""
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


def slug_da_url(url):
    return url.rstrip("/").rsplit("/", 1)[-1]


def levantar():
    """
    Percorre as páginas e separa as que têm descrição das que não têm.

    Retorna (sem_descricao, exemplos):
      sem_descricao  [(aba, slug, pagina, conteudo, categorias)]
      exemplos       descrições existentes, para servirem de referência
    """
    sem_descricao, exemplos = [], []

    for aba, url in sorted(config.ABAS_LINKS.items()):
        if aba in ABAS_FORA:
            continue

        slug = slug_da_url(url)
        pagina = obter_pagina(slug)
        if not pagina:
            print(f"   ⚠️  {aba}: página não encontrada")
            continue

        conteudo = pagina.get("content", {}).get("raw", "")
        partes = P.partir_conteudo(conteudo)
        if not partes:
            print(f"   ⚠️  {aba}: sem o marcador de publicação")
            continue

        texto = P.texto_editorial(partes[0])
        if texto:
            exemplos.append(texto)
            continue

        categorias = descricao.categorias_da_pagina(conteudo)
        if not categorias:
            print(f"   ⚠️  {aba}: sem categorias na tabela — não dá para "
                  f"descrever a partir dos dados, pulando")
            continue

        sem_descricao.append((aba, slug, pagina, conteudo, categorias))

    return sem_descricao, exemplos


def propor(args):
    chave = _chave_groq()
    modelo = args.modelo or descricao.MODELO_PADRAO

    print("🔍 Levantando páginas...")
    sem_descricao, exemplos = levantar()
    print(f"   {len(exemplos)} página(s) com descrição (servem de referência)")

    if not sem_descricao:
        print("\n✅ Todas as páginas já têm descrição.")
        return {}

    print(f"\n🎯 {len(sem_descricao)} página(s) sem descrição")
    print(f"🤖 Modelo: {modelo}\n")

    # As mais longas costumam ser as mais bem escritas, e ancoram melhor o tom.
    referencia = sorted(exemplos, key=len, reverse=True)[:QUANTOS_EXEMPLOS]

    propostas = {}
    for aba, slug, _, _, categorias in sem_descricao:
        resumo = ", ".join(f"{k} ({n})" for k, n in categorias.most_common(5))
        print(f"   {aba}")
        print(f"      categorias: {resumo}")

        texto, problemas = descricao.gerar(aba, categorias, referencia, chave, modelo)
        if problemas:
            print(f"      ✗ {'; '.join(problemas)}")
            continue

        print(f"      → {texto}")
        propostas[aba] = {
            "texto": texto,
            "categorias": [f"{k} ({n})" for k, n in categorias.most_common(10)],
        }
        print()

    if not propostas:
        print("\n❌ Nenhuma proposta aproveitável.")
        # No modo automático isso não pode derrubar a publicação diária: a
        # descrição é um acréscimo, e a página funciona sem ela.
        if not args.auto:
            sys.exit(1)
        return {}

    with open(ARQUIVO, "w", encoding="utf-8") as f:
        json.dump({
            "gerado_em": datetime.now().isoformat(timespec="seconds"),
            "modelo": modelo,
            "descricoes": propostas,
        }, f, ensure_ascii=False, indent=1)

    print(f"💾 {len(propostas)} proposta(s) em descricoes.json")
    if not args.auto:
        print("\n   LEIA e corrija o arquivo antes de aplicar. Compare cada frase")
        print("   com as categorias listadas ao lado dela — é para isso que elas")
        print("   estão no arquivo.")

    return propostas


def inserir(preambulo_texto, frase):
    """
    Encaixa a descrição como bloco do Gutenberg, logo antes do <head>.

    É onde ela fica nas páginas que já têm: depois da capa e do botão VOLTAR,
    antes do preâmbulo técnico. Retorna None se não houver onde encaixar.
    """
    bloco = ("<!-- wp:paragraph -->\n"
             f"<p>{html.escape(frase, quote=False)}</p>\n"
             "<!-- /wp:paragraph -->\n\n")

    i = preambulo_texto.lower().find("<head")
    if i == -1:
        return None
    return preambulo_texto[:i] + bloco + preambulo_texto[i:]


def aplicar(args):
    if not os.path.exists(ARQUIVO):
        print(f"❌ {ARQUIVO} não existe. Rode --propor primeiro.")
        sys.exit(1)

    with open(ARQUIVO, encoding="utf-8") as f:
        dados = json.load(f)
    propostas = dados.get("descricoes", {})

    print(f"📄 descricoes.json — {len(propostas)} descrição(ões), "
          f"geradas em {dados.get('gerado_em', '?')} por {dados.get('modelo', '?')}\n")

    carimbo = datetime.now().strftime("%Y%m%d-%H%M%S")
    pasta_backup = os.path.join(DIR_BACKUPS, f"descricao-{carimbo}")
    aplicadas = 0

    for aba, item in sorted(propostas.items()):
        frase = item.get("texto", "").strip()
        url = config.ABAS_LINKS.get(aba)
        if not frase or not url:
            print(f"   ✗ {aba}: sem texto ou fora de ABAS_LINKS")
            continue

        slug = slug_da_url(url)
        pagina = obter_pagina(slug)
        if not pagina:
            print(f"   ✗ {aba}: página não encontrada")
            continue

        conteudo = pagina.get("content", {}).get("raw", "")
        partes = P.partir_conteudo(conteudo)
        if not partes:
            print(f"   ✗ {aba}: sem o marcador de publicação")
            continue

        pre, bloco_tabela, sufixo = partes

        # Nunca por cima de um texto existente: se apareceu descrição desde a
        # proposta, é decisão de alguém e prevalece.
        if P.texto_editorial(pre):
            print(f"   ⏭️  {aba}: já tem descrição, pulando")
            continue

        novo_pre = inserir(pre, frase)
        if novo_pre is None:
            print(f"   ✗ {aba}: não achei onde encaixar (sem <head>)")
            continue

        # Mesma disciplina do preâmbulo: confere antes de gravar.
        problemas = P.conferir_preambulo(novo_pre.replace(frase, ""))
        if frase not in P.texto_editorial(novo_pre):
            problemas.append("a frase não sobreviveu à montagem")
        if problemas:
            print(f"   ✗ {aba}: {'; '.join(problemas)}")
            continue

        print(f"   {aba}")
        print(f"      {frase}")

        if args.dry_run:
            continue

        os.makedirs(pasta_backup, exist_ok=True)
        with open(os.path.join(pasta_backup, f"{slug}.json"), "w",
                  encoding="utf-8") as f:
            json.dump({"slug": slug, "pagina_id": pagina["id"],
                       "salvo_em": datetime.now().isoformat(timespec="seconds"),
                       "conteudo": conteudo}, f, ensure_ascii=False, indent=1)

        resposta = rede.com_retentativa(
            lambda: requests.post(
                f"{API}/pages/{pagina['id']}",
                auth=_auth(), headers=CABECALHOS,
                json={"content": novo_pre + bloco_tabela + sufixo},
                timeout=30,
            ),
            descricao=f"gravar descrição em /{slug}/",
        )

        if resposta.status_code == 200:
            print("      ✓ aplicada")
            aplicadas += 1
        else:
            print(f"      ✗ falha (HTTP {resposta.status_code})")

    if args.dry_run:
        print("\n(--dry-run: nada foi alterado)")
    elif aplicadas:
        print(f"\n💾 Backups em backups/descricao-{carimbo}/")


def main():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--propor", action="store_true",
                        help="gera as propostas em descricoes.json (não toca no site)")
    parser.add_argument("--aplicar", action="store_true",
                        help="grava no site o que está em descricoes.json")
    parser.add_argument("--auto", action="store_true",
                        help="gera E grava na mesma execução, sem revisão "
                             "humana (usado na publicação diária)")
    parser.add_argument("--dry-run", action="store_true",
                        help="com --aplicar, mostra o que faria sem gravar")
    parser.add_argument("--modelo", default=None,
                        help=f"modelo da Groq (padrão: {descricao.MODELO_PADRAO})")
    parser.add_argument("--listar-modelos", action="store_true",
                        help="lista os modelos que a sua chave alcança")
    args = parser.parse_args()

    print("=" * 64)
    print("📝 DESCRIÇÕES DAS PÁGINAS")
    print("=" * 64)

    if args.listar_modelos:
        for m in descricao.listar_modelos(_chave_groq()):
            print(f"   {m}")
        return

    if args.auto:
        # Página nova só ganha descrição depois que a publicação diária
        # preencheu a tabela dela: as categorias saem de lá. Por isso este
        # modo roda no fim do "Atualizar INOVA", e não na criação da página.
        print("🤖 Modo automático: gera e grava sem revisão.\n")
        if propor(args):
            print()
            aplicar(args)
    elif args.propor:
        propor(args)
    elif args.aplicar:
        aplicar(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()

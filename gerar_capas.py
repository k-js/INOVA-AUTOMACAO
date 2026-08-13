# -*- coding: utf-8 -*-
"""
Escolhe a imagem de capa das páginas que estão sem.

Esta primeira versão SÓ ANALISA E RELATA. Ela não escreve nada no site e não
sobe nada para a biblioteca de mídia — a gravação entra depois, quando os
resultados desta etapa tiverem sido conferidos.

O caminho:

    categorias da página  ->  termo de busca em inglês (modelo de texto)
            ->  Pexels devolve candidatas em paisagem
            ->  descarta as pequenas demais para o recorte 3:1
            ->  visão: NSFW, relevância e presença de pessoas (CLIP)
            ->  ordena: sem pessoas primeiro, depois por relevância
            ->  recorta 3:1 até 2400x800, sem ampliar

O mesmo termo alimenta a busca e a medição de relevância, para o CLIP estar
pontuando exatamente contra o que foi pedido ao banco de imagens.

Precisa de PEXELS_API_KEY e GROQ_API_KEY. As dependências de visão estão em
requirements-visao.txt.

    python gerar_capas.py --analisar
    python gerar_capas.py --analisar --abas GAMETECHS,TRAVELTECHS
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

import config
import descricao
import imagem as img
import banco_imagens as banco
import visao

RAIZ = os.path.dirname(os.path.abspath(__file__))
DIR_SAIDA = os.path.join(RAIZ, "capas")
load_dotenv(dotenv_path=os.path.join(RAIZ, "credenciais", ".env"))

API = "https://inova.ufpr.br/wp-json/wp/v2"
CABECALHOS = {"User-Agent": "Mozilla/5.0", "Content-Type": "application/json"}

ABAS_FORA = {config.ABA_PITCHS, config.ABA_VIDEOS}


def _auth():
    usuario, senha = os.getenv("WP_USER"), os.getenv("WP_APP_PASSWORD")
    if not usuario or not senha:
        print("❌ WP_USER e WP_APP_PASSWORD não definidos.")
        sys.exit(1)
    return HTTPBasicAuth(usuario, senha)


def obter_pagina(slug):
    resposta = rede.com_retentativa(
        lambda: requests.get(
            f"{API}/pages", params={"slug": slug, "context": "edit"},
            auth=_auth(), headers=CABECALHOS, timeout=30),
        descricao=f"obter página '{slug}'",
    )
    if resposta.status_code != 200:
        return None
    paginas = resposta.json()
    return paginas[0] if paginas else None


def paginas_sem_capa(filtro=None):
    """
    Páginas sem imagem de capa, com as categorias de cada uma.

    A capa é o bloco wp:cover do preâmbulo. Uma página com <img> ali já tem
    capa e não entra.
    """
    achadas = []
    for aba, url in sorted(config.ABAS_LINKS.items()):
        if aba in ABAS_FORA or (filtro and aba not in filtro):
            continue

        slug = url.rstrip("/").rsplit("/", 1)[-1]
        pagina = obter_pagina(slug)
        if not pagina:
            print(f"   ⚠️  {aba}: página não encontrada")
            continue

        conteudo = pagina.get("content", {}).get("raw", "")
        import preambulo as P
        partes = P.partir_conteudo(conteudo)
        if not partes:
            print(f"   ⚠️  {aba}: sem o marcador de publicação")
            continue

        imagens, _ = P.conteudo_do_preambulo(partes[0])
        if imagens:
            continue  # já tem capa

        categorias = descricao.categorias_da_pagina(conteudo)
        if not categorias:
            print(f"   ⚠️  {aba}: sem categorias na tabela — sem base para o termo")
            continue

        achadas.append((aba, slug, categorias))
    return achadas


def analisar(args):
    if not visao.disponivel():
        print("❌ Dependências de visão ausentes.\n"
              "   pip install -r requirements-visao.txt")
        sys.exit(1)

    chave_groq = os.getenv("GROQ_API_KEY")
    if not chave_groq:
        print("❌ GROQ_API_KEY não definida.")
        sys.exit(1)
    chave_pexels = banco.chave()

    filtro = {a.strip().upper() for a in args.abas.split(",")} if args.abas else None

    print("🔍 Procurando páginas sem capa...")
    alvos = paginas_sem_capa(filtro)
    if not alvos:
        print("\n✅ Todas as páginas já têm capa.")
        return

    print(f"   {len(alvos)} página(s) sem capa\n")
    os.makedirs(DIR_SAIDA, exist_ok=True)
    relatorio = {}

    for aba, slug, categorias in alvos:
        print("=" * 64)
        print(f"📄 {aba}")
        print(f"   categorias: {', '.join(f'{k} ({n})' for k, n in categorias.most_common(5))}")

        termo = descricao.termo_de_busca(aba, categorias, chave_groq, args.modelo)
        if not termo:
            print("   ❌ não consegui um termo em inglês — pulando\n")
            relatorio[aba] = {"termo": "", "escolhida": None}
            continue
        print(f"   termo de busca: {termo!r}")

        candidatas = banco.buscar(termo, chave_pexels)
        grandes = banco.grandes_o_bastante(candidatas)
        print(f"   Pexels: {len(candidatas)} candidatas, "
              f"{len(grandes)} grandes o bastante para 2400x800\n")

        analisadas = []
        for i, cand in enumerate(grandes[:args.limite], 1):
            try:
                dados = banco.baixar(cand)
            except Exception as erro:
                print(f"   {i:>2}. ✗ download falhou: {erro}")
                continue

            resultado = visao.analisar(dados, termo)
            marca = "✗" if resultado["reprovada"] else "•"
            print(f"   {i:>2}. {marca} rel {resultado['relevancia']:.2f}  "
                  f"nsfw {resultado['nsfw']:.2f}  pessoas {resultado['pessoas']:.2f}  "
                  f"{cand['largura']}x{cand['altura']}  {cand['legenda'][:44]}")
            if resultado["reprovada"]:
                print(f"        reprovada: {resultado['reprovada']}")
                continue

            analisadas.append({"candidata": cand, "analise": resultado, "dados": dados})

        if not analisadas:
            print("   ❌ nenhuma candidata aprovada\n")
            relatorio[aba] = {"termo": termo, "escolhida": None}
            continue

        ordenadas = visao.ordenar(analisadas)
        vencedora = ordenadas[0]
        cand, res = vencedora["candidata"], vencedora["analise"]

        recorte, largura, altura = img.padronizar(vencedora["dados"])
        arquivo = os.path.join(DIR_SAIDA, img.nome_do_arquivo(slug))
        with open(arquivo, "wb") as f:
            f.write(recorte)

        alt = descricao.texto_alternativo(cand["legenda"], aba, chave_groq, args.modelo)

        print(f"\n   ✅ escolhida: {cand['url_pagina']}")
        print(f"      relevância {res['relevancia']:.2f} | pessoas {res['pessoas']:.2f} | "
              f"autor {cand['autor']}")
        print(f"      recorte {largura}x{altura}, {len(recorte)//1024} KB "
              f"-> capas/{img.nome_do_arquivo(slug)}")
        print(f"      alt: {alt}\n")

        relatorio[aba] = {
            "termo": termo,
            "arquivo": img.nome_do_arquivo(slug),
            "alt": alt,
            "recorte": f"{largura}x{altura}",
            "escolhida": {
                "origem": cand["origem"], "licenca": cand["licenca"],
                "url_pagina": cand["url_pagina"], "autor": cand["autor"],
                "original": f"{cand['largura']}x{cand['altura']}",
                "legenda": cand["legenda"],
                "relevancia": round(res["relevancia"], 3),
                "pessoas": round(res["pessoas"], 3), "nsfw": round(res["nsfw"], 3),
            },
        }

    caminho = os.path.join(DIR_SAIDA, "capas.json")
    with open(caminho, "w", encoding="utf-8") as f:
        json.dump({"analisado_em": datetime.now().isoformat(timespec="seconds"),
                   "capas": relatorio}, f, ensure_ascii=False, indent=1)

    print("=" * 64)
    print(f"💾 {len(relatorio)} análise(s) em capas/capas.json")
    print("   As imagens recortadas estão em capas/, para conferência.")
    print("   NADA foi enviado ao site — a gravação entra na próxima etapa.")


def main():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--analisar", action="store_true",
                        help="busca, analisa e recorta — sem tocar no site")
    parser.add_argument("--abas", default="",
                        help="limita a estas abas (separadas por vírgula)")
    parser.add_argument("--limite", type=int, default=8,
                        help="máximo de candidatas a baixar por página (padrão: 8)")
    parser.add_argument("--modelo", default=None, help="modelo da Groq")
    args = parser.parse_args()

    print("=" * 64)
    print("🖼️  CAPAS DAS PÁGINAS")
    print("=" * 64)

    if args.analisar:
        analisar(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()

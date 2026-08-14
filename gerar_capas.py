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
            ->  visão: saturação, NSFW, relevância, similaridade e pessoas
            ->  ordena: sem pessoas primeiro, depois por similaridade
            ->  recorta 3:1 até 2400x800, sem ampliar

O mesmo termo alimenta a busca e a medição do CLIP, para ele estar
pontuando exatamente contra o que foi pedido ao banco de imagens.

Precisa de PEXELS_API_KEY e GROQ_API_KEY. As dependências de visão estão em
requirements-visao.txt.

    python gerar_capas.py --analisar
    python gerar_capas.py --analisar --abas GAMETECHS,TRAVELTECHS
"""

import io
import os
import sys
import json
import argparse
from datetime import datetime

for _fluxo in (sys.stdout, sys.stderr):
    try:
        # line_buffering: fora de um terminal o Python segura a saída em
        # buffer, e o log da Action fica vazio até o processo terminar —
        # uma execução longa parece travada quando só está trabalhando.
        _fluxo.reconfigure(encoding="utf-8", errors="replace",
                           line_buffering=True)
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
import capa as capa_wp
import preambulo as P

RAIZ = os.path.dirname(os.path.abspath(__file__))
DIR_SAIDA = os.path.join(RAIZ, "capas")
ARQUIVO = os.path.join(RAIZ, "capas.json")
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
    """
    A página com content.raw, ou None.

    Devolve None também quando a rede falha depois das retentativas, em vez de
    interromper tudo: o site da UFPR fica intermitente de vez em quando, e uma
    queda de segundos na primeira página não pode derrubar um percurso de
    trinta e sete. O aviso sai no log para a falha não passar despercebida.
    """
    try:
        resposta = rede.com_retentativa(
            lambda: requests.get(
                f"{API}/pages", params={"slug": slug, "context": "edit"},
                auth=_auth(), headers=CABECALHOS, timeout=30),
            descricao=f"obter página '{slug}'",
        )
    except requests.RequestException as erro:
        print(f"   ⚠️  {slug}: rede falhou ({type(erro).__name__}) — pulando")
        return None

    if resposta.status_code != 200:
        return None
    paginas = resposta.json()
    return paginas[0] if paginas else None


def paginas_sem_capa(filtro=None, substituir=False):
    """
    Páginas sem imagem de capa, com as categorias de cada uma.

    A capa é o bloco wp:cover do preâmbulo. Uma página com <img> ali já tem
    capa e não entra — a não ser com substituir=True, para o caso de a capa
    atual não servir (a da PROPRIEDADE INTELECTUAL tem 640x480 e não sobrevive
    ao recorte). Trocar a capa de uma página é decisão editorial, então exige
    nomear a aba: substituir só vale junto de um filtro.
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
        partes = P.partir_conteudo(conteudo)
        if not partes:
            print(f"   ⚠️  {aba}: sem o marcador de publicação")
            continue

        imagens, _ = P.conteudo_do_preambulo(partes[0])
        if imagens and not (substituir and filtro):
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

    if args.substituir and not filtro:
        print("❌ --substituir exige --abas: trocar a capa de uma página é\n"
              "   decisão editorial, e não pode valer para todas de uma vez.")
        sys.exit(1)
    print("🔍 Procurando páginas sem capa..." if not args.substituir
          else "🔍 Preparando substituição de capa...")
    alvos = paginas_sem_capa(filtro, args.substituir)
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
            print(f"   {i:>2}. {marca} sim {resultado['similaridade']:.3f}  "
                  f"rel {resultado['relevancia']:.2f}  nsfw {resultado['nsfw']:.2f}  "
                  f"pessoas {resultado['pessoas']:.2f}  sat {resultado['saturacao']:.0f}  "
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
        print(f"      similaridade {res['similaridade']:.3f} | pessoas {res['pessoas']:.2f} | "
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
                "url_arquivo": cand["url_arquivo"],
                "original": f"{cand['largura']}x{cand['altura']}",
                "legenda": cand["legenda"],
                "similaridade": round(res["similaridade"], 3),
                "saturacao": round(res["saturacao"]),
                "relevancia": round(res["relevancia"], 3),
                "pessoas": round(res["pessoas"], 3), "nsfw": round(res["nsfw"], 3),
            },
        }

    with open(ARQUIVO, "w", encoding="utf-8") as f:
        json.dump({"analisado_em": datetime.now().isoformat(timespec="seconds"),
                   "capas": relatorio}, f, ensure_ascii=False, indent=1)

    print("=" * 64)
    print(f"💾 {len(relatorio)} análise(s) em capas.json")
    print("   As imagens recortadas estão em capas/, para conferência.")
    print("   NADA foi enviado ao site — a gravação entra na próxima etapa.")


def aplicar(args):
    """
    Grava no site as capas registradas em capas.json.

    Nada é escolhido aqui: a foto vencedora é rebaixada pela URL que ficou
    guardada, para o que vai ao ar ser exatamente o que foi conferido.
    """
    if not os.path.exists(ARQUIVO):
        print(f"❌ {ARQUIVO} não existe. Rode --analisar primeiro.")
        sys.exit(1)

    with open(ARQUIVO, encoding="utf-8") as f:
        dados_json = json.load(f)
    capas = {a: c for a, c in dados_json.get("capas", {}).items() if c.get("escolhida")}

    print(f"📄 capas.json — {len(capas)} capa(s), analisadas em "
          f"{dados_json.get('analisado_em', '?')}\n")
    if not capas:
        print("Nenhuma capa escolhida no arquivo.")
        return

    # O bloco wp:cover é copiado de uma página que já funciona, e não escrito
    # de cabeça: a estrutura do Gutenberg repete o mesmo dado em três lugares.
    url_modelo = config.ABAS_LINKS.get(P.ABA_MODELO)
    pagina_modelo = obter_pagina(url_modelo.rstrip("/").rsplit("/", 1)[-1])
    if not pagina_modelo:
        print(f"❌ página modelo '{P.ABA_MODELO}' não encontrada.")
        sys.exit(1)
    partes_modelo = P.partir_conteudo(pagina_modelo.get("content", {}).get("raw", ""))
    bloco_modelo = capa_wp.extrair_bloco_modelo(partes_modelo[0]) if partes_modelo else None
    if not bloco_modelo:
        print(f"❌ a página modelo '{P.ABA_MODELO}' não tem bloco wp:cover.")
        sys.exit(1)
    print(f"🧩 bloco de capa copiado de {P.ABA_MODELO} ({len(bloco_modelo)} chars)\n")

    carimbo = datetime.now().strftime("%Y%m%d-%H%M%S")
    pasta_backup = os.path.join(RAIZ, "backups", f"capa-{carimbo}")
    aplicadas = 0

    for aba, item in sorted(capas.items()):
        escolha = item["escolhida"]
        url = config.ABAS_LINKS.get(aba)
        if not url:
            print(f"   ✗ {aba}: fora de ABAS_LINKS")
            continue
        slug = url.rstrip("/").rsplit("/", 1)[-1]

        pagina = obter_pagina(slug)
        if not pagina:
            print(f"   ✗ {aba}: página não encontrada")
            continue

        conteudo = pagina.get("content", {}).get("raw", "")
        partes = P.partir_conteudo(conteudo)
        if not partes:
            print(f"   ✗ {aba}: sem o marcador de publicação")
            continue
        pre, tabela, sufixo = partes

        # Nunca por cima de uma capa existente: se alguém pôs uma no meio do
        # caminho, é decisão de gente e prevalece.
        if P.conteudo_do_preambulo(pre)[0] and not args.substituir:
            print(f"   ⏭️  {aba}: já tem capa, pulando")
            continue

        print(f"   {aba}")
        print(f"      {escolha['url_pagina']}  ({escolha['autor']})")

        if args.dry_run:
            print(f"      alt: {item['alt']}\n")
            continue

        dados = banco.baixar({"url_arquivo": escolha["url_arquivo"]})
        recorte, largura, altura = img.padronizar(dados)

        media_id, url_midia = capa_wp.enviar_para_biblioteca(
            API, recorte, img.nome_do_arquivo(slug), item["alt"],
            f"Capa {aba}", _auth())
        print(f"      mídia {media_id}: {largura}x{altura}, {len(recorte)//1024} KB")

        bloco, problemas = capa_wp.montar_bloco(bloco_modelo, url_midia, media_id,
                                                item["alt"])
        novo_pre = capa_wp.inserir_capa(pre, bloco) if bloco else None

        # Mesma disciplina do preâmbulo: confere ANTES de gravar.
        if novo_pre:
            if not P.tem_preambulo(novo_pre):
                problemas.append("o CSS ou o campo de busca não sobreviveram")
            if len(P.conteudo_do_preambulo(novo_pre)[0]) != 1:
                problemas.append("a página ficou com um número inesperado de imagens")
            if P.texto_editorial(pre) and not P.texto_editorial(novo_pre):
                problemas.append("a descrição da página se perdeu")
        if problemas:
            print(f"      ✗ não gravei: {'; '.join(problemas)}\n")
            continue

        os.makedirs(pasta_backup, exist_ok=True)
        with open(os.path.join(pasta_backup, f"{slug}.json"), "w",
                  encoding="utf-8") as f:
            json.dump({"slug": slug, "pagina_id": pagina["id"],
                       "salvo_em": datetime.now().isoformat(timespec="seconds"),
                       "conteudo": conteudo}, f, ensure_ascii=False, indent=1)

        resposta = rede.com_retentativa(
            lambda: requests.post(
                f"{API}/pages/{pagina['id']}", auth=_auth(), headers=CABECALHOS,
                json={"content": novo_pre + tabela + sufixo}, timeout=60),
            descricao=f"gravar capa em /{slug}/",
        )
        if resposta.status_code == 200:
            print("      ✓ capa aplicada\n")
            aplicadas += 1
        else:
            print(f"      ✗ falha (HTTP {resposta.status_code})\n")

    if args.dry_run:
        print("(--dry-run: nada foi alterado)")
    elif aplicadas:
        print(f"💾 Backups em backups/capa-{carimbo}/")


def repadronizar(args):
    """
    Recorta as capas que já existem para o padrão 3:1, até 2400x800.

    As 33 capas do site vão de 1.5 a 3.49 de proporção, e a da FINTECHS tem
    293px de altura — abaixo dos 300px do bloco, e por isso é esticada. A
    proporção é o que padroniza; a resolução é um teto, e NADA é ampliado.

    A foto é a mesma: só o enquadramento muda. A mídia antiga fica intacta na
    biblioteca, e o bloco passa a apontar para a nova — desfazer é reapontar.
    """
    chave_groq = os.getenv("GROQ_API_KEY")
    carimbo = datetime.now().strftime("%Y%m%d-%H%M%S")
    pasta_backup = os.path.join(RAIZ, "backups", f"repadronizar-{carimbo}")

    filtro = {a.strip().upper() for a in args.abas.split(",")} if args.abas else None
    feitas = pequenas = ja_ok = 0

    # ABAS_FORA não se aplica aqui. Ela existe por causa do layout da TABELA
    # — PITCHS tem embeds de vídeo, VÍDEOS tem 3 colunas —, e a capa é o mesmo
    # elemento em todas as páginas. Excluí-las da padronização de capa foi
    # amplo demais: a de VÍDEOS E PODCASTS tem 4920x3280 e cabe no alvo cheio.
    # Página sem bloco de capa é pulada logo adiante, de qualquer forma.
    print("🔍 Percorrendo as capas existentes...\n")
    for aba, url in sorted(config.ABAS_LINKS.items()):
        if filtro and aba not in filtro:
            continue
        slug = url.rstrip("/").rsplit("/", 1)[-1]

        pagina = obter_pagina(slug)
        if not pagina:
            continue
        conteudo = pagina.get("content", {}).get("raw", "")
        partes = P.partir_conteudo(conteudo)
        if not partes:
            continue
        pre, tabela, sufixo = partes

        bloco_atual = capa_wp.extrair_bloco_modelo(pre)
        if not bloco_atual:
            continue
        media_id = capa_wp.media_id_do_bloco(bloco_atual)
        if not media_id:
            print(f"   ⚠️  {aba}: bloco sem referência de mídia")
            continue

        resposta = rede.com_retentativa(
            lambda: requests.get(f"{API}/media/{media_id}", auth=_auth(),
                                 headers=CABECALHOS, timeout=30),
            descricao=f"ler mídia {media_id}",
        )
        if resposta.status_code != 200:
            print(f"   ⚠️  {aba}: mídia {media_id} não encontrada")
            continue
        midia = resposta.json()
        url_arquivo = midia.get("source_url", "")
        nome_atual = url_arquivo.rsplit("/", 1)[-1]

        if nome_atual == img.nome_do_arquivo(slug):
            ja_ok += 1
            continue

        try:
            dados = banco.baixar({"url_arquivo": url_arquivo})
        except Exception as erro:
            print(f"   ✗ {aba}: baixar a capa falhou ({type(erro).__name__})")
            continue
        from PIL import Image
        largura, altura = Image.open(io.BytesIO(dados)).size
        final_l, final_a, aviso = img.avaliar(largura, altura)

        if aviso and aviso.startswith("pequena demais"):
            print(f"   ⚠️  {aba}: {largura}x{altura} — {aviso}")
            print("        precisa de imagem nova; não vou piorar ampliando\n")
            pequenas += 1
            continue

        print(f"   {aba}")
        print(f"      {largura}x{altura} -> {final_l}x{final_a}"
              f"{'  (máximo sem ampliar)' if aviso else ''}")

        # O alt existente prevalece. Só quando está vazio — o caso das 33 —
        # é que se tenta escrever um, a partir do nome do arquivo.
        alt = capa_wp.extrair_alt(bloco_atual)
        if not alt and chave_groq:
            palavras = capa_wp.palavras_do_arquivo(nome_atual)
            if palavras:
                alt = descricao.alt_do_nome_do_arquivo(palavras, aba, chave_groq,
                                                       args.modelo)
        print(f"      alt: {alt or '(sem base no nome do arquivo — fica vazio)'}")

        if args.dry_run:
            print()
            feitas += 1
            continue

        recorte, larg, alt_px = img.padronizar(dados)
        novo_id, nova_url = capa_wp.enviar_para_biblioteca(
            API, recorte, img.nome_do_arquivo(slug), alt, f"Capa {aba}", _auth())

        novo_bloco, problemas = capa_wp.montar_bloco(bloco_atual, nova_url,
                                                     novo_id, alt)
        novo_pre = pre.replace(bloco_atual, novo_bloco) if novo_bloco else None
        if novo_pre:
            if not P.tem_preambulo(novo_pre):
                problemas.append("o CSS ou o campo de busca não sobreviveram")
            if len(P.conteudo_do_preambulo(novo_pre)[0]) != 1:
                problemas.append("a página ficou com número inesperado de imagens")
            if P.texto_editorial(pre) != P.texto_editorial(novo_pre):
                problemas.append("a descrição da página mudou")
        if problemas:
            print(f"      ✗ não gravei: {'; '.join(problemas)}\n")
            continue

        os.makedirs(pasta_backup, exist_ok=True)
        with open(os.path.join(pasta_backup, f"{slug}.json"), "w",
                  encoding="utf-8") as f:
            json.dump({"slug": slug, "pagina_id": pagina["id"],
                       "midia_anterior": media_id,
                       "salvo_em": datetime.now().isoformat(timespec="seconds"),
                       "conteudo": conteudo}, f, ensure_ascii=False, indent=1)

        gravou = rede.com_retentativa(
            lambda: requests.post(
                f"{API}/pages/{pagina['id']}", auth=_auth(), headers=CABECALHOS,
                json={"content": novo_pre + tabela + sufixo}, timeout=60),
            descricao=f"gravar capa padronizada em /{slug}/",
        )
        if gravou.status_code == 200:
            print(f"      ✓ mídia {novo_id}, {len(recorte)//1024} KB\n")
            feitas += 1
        else:
            print(f"      ✗ falha (HTTP {gravou.status_code})\n")

    print("=" * 64)
    print(f"{feitas} padronizada(s) | {ja_ok} já no padrão | "
          f"{pequenas} pequena(s) demais")
    if args.dry_run:
        print("(--dry-run: nada foi alterado)")
    elif feitas:
        print(f"💾 Backups em backups/repadronizar-{carimbo}/")


def _gravar_alt(aba, pagina, partes, bloco, media_id, alt, dry_run, pasta_backup):
    """
    Escreve o alt no bloco da PÁGINA — e, de brinde, na biblioteca de mídia.

    O que a página exibe vem do atributo alt dentro do bloco wp:cover. Gravar
    só no alt_text da mídia não muda nada no site: foi o que aconteceu na
    primeira versão do --legendar, que rodou sem erro e sem efeito.

    Devolve True se gravou.
    """
    pre, tabela, sufixo = partes

    novo_bloco, problemas = capa_wp.trocar_alt(bloco, alt)
    if problemas:
        print(f"      ✗ {'; '.join(problemas)}\n")
        return False

    novo_pre = pre.replace(bloco, novo_bloco)
    if not P.tem_preambulo(novo_pre):
        print("      ✗ o CSS ou o campo de busca não sobreviveram\n")
        return False
    if len(P.conteudo_do_preambulo(novo_pre)[0]) != 1:
        print("      ✗ a página ficou com número inesperado de imagens\n")
        return False

    if dry_run:
        print()
        return False

    os.makedirs(pasta_backup, exist_ok=True)
    with open(os.path.join(pasta_backup, f"{pagina['id']}.json"), "w",
              encoding="utf-8") as f:
        json.dump({"pagina_id": pagina["id"], "aba": aba,
                   "salvo_em": datetime.now().isoformat(timespec="seconds"),
                   "conteudo": pre + tabela + sufixo}, f, ensure_ascii=False, indent=1)

    gravou = rede.com_retentativa(
        lambda: requests.post(
            f"{API}/pages/{pagina['id']}", auth=_auth(), headers=CABECALHOS,
            json={"content": novo_pre + tabela + sufixo}, timeout=60),
        descricao=f"gravar alt na página {pagina['id']}",
    )
    if gravou.status_code != 200:
        print(f"      ✗ falha (HTTP {gravou.status_code})\n")
        return False

    # A biblioteca também, para quem reaproveitar a imagem noutro lugar. Se
    # falhar, não é motivo para dar a página como não gravada.
    try:
        requests.post(f"{API}/media/{media_id}", auth=_auth(),
                      headers=CABECALHOS, json={"alt_text": alt}, timeout=30)
    except requests.RequestException:
        pass

    print("      ✓ gravado\n")
    return True


def legendar(args):
    """
    Escreve o alt olhando a imagem, com um modelo de visão.

    Onze capas estão sem alt porque o nome do arquivo não diz nada
    ('library-849797_1280'). E das que têm, dezoito descrevem a foto ORIGINAL,
    não o recorte 3:1 publicado — o corte descarta mais da metade da altura, e
    o assunto citado pode ter ficado fora.

    Aqui a legenda sai da imagem que está no ar. Por padrão só mexe nas que
    estão sem alt; --abas força as indicadas, tenham alt ou não.
    """
    if not visao.disponivel():
        print("❌ Dependências de visão ausentes.")
        sys.exit(1)
    chave_groq = os.getenv("GROQ_API_KEY")
    if not chave_groq:
        print("❌ GROQ_API_KEY não definida.")
        sys.exit(1)

    filtro = {a.strip().upper() for a in args.abas.split(",")} if args.abas else None
    print("🔍 " + ("Legendando as abas indicadas..." if filtro
                   else "Procurando capas sem texto alternativo...") + "\n")

    feitas = 0
    carimbo = datetime.now().strftime("%Y%m%d-%H%M%S")
    pasta_backup = os.path.join(RAIZ, "backups", f"alt-{carimbo}")

    for aba, url in sorted(config.ABAS_LINKS.items()):
        if filtro and aba not in filtro:
            continue

        slug = url.rstrip("/").rsplit("/", 1)[-1]
        pagina = obter_pagina(slug)
        partes = P.partir_conteudo(pagina.get("content", {}).get("raw", "")) if pagina else None
        if not partes:
            continue
        bloco = capa_wp.extrair_bloco_modelo(partes[0])
        media_id = capa_wp.media_id_do_bloco(bloco) if bloco else None
        if not media_id:
            continue

        alt_atual = capa_wp.extrair_alt(bloco)
        if alt_atual and not filtro:
            continue

        resposta = rede.com_retentativa(
            lambda: requests.get(f"{API}/media/{media_id}", auth=_auth(),
                                 headers=CABECALHOS, timeout=30),
            descricao=f"ler mídia {media_id}",
        )
        if resposta.status_code != 200:
            print(f"   ✗ {aba}: mídia {media_id} não encontrada")
            continue
        url_imagem = resposta.json().get("source_url", "")

        try:
            dados = banco.baixar({"url_arquivo": url_imagem})
            legenda = visao.legendar(dados)
            novo = descricao.alt_da_legenda(legenda, aba, chave_groq, args.modelo)
        except Exception as erro:
            print(f"   ✗ {aba}: {type(erro).__name__}: {str(erro)[:70]}")
            continue

        # A URL vai no log para a conferência ser um clique: abrir a imagem e
        # ler o alt proposto ao lado.
        print(f"   {aba}")
        print(f"      imagem   : {url_imagem}")
        print(f"      alt atual: {alt_atual or '(vazio)'}")
        print(f"      visão viu: {legenda}")
        print(f"      proposto : {novo}")

        if not novo:
            print()
            continue
        if _gravar_alt(aba, pagina, partes, bloco, media_id, novo,
                       args.dry_run, pasta_backup):
            feitas += 1

    print("=" * 64)
    print(f"{feitas} alt(s) gravado(s)" if not args.dry_run
          else "(--dry-run: nada foi alterado)")
    if feitas:
        print(f"💾 Backups em backups/alt-{carimbo}/")


def refazer_alt(args):
    """
    Reescreve o texto alternativo das capas, sem tocar na imagem.

    Separado da repadronização porque aquela é idempotente pelo nome do
    arquivo: uma vez que a capa virou capa-<slug>.jpg, ela é pulada, e um alt
    ruim ficaria lá para sempre.

    A base continua sendo o nome do arquivo ORIGINAL, guardado no backup da
    repadronização — o arquivo novo se chama capa-<slug>.jpg e não descreve
    mais nada.
    """
    chave_groq = os.getenv("GROQ_API_KEY")
    if not chave_groq:
        print("❌ GROQ_API_KEY não definida.")
        sys.exit(1)

    filtro = {a.strip().upper() for a in args.abas.split(",")} if args.abas else None
    if not filtro:
        print("❌ Informe --abas: reescrever o alt de todas de uma vez\n"
              "   gastaria chamadas à toa nas que já estão boas.")
        sys.exit(1)

    carimbo = datetime.now().strftime("%Y%m%d-%H%M%S")
    pasta_backup = os.path.join(RAIZ, "backups", f"alt-{carimbo}")

    for aba in sorted(filtro):
        url = config.ABAS_LINKS.get(aba)
        if not url:
            print(f"   ✗ {aba}: fora de ABAS_LINKS")
            continue
        slug = url.rstrip("/").rsplit("/", 1)[-1]

        pagina = obter_pagina(slug)
        partes = P.partir_conteudo(pagina.get("content", {}).get("raw", "")) if pagina else None
        if not partes:
            print(f"   ✗ {aba}: página não encontrada ou sem marcador")
            continue
        bloco = capa_wp.extrair_bloco_modelo(partes[0])
        media_id = capa_wp.media_id_do_bloco(bloco) if bloco else None
        if not media_id:
            print(f"   ✗ {aba}: sem bloco de capa")
            continue

        base = args.origem or capa_wp.extrair_alt(bloco)
        if not base:
            print(f"   ✗ {aba}: sem base para reescrever — use --origem")
            continue

        novo = descricao.alt_do_nome_do_arquivo(base, aba, chave_groq, args.modelo)
        print(f"   {aba}")
        print(f"      antes : {capa_wp.extrair_alt(bloco)}")
        print(f"      agora : {novo}")

        if not novo:
            print()
            continue
        _gravar_alt(aba, pagina, partes, bloco, media_id, novo,
                    args.dry_run, pasta_backup)

    if args.dry_run:
        print("(--dry-run: nada foi alterado)")
    else:
        print(f"💾 Backups em backups/alt-{carimbo}/")


def main():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--analisar", action="store_true",
                        help="busca, analisa e recorta — sem tocar no site")
    parser.add_argument("--legendar", action="store_true",
                        help="escreve o alt olhando a imagem publicada "
                             "(padrão: só as que estão sem alt)")
    parser.add_argument("--refazer-alt", action="store_true",
                        help="reescreve o alt das abas dadas em --abas")
    parser.add_argument("--origem", default="",
                        help="com --refazer-alt: texto de partida (padrão: o alt atual)")
    parser.add_argument("--repadronizar", action="store_true",
                        help="recorta as capas JÁ EXISTENTES para o padrão 3:1")
    parser.add_argument("--aplicar", action="store_true",
                        help="grava no site as capas escolhidas em capas.json")
    parser.add_argument("--dry-run", action="store_true",
                        help="com --aplicar, mostra o que faria sem gravar")
    parser.add_argument("--substituir", action="store_true",
                        help="com --analisar, troca a capa de páginas que JÁ têm "
                             "uma (exige --abas)")
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
    elif args.aplicar:
        aplicar(args)
    elif args.repadronizar:
        repadronizar(args)
    elif args.refazer_alt:
        refazer_alt(args)
    elif args.legendar:
        legendar(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()

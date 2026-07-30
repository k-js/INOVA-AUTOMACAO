# -*- coding: utf-8 -*-
"""
Confere se a configuração do repositório ainda bate com a planilha real.

NÃO altera a planilha e NÃO publica nada no site. Só lê e relata.

Para que serve: quando alguém renomeia uma aba, cria uma aba nova ou muda o
nome de uma coluna no Google Sheets, o código para de achar aquilo e a
publicação falha. Este script detecta isso ANTES, e diz exatamente o que mudou
e qual nome provavelmente substituiu qual.

Como rodar:
    python validar.py

Código de saída:
    0 = tudo certo (pode ter avisos)
    1 = há erros que vão quebrar a publicação
"""

import os
import sys
import json
import difflib

import gspread
from google.oauth2.service_account import Credentials

import config


# ---------------------------------------------------------------------
# Coleta de problemas
# ---------------------------------------------------------------------
erros = []    # quebram a publicação
avisos = []   # não quebram, mas merecem atenção


def erro(msg):
    erros.append(msg)


def aviso(msg):
    avisos.append(msg)


def parecido(alvo, candidatos, n=2):
    """Sugere nomes parecidos, para apontar renomeações (T&I vs T&L, acento, etc.)."""
    return difflib.get_close_matches(alvo, list(candidatos), n=n, cutoff=0.6)


# ---------------------------------------------------------------------
# Conexão
# ---------------------------------------------------------------------
def conectar():
    google_json = os.environ.get("GOOGLE_JSON")
    gsheets_key = os.environ.get("GSHEETS_KEY")

    if not google_json:
        print("❌ GOOGLE_JSON não está definido.")
        print("   Na Action ele vem dos Secrets; localmente, de credenciais/.env")
        sys.exit(1)
    if not gsheets_key:
        print("❌ GSHEETS_KEY não está definido.")
        sys.exit(1)

    escopos = [
        "https://www.googleapis.com/auth/drive",
        "https://www.googleapis.com/auth/spreadsheets",
    ]
    creds = Credentials.from_service_account_info(json.loads(google_json), scopes=escopos)
    cliente = gspread.authorize(creds)
    return cliente.open_by_key(gsheets_key)


# ---------------------------------------------------------------------
# Verificações
# ---------------------------------------------------------------------
def checar_abas(nomes_reais):
    """Compara as abas configuradas com as que existem de fato na planilha."""
    print("\n📑 ABAS")

    reais = set(nomes_reais)
    configuradas = set(config.ABAS_LINKS)

    # Configurada mas inexistente: é o caso clássico de aba renomeada.
    for aba in sorted(configuradas - reais):
        sugestoes = parecido(aba, reais)
        if sugestoes:
            erro(
                f"Aba '{aba}' está em ABAS_LINKS mas não existe na planilha.\n"
                f"     Provavelmente foi renomeada para: {' ou '.join(repr(s) for s in sugestoes)}\n"
                f"     → Atualize a chave em config.py (ABAS_LINKS)."
            )
        else:
            erro(
                f"Aba '{aba}' está em ABAS_LINKS mas não existe na planilha "
                f"(nenhum nome parecido encontrado — foi excluída?)."
            )

    # Existe na planilha, não está configurada nem ignorada: aba nova.
    nao_mapeadas = reais - configuradas - config.ABAS_IGNORADAS
    for aba in sorted(nao_mapeadas):
        aviso(
            f"Aba '{aba}' existe na planilha mas não tem página mapeada.\n"
            f"     → Se já tem página no site, adicione em ABAS_LINKS.\n"
            f"     → Se ainda não tem, adicione em ABAS_IGNORADAS para silenciar este aviso."
        )

    # Abas de apoio obrigatórias.
    for obrigatoria in (config.ABA_CONTROLE, config.ABA_HISTORICO):
        if obrigatoria not in reais:
            sugestoes = parecido(obrigatoria, reais)
            extra = f" Nomes parecidos: {sugestoes}" if sugestoes else ""
            erro(f"Aba obrigatória '{obrigatoria}' não encontrada na planilha.{extra}")

    ok = len(configuradas & reais)
    print(f"   {ok} de {len(configuradas)} abas configuradas encontradas na planilha.")
    if nao_mapeadas:
        print(f"   {len(nao_mapeadas)} aba(s) na planilha sem página mapeada.")


def checar_colunas(planilha, nomes_reais):
    """Confere, aba por aba, se as colunas que o código usa ainda existem."""
    print("\n📋 COLUNAS")

    a_verificar = [a for a in config.ABAS_LINKS if a in nomes_reais]
    problemas = 0

    for nome_aba in sorted(a_verificar):
        try:
            cabecalho = planilha.worksheet(nome_aba).row_values(1)
        except Exception as e:
            erro(f"Não foi possível ler o cabeçalho da aba '{nome_aba}': {e}")
            continue

        cabecalho = [c.strip() for c in cabecalho if c and c.strip()]
        if not cabecalho:
            aviso(f"Aba '{nome_aba}' está sem cabeçalho (linha 1 vazia).")
            continue

        # A aba de pitchs tem estrutura própria; não segue o padrão das demais.
        if nome_aba == config.ABA_PITCHS:
            continue

        # Coluna identificadora (NOME / ORGANIZAÇÃO)
        if not config.encontrar_coluna_identificador(cabecalho):
            erro(
                f"Aba '{nome_aba}': nenhuma coluna de identificação encontrada.\n"
                f"     Esperado algo como NOME ou ORGANIZAÇÃO. Cabeçalho atual: {cabecalho}"
            )
            problemas += 1

        # Colunas sem as quais não dá para gerar a tabela
        for col in config.COLUNAS_OBRIGATORIAS:
            if not config.encontrar_coluna(cabecalho, col):
                sugestoes = parecido(col, cabecalho)
                dica = f" Parecido no cabeçalho: {sugestoes}" if sugestoes else ""
                erro(f"Aba '{nome_aba}': coluna obrigatória '{col}' não encontrada.{dica}")
                problemas += 1

        # Balão é opcional, mas quando some o tooltip desaparece calado
        if not config.encontrar_coluna(cabecalho, config.COL_BALAO):
            sugestoes = parecido(config.COL_BALAO, cabecalho)
            dica = f" Parecido: {sugestoes}" if sugestoes else ""
            aviso(f"Aba '{nome_aba}': sem coluna '{config.COL_BALAO}' — tooltips ficarão vazios.{dica}")

        # Coerência entre o roteamento configurado e as colunas que a aba tem
        tem_uf = config.encontrar_coluna(cabecalho, config.COL_UF) is not None
        tem_cidade = config.encontrar_coluna(cabecalho, config.COL_CIDADE) is not None
        tem_pais = config.encontrar_coluna(cabecalho, config.COL_PAIS) is not None

        if config.incluir_geografia(nome_aba):
            if config.usa_gerador_pais(nome_aba) and not tem_pais and not tem_cidade:
                aviso(
                    f"Aba '{nome_aba}' está em ABAS_PAIS mas não tem coluna "
                    f"'{config.COL_PAIS}' nem '{config.COL_CIDADE}'"
                    + (" (só UF)." if tem_uf else ".")
                    + "\n     → O filtro geográfico sairá incompleto."
                )
            elif not tem_uf and not tem_cidade and not tem_pais:
                aviso(
                    f"Aba '{nome_aba}' não tem nenhuma coluna geográfica.\n"
                    f"     → Considere adicioná-la em ABAS_SEM_GEOGRAFIA no config.py."
                )
        else:
            if tem_cidade or tem_pais:
                aviso(
                    f"Aba '{nome_aba}' está em ABAS_SEM_GEOGRAFIA, mas a planilha tem "
                    f"coluna geográfica. O filtro não será exibido."
                )

    print(f"   {len(a_verificar)} aba(s) verificada(s).")


def checar_abas_selecionadas(planilha, nomes_reais):
    """Confere se as abas listadas em CHECAR ABAS são publicáveis."""
    print(f"\n✅ {config.ABA_CONTROLE}")

    if config.ABA_CONTROLE not in nomes_reais:
        return  # já reportado em checar_abas

    try:
        selecionadas = planilha.worksheet(config.ABA_CONTROLE).col_values(1)[1:]
    except Exception as e:
        erro(f"Não foi possível ler '{config.ABA_CONTROLE}': {e}")
        return

    selecionadas = [a.strip() for a in selecionadas if a and a.strip()]

    if not selecionadas:
        print("   Nenhuma aba marcada para atualização no momento.")
        return

    print(f"   {len(selecionadas)} aba(s) marcada(s): {', '.join(selecionadas)}")

    for aba in selecionadas:
        if aba in config.ABAS_LINKS:
            continue
        sugestoes = parecido(aba, config.ABAS_LINKS)
        if sugestoes:
            erro(
                f"'{config.ABA_CONTROLE}' pede atualização de '{aba}', que não tem "
                f"página mapeada.\n     Você quis dizer: {' ou '.join(repr(s) for s in sugestoes)}?"
            )
        else:
            erro(
                f"'{config.ABA_CONTROLE}' pede atualização de '{aba}', que não está "
                f"em ABAS_LINKS. A publicação dessa aba vai falhar."
            )


# ---------------------------------------------------------------------
def main():
    print("=" * 64)
    print("🔍 VALIDAÇÃO DA PLANILHA")
    print("=" * 64)

    planilha = conectar()
    print(f"✅ Planilha aberta: {planilha.title}")

    nomes_reais = [ws.title for ws in planilha.worksheets()]
    print(f"   {len(nomes_reais)} abas encontradas.")

    checar_abas(nomes_reais)
    checar_colunas(planilha, nomes_reais)
    checar_abas_selecionadas(planilha, nomes_reais)

    print("\n" + "=" * 64)
    print("📊 RESULTADO")
    print("=" * 64)

    if avisos:
        print(f"\n⚠️  {len(avisos)} aviso(s):\n")
        for a in avisos:
            print(f"  ⚠️  {a}\n")

    if erros:
        print(f"\n❌ {len(erros)} erro(s) — a publicação vai falhar:\n")
        for e in erros:
            print(f"  ❌ {e}\n")
        print("Corrija config.py (ou a planilha) e rode a validação de novo.")
        sys.exit(1)

    print("\n🎉 Configuração compatível com a planilha. Nada quebrado.")
    sys.exit(0)


if __name__ == "__main__":
    main()

# -*- coding: utf-8 -*-
"""
Fonte única da verdade sobre a estrutura da planilha.

Se uma aba for renomeada, criada ou tiver colunas alteradas no Google Sheets,
ESTE é o único arquivo do repositório que precisa mudar. Todos os scripts
importam daqui em vez de repetir os nomes.

Antes de publicar depois de qualquer mudança aqui, rode:

    python validar.py

O validador compara este arquivo com a planilha real e aponta divergências
(aba renomeada, aba nova sem link, coluna que sumiu) antes que virem erro.
"""

import unicodedata

# =========================================================================
# Nomes fixos da planilha
# =========================================================================
NOME_PLANILHA = "PORTAL DA INOVAÇÃO E STARTUPS"

ABA_CONTROLE = "CHECAR ABAS"   # lista, na coluna A, quais abas atualizar
ABA_HISTORICO = "HISTÓRICO"    # log de entradas/saídas

# =========================================================================
# Colunas
# =========================================================================
# A coluna que identifica a organização varia entre as abas: umas usam NOME,
# outras ORGANIZAÇÃO. Qualquer uma destas variações é aceita (a comparação
# ignora acento e maiúsculas).
VARIACOES_IDENTIFICADOR = {
    "NOME OU ORGANIZACAO",
    "ORGANIZACAO",
    "NOME",
}

COL_CATEGORIA = "CATEGORIA"
COL_LINK = "LINK"
COL_STATUS = "STATUS"
COL_BALAO = "CONTEÚDO BALÃO"
COL_UF = "UF"
COL_CIDADE = "CIDADE"
COL_PAIS = "PAÍS"

# Colunas sem as quais uma aba não pode gerar HTML.
COLUNAS_OBRIGATORIAS = [COL_CATEGORIA, COL_LINK, COL_STATUS]

# =========================================================================
# Valores da coluna STATUS
# =========================================================================
STATUS_ADICIONAR = "ADICIONAR AO SITE"
STATUS_REMOVER = "REMOVER"
STATUS_EDITAR = "EDITAR"
STATUS_PUBLICADO = "ADICIONADO AO SITE"

# =========================================================================
# Mapeamento aba -> URL da página no WordPress
# =========================================================================
# A chave precisa bater EXATAMENTE com o nome da aba no Google Sheets.
# Aba sem entrada aqui é ignorada pela automação (o validador avisa).
ABAS_LINKS = {
    "ACELERADORAS E INCUBADORAS": "https://inova.ufpr.br/aceleradoras-incubadoras/",
    "ASSOCIAÇÕES EMPRESARIAIS": "https://inova.ufpr.br/associacao-empresarial/",
    "CONSTRUTECHS E PROPTECHS": "https://inova.ufpr.br/construtechs-e-proptechs/",
    "DEEPTECHS": "https://inova.ufpr.br/biotechs/",
    "EDTECHS": "https://inova.ufpr.br/edtechs/",
    "ENERGYTECHS": "https://inova.ufpr.br/energytechs/",
    "FASHIONTECHS": "https://inova.ufpr.br/fashiontechs/",
    "FINANCIAMENTO A INOVAÇÃO": "https://inova.ufpr.br/financiamento-inovacao/",
    "FINTECHS": "https://inova.ufpr.br/fintechs/",
    "FOODTECHS": "https://inova.ufpr.br/foodtechs/",
    "GAMETECHS": "https://inova.ufpr.br/gametechs/",
    "GOVTECHS": "https://inova.ufpr.br/govtechs/",
    "GREENTECHS": "https://inova.ufpr.br/greentechs/",
    "HEALTHTECHS": "https://inova.ufpr.br/health-tech/",
    "HRTECHS": "https://inova.ufpr.br/hrtechs/",
    "HUBS E ECOSSISTEMAS": "https://inova.ufpr.br/hubs-e-ecossistemas/",
    "INDTECHS": "https://inova.ufpr.br/indtechs/",
    "INOVAÇÃO NAS UNIVERSIDADES": "https://inova.ufpr.br/inovacao-nas-universidades/",
    "INSTITUTOS DE PESQUISA E CENTROS DE T&I": "https://inova.ufpr.br/institutos-de-pesquisa/",
    "INSURTECHS": "https://inova.ufpr.br/insurtechs/",
    "LAWTECHS E LEGALTECHS": "https://inova.ufpr.br/lawtechs-e-legaltechs/",
    "LOGTECHS": "https://inova.ufpr.br/logtechs/",
    "MANAGETECHS": "https://inova.ufpr.br/managetechs/",
    "MARTECHS": "https://inova.ufpr.br/martechs/",
    "MOBITECHS": "https://inova.ufpr.br/mobitechs/",
    "PARQUES CIENTÍFICOS": "https://inova.ufpr.br/parques-tecnologicos/",
    "PERÍODICOS CIENTÍFICOS": "https://inova.ufpr.br/periodicos-cientificos/",
    "PETTECHS": "https://inova.ufpr.br/pet-techs/",
    "PITCHS DE STARTUPS": "https://inova.ufpr.br/pitchs-de-startups-incubadoras-e-aceleradoras/",
    "POLÍTICAS DE INOVAÇÃO": "https://inova.ufpr.br/politicas-de-inovacao/",
    "PORTAIS DE NOTÍCIAS": "https://inova.ufpr.br/portais-de-noticias/",
    "PROPRIEDADE INTELECTUAL": "https://inova.ufpr.br/1234-2/",
    "RETAILTECHS": "https://inova.ufpr.br/retailtechs-2/",
    "SECURITYTECHS": "https://inova.ufpr.br/securitytechs/",
    "SOCIALTECHS": "https://inova.ufpr.br/socialtechs/",
    "TECHS": "https://inova.ufpr.br/techs/",
    "TRAVELTECHS": "https://inova.ufpr.br/traveltechs/",
    "VÍDEOS E PODCASTS": "https://inova.ufpr.br/cursos-e-podcasts-de-empreendedorismo/",
    "WATERTECHS": "https://inova.ufpr.br/watertechs/",
}

# =========================================================================
# Abas que existem na planilha mas NÃO devem ser publicadas
# =========================================================================
# Abas de apoio (controle, BI, rascunho) e abas de categorias que ainda não
# têm página criada no site. Ao criar a página no WordPress, tire a aba
# daqui e adicione em ABAS_LINKS.
ABAS_IGNORADAS = {
    # Estrutura / apoio
    "HOME",
    ABA_CONTROLE,
    ABA_HISTORICO,
    "BI STARTUPS",
    "MAPA POWER BI",
    "Centros de Pesquisa",
    "deeptechs comparativo",
    # Aba de teste da equipe: não é página do site. Ficou mapeada em
    # ABAS_LINKS por engano, apontando para /teste/, que nunca existiu — cada
    # execução gastava uma tentativa nela e terminava com um aviso.
    "TESTE",
    # A página /agtechs/ existe no site e tem botão em /startups/, mas leva a
    # OUTRO portfólio: ela não é alimentada por esta planilha. Está correta
    # como está — não é caso de publicar, nem de tirar o botão. Confirmado com
    # a equipe em 13/08/2026.
    "AGTECHS",
    # --- Sem página no site ---
    #
    # Aguardando a EQUIPE terminar de preencher os dados na planilha.
    # Não propor criação de página: a aba ainda está em construção.
    # Situação informada pela equipe em 14/08/2026.
    #
    # SECURITYTECHS saiu daqui em 20/08/2026: publicação pedida pelo professor,
    # junto com PORTAIS DE NOTÍCIAS. As duas foram para ABAS_AGUARDANDO_PAGINA.
    "BEAUTYTECHS",
    "EVENTECHS",
    "SPORTECHS",
}

# Abas cuja página no WordPress ainda está como RASCUNHO.
#
# A página existe e já tem URL em ABAS_LINKS, mas só vai ao ar quando alguém
# clicar em "Publicar" no WordPress. Até lá, a publicação falha nessas abas: o
# atualizador_WP.py procura a página pelo slug, e a API não retorna rascunhos
# em busca não autenticada.
#
# Para publicar pela Action:
#   Actions → "Criar páginas no WordPress" → marcar "Publicar as páginas
#   em rascunho"
#
# FASHIONTECHS, GAMETECHS, INSURTECHS e TRAVELTECHS passaram por aqui em
# 30/07/2026 e já aparecem na grade de /startups/.
#
# As duas de agora entraram em 20/08/2026, a pedido do professor. Ao serem
# publicadas, tire-as desta lista — o próprio script avisa no fim da execução.
ABAS_AGUARDANDO_PAGINA = {
    "PORTAIS DE NOTÍCIAS",
    "SECURITYTECHS",
}

# =========================================================================
# Roteamento: qual gerador de HTML usar em cada aba
# =========================================================================
# O padrão é o gerador comum (UF + CIDADE). As listas abaixo são exceções.

# Abas com gerador próprio, por terem estrutura muito diferente.
ABA_PITCHS = "PITCHS DE STARTUPS"       # embeds de vídeo
ABA_VIDEOS = "VÍDEOS E PODCASTS"        # layout de 3 colunas

# Abas cuja coluna geográfica é PAÍS (e não CIDADE).
#
# ATENÇÃO: pela leitura da planilha, 'ASSOCIAÇÕES EMPRESARIAIS' e
# 'POLÍTICAS DE INOVAÇÃO' têm apenas UF — não têm CIDADE nem PAÍS. Elas estão
# nesta lista desde antes; o gerador de país simplesmente não encontra a coluna
# e o filtro sai incompleto. O validador sinaliza isso como aviso.
# Decida caso a caso: ou some a coluna PAÍS na planilha, ou tire a aba daqui.
ABAS_PAIS = {
    "ASSOCIAÇÕES EMPRESARIAIS",
    "FINANCIAMENTO A INOVAÇÃO",
    "HUBS E ECOSSISTEMAS",
    "INSTITUTOS DE PESQUISA E CENTROS DE T&I",
    "POLÍTICAS DE INOVAÇÃO",
    "PROPRIEDADE INTELECTUAL",
}

# Abas sem relação geográfica: o filtro de Estado/Cidade/País é removido
# inteiramente do HTML gerado para elas.
#
# Só entram aqui abas que NÃO têm coluna geográfica na planilha. Uma aba que
# tem a coluna e está listada aqui perde o filtro e a coluna no site, sem
# nenhum aviso — foi o que aconteceu com POLÍTICAS DE INOVAÇÃO (tem UF),
# PROPRIEDADE INTELECTUAL (tem PAÍS) e PERÍODICOS CIENTÍFICOS (tem PAÍS).
#
# Vazio no momento: todas as abas mapeadas têm coluna geográfica e a exibem.
# O validador avisa se alguma aba listada aqui tiver a coluna na planilha.
ABAS_SEM_GEOGRAFIA = set()


# =========================================================================
# Utilidades de comparação de nomes
# =========================================================================
def normalizar(texto):
    """
    Maiúsculo e sem acento, para comparar nomes de forma tolerante.
    'Organização', 'ORGANIZAÇÃO' e 'organizacao' viram todos 'ORGANIZACAO'.
    """
    if texto is None:
        return ""
    texto = str(texto).strip().upper()
    return unicodedata.normalize("NFKD", texto).encode("ASCII", "ignore").decode("ASCII")


def encontrar_coluna(cabecalho, nome_procurado):
    """
    Acha uma coluna pelo nome ignorando acento e maiúsculas.
    Retorna o nome EXATO como está no cabeçalho, ou None.

    Use sempre isto em vez de `cabecalho.index("PAÍS")`: assim a planilha pode
    ter 'PAIS', 'País' ou 'PAÍS' que o código continua achando.
    """
    alvo = normalizar(nome_procurado)
    for col in cabecalho:
        if normalizar(col) == alvo:
            return col
    return None


def encontrar_coluna_identificador(cabecalho):
    """
    Acha a coluna que identifica a organização (NOME / ORGANIZAÇÃO / variações),
    ignorando acento e maiúsculas. Retorna o nome EXATO, ou None.
    """
    for col in cabecalho:
        if normalizar(col) in VARIACOES_IDENTIFICADOR:
            return col
    return None


def mapear_colunas_normalizadas(colunas):
    """Mapeia nome normalizado -> nome exato, para busca por nome (nunca por posição)."""
    return {normalizar(c): c for c in colunas}


def incluir_geografia(aba):
    """True se a aba deve exibir filtro de Estado/Cidade/País."""
    return normalizar(aba) not in {normalizar(a) for a in ABAS_SEM_GEOGRAFIA}


def usa_gerador_pais(aba):
    """True se a aba usa o gerador com coluna PAÍS."""
    return normalizar(aba) in {normalizar(a) for a in ABAS_PAIS}

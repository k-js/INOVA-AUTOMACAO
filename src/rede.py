# -*- coding: utf-8 -*-
"""
Ajustes de rede para o ambiente da GitHub Action.

O site inova.ufpr.br publica endereço IPv4 e IPv6:

    IPv4: 200.17.209.3
    IPv6: 2801:82:8020::d55:ba:2

Os runners do GitHub não têm conectividade IPv6. Quando a resolução de nomes
devolve o endereço IPv6 primeiro, a conexão falha com:

    OSError: [Errno 101] Network is unreachable

Importar este módulo faz a resolução ignorar IPv6, o que resolve o problema
sem afetar quem roda localmente (onde IPv4 continua sendo usado normalmente).

Uso: basta importar antes de fazer requisições.

    import rede  # noqa: F401
"""

import socket

_getaddrinfo_original = socket.getaddrinfo


def _somente_ipv4(host, port, family=0, type=0, proto=0, flags=0):
    """
    Versão de socket.getaddrinfo que devolve apenas endereços IPv4.

    Se não houver nenhum IPv4 para o host, repassa o resultado original em vez
    de falhar — assim um host exclusivamente IPv6 continua funcionando em
    ambientes que o suportem.
    """
    resultados = _getaddrinfo_original(host, port, family, type, proto, flags)
    apenas_v4 = [r for r in resultados if r[0] == socket.AF_INET]
    return apenas_v4 or resultados


def forcar_ipv4():
    """Aplica o ajuste. Idempotente: chamar mais de uma vez não acumula."""
    if socket.getaddrinfo is not _somente_ipv4:
        socket.getaddrinfo = _somente_ipv4


# Aplicado na importação, para que baste `import rede` no topo do script.
forcar_ipv4()

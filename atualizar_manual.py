# atualizar_manual.py
from criarHTML import processa_aba_gera_html
from atualizador_WP import atualizar_pagina_wp

def atualizar_construtechs_manual():
    print("🔄 ATUALIZAÇÃO MANUAL - CONSTRUTECHS E PROPTECHS")
    print("=" * 50)
    
    aba = "CONSTRUTECHS E PROPTECHS"
    url = "https://inova.ufpr.br/construtechs-e-proptechs/"
    
    print(f"1. 🗂️ Processando aba: {aba}")
    html = processa_aba_gera_html(aba)
    
    if not html:
        print("❌ Falha ao gerar HTML")
        return False
        
    print(f"2. 📏 HTML gerado: {len(html)} caracteres")
    print(f"3. 🌐 Atualizando WordPress: {url}")
    
    resultado = atualizar_pagina_wp(url, html)
    
    if resultado:
        print("✅ Página atualizada com SUCESSO!")
        print("💡 Atualize a página no navegador para ver as mudanças")
    else:
        print("❌ Falha ao atualizar a página")
        
    return resultado

# Executar
atualizar_construtechs_manual()
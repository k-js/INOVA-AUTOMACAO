import json
import os

def converter_json():
    print("🔄 CONVERSOR DE JSON PARA .env")
    print("=" * 50)
    
    # REMOVA o caminho hardcoded e use input() normal
    caminho_json = input("Cole o caminho completo do arquivo JSON baixado: ").strip().strip('"')
    
    try:
        with open(caminho_json, 'r', encoding='utf-8') as f:
            creds = json.load(f)
        
        google_json_str = json.dumps(creds)
        
        print("\n✅ CONVERSÃO BEM-SUCEDIDA!")
        print("=" * 50)
        print("COPIAR ESTE TEXTO PARA O ARQUIVO .env:")
        print("=" * 50)
        print(f'GOOGLE_JSON={google_json_str}')
        print("=" * 50)
        
        env_path = 'credenciais/.env'
        if os.path.exists(env_path):
            with open(env_path, 'r', encoding='utf-8') as f:
                conteudo = f.read()
            
            linhas = conteudo.split('\n')
            novas_linhas = []
            google_json_atualizado = False
            
            for linha in linhas:
                if linha.startswith('GOOGLE_JSON='):
                    novas_linhas.append(f'GOOGLE_JSON={google_json_str}')
                    google_json_atualizado = True
                else:
                    novas_linhas.append(linha)
            
            if not google_json_atualizado:
                novas_linhas.append(f'GOOGLE_JSON={google_json_str}')
            
            with open(env_path, 'w', encoding='utf-8') as f:
                f.write('\n'.join(novas_linhas))
            
            print("\n📁 Arquivo .env atualizado automaticamente!")
        else:
            print(f"\n⚠️  Arquivo {env_path} não encontrado.")
        
        print(f"\n📧 E-mail da Service Account: {creds.get('client_email', 'Não encontrado')}")
        
    except FileNotFoundError:
        print("❌ Arquivo JSON não encontrado. Verifique o caminho.")
    except Exception as e:
        print(f"❌ Erro: {e}")

if __name__ == "__main__":
    converter_json()
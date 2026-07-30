# 🛰️ Atualizador de Páginas do Projeto INOVA – UFPR

Este projeto automatiza a atualização de páginas do site [inova.ufpr.br](https://inova.ufpr.br), que divulga organizações de inovação mapeadas pelo projeto de extensão **Inovação e Desenvolvimento Territorial** da UFPR.

## ✨ Objetivo

A equipe do projeto mantém uma planilha no Google Sheets com diversas abas (startups, aceleradoras, universidades, etc.). Este sistema:

Converte automaticamente o conteúdo das abas em HTML interativo.

Atualiza as páginas do WordPress todos os dias por meio de uma GitHub Action.

Identifica quais abas precisam de atualização através da coluna STATUS da planilha (ADICIONAR AO SITE, REMOVER, EDITAR).

Publica o HTML nas páginas corretas do WordPress via REST API.

---

## 🔧 Funcionalidades

✅ Atualização diária automática via GitHub Actions
✅ Geração de HTML com filtros por estado, cidade/país e categoria em JavaScript
✅ Integração direta com Google Sheets (via App Script + API)
✅ Mapeamento entre aba e URL configurado no arquivo main.py
✅ Substituição dinâmica do conteúdo no WordPress
✅ Processamento automatizado conforme o STATUS de cada aba

---

## 🛠️ Tecnologias utilizadas

- **Python 3**
- `pandas`
- `GitHub Actions`
- `GitHub Secrets`
- `requests`
- `openpyxl`
- **Google Sheets API + App Script**
- **WordPress REST API**

---

## 📂 Estrutura do Projeto

```
├── main.py              # Publicação: orquestra a atualização (usado pela Action)
├── validar.py           # Confere se a planilha bate com a configuração (só lê)
├── interface.py         # Interface gráfica para rodar manualmente
├── requirements.txt     # Dependências
│
├── src/
│   ├── config.py        # ⭐ Nomes de abas, colunas e URLs — fonte única
│   ├── conexao_api.py   # Cliente autenticado do Google Sheets
│   ├── atualizador_WP.py# Publicação via REST API do WordPress
│   ├── criarHTML.py     # Gerador padrão (UF + Cidade)
│   ├── criaHTMLPais.py  # Gerador com coluna País
│   ├── criarHTML_3col.py# Gerador de 3 colunas (Vídeos e Podcasts)
│   ├── pitchs.py        # Gerador dos pitches em vídeo
│   └── converter_json.py# Utilitário para gerar o .env da service account
│
├── apps-script/         # Código que roda dentro da planilha (Google Apps Script)
├── docs/
│   └── MANUTENCAO.md    # ⭐ O que fazer quando aba/coluna muda de nome
└── .github/workflows/
    ├── atualizar.yml    # Publicação diária (10:00 UTC)
    └── validar.yml      # Validação diária (08:00 UTC), sem publicar
```

---

## 🔧 Manutenção

Quando uma **aba for renomeada, criada, ou uma coluna mudar de nome** na
planilha, o código precisa saber. Rode a validação:

**Actions → "Validar planilha (somente leitura)" → "Run workflow"**

Ela lê a planilha, compara com [src/config.py](src/config.py) e aponta o que
está divergente — inclusive sugerindo o nome provável quando detecta uma
renomeação. Não publica nada e não altera a planilha.

O passo a passo de cada situação está em [docs/MANUTENCAO.md](docs/MANUTENCAO.md).

---

## 🔐 Segurança

-As credenciais do WordPress e do Google estão armazenadas como GitHub Secrets, não sendo expostas no código.

-A autenticação com o WordPress é feita por senha de aplicativo, prática segura e recomendada para uso com a REST API.

---

## 👨‍💻 Autor

Desenvolvido por **Marcos Felipe Lopes Rodrigues**, aluno de Ciências Econômicas da UFPR e integrante do projeto de extensão *Inovação e Desenvolvimento Territorial*.

---

## 📃 Licença

Este projeto é de uso acadêmico e institucional, vinculado à Universidade Federal do Paraná.

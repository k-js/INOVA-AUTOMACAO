# 🛰️ Atualizador de Páginas do Projeto INOVA – UFPR

Este projeto automatiza a atualização de páginas do site [inova.ufpr.br](https://inova.ufpr.br), que divulga organizações de inovação mapeadas pelo projeto de extensão **Inovação e Desenvolvimento Territorial** da UFPR.

## ✨ Objetivo

A equipe mantém uma planilha no Google Sheets com dezenas de abas (startups, aceleradoras, universidades, etc.). Este sistema transforma essas abas em páginas do site, sem ninguém editar HTML.

A planilha é a fonte da verdade. **O código nunca a altera** — só lê.

O ciclo completo:

1. A equipe marca a coluna **STATUS** nas abas (`ADICIONAR AO SITE`, `EDITAR`, `REMOVER`)
2. O Apps Script lista em **CHECAR ABAS** quais abas têm pendência
3. A GitHub Action diária lê essa lista e republica as páginas correspondentes
4. Página nova ganha capa, descrição e botão automaticamente

---

## 🔧 O que o sistema faz

### Todo dia, sozinho

| | |
|---|---|
| **Valida** | confere se a planilha ainda bate com a configuração, e avisa quando uma aba é criada ou renomeada |
| **Faz backup** | salva o conteúdo atual de cada página antes de reescrevê-la |
| **Publica** | gera o HTML da tabela, com filtros de estado, cidade/país e categoria, e grava via REST API |
| **Descreve** | escreve a frase de apresentação das páginas que ainda não têm |

### Sob demanda, quando você clica

| | |
|---|---|
| **Cria páginas** | de abas que ainda não existem no site — nascem como rascunho, e só vão ao ar quando alguém publica |
| **Escolhe capas** | busca no Pexels e analisa cada candidata localmente antes de publicar |
| **Sincroniza botões** | mantém a grade de /startups/ e aponta cada link direto ao destino |
| **Padroniza preâmbulo** | CSS das tabelas, campo de busca e botão VOLTAR |
| **Renomeia slugs** | com conferência automática e reversão se algo não bater |

### Capa e descrição, em detalhe

São as duas partes que fazem uma página nova nascer pronta.

**A descrição** é escrita por um modelo de linguagem (Groq), mas **ancorada nas categorias que a própria aba já tem** — e não inventada do nome. A página de INSURTECHS é descrita a partir das categorias que aparecem na tabela dela, com os pesos que elas têm.

**A capa** passa por uma análise de imagem local antes de ser publicada, nesta ordem — do mais barato ao mais caro:

| Etapa | O que faz |
|---|---|
| saturação | descarta imagem em preto e branco (sem modelo, só pixels) |
| NSFW | descarta conteúdo impróprio |
| relevância | CLIP decide se a imagem tem a ver com o tema — porteira, passa ou não passa |
| similaridade | CLIP ordena as aprovadas por proximidade com o tema |
| pessoas | prefere imagem com gente, quando há empate |

A escolhida é recortada em **3:1, até 2400×800**, nunca ampliada. O texto alternativo é escrito por um modelo de legendagem (BLIP) a partir da imagem **já recortada** — a que o visitante vê, e não a original.

---

## 🛠️ Tecnologias

- **Python 3**
- `pandas`, `openpyxl` — leitura da planilha
- `gspread`, `google-auth` — Google Sheets API
- `requests` — WordPress REST API
- `Pillow` — recorte das capas
- `torch`, `transformers` — CLIP e BLIP, na análise das capas
- **Google Apps Script** — roda dentro da planilha
- **GitHub Actions** e **GitHub Secrets**

As dependências ficam em **dois arquivos**, de propósito:

- `requirements.txt` — o dia a dia
- `requirements-visao.txt` — CLIP e BLIP, ~1 GB, 2-3 min de instalação. Só o workflow das capas carrega esse peso; a publicação diária não

---

## 📂 Estrutura do Projeto

```
├── main.py                  # Publicação diária: orquestra tudo (usado pela Action)
├── validar.py               # Confere se a planilha bate com a configuração (só lê)
├── backup_paginas.py        # Salva as páginas antes de a publicação reescrevê-las
├── interface.py             # Interface gráfica para rodar manualmente
│
├── sincronizar_config.py    # Mantém o config.py em sincronia com planilha e site
├── sincronizar_botoes.py    # Grade de botões de /startups/
├── corrigir_preambulo.py    # CSS das tabelas, campo de busca, botão VOLTAR
├── gerar_capas.py           # Escolhe, recorta e publica as imagens de capa
├── gerar_descricoes.py      # Escreve a frase de apresentação das páginas
├── renomear_slug.py         # Padroniza slugs, conferindo e revertendo sozinho
├── remover_do_menu.py       # Tira do menu itens que apontam para rascunho
│
├── requirements.txt         # Dependências do dia a dia
├── requirements-visao.txt   # CLIP e BLIP (só o workflow das capas)
│
├── src/
│   ├── config.py            # ⭐ Nomes de abas, colunas e URLs — fonte única
│   ├── conexao_api.py       # Cliente autenticado do Google Sheets
│   ├── rede.py              # Ajustes de rede para o runner da Action
│   ├── atualizador_WP.py    # Publicação via REST API do WordPress
│   │
│   ├── criarHTML.py         # Gerador padrão (UF + Cidade)
│   ├── criaHTMLPais.py      # Gerador com coluna País
│   ├── criarHTML_3col.py    # Gerador de 3 colunas (Vídeos e Podcasts)
│   ├── pitchs.py            # Gerador dos pitches em vídeo
│   │
│   ├── criar_pagina_wp.py   # Cria a página de uma aba que ainda não tem
│   ├── preambulo.py         # O que vem ANTES do marcador de publicação
│   ├── botoes_wp.py         # Leitura e escrita da grade de botões
│   │
│   ├── descricao.py         # Descrição a partir das categorias da própria aba
│   ├── banco_imagens.py     # Busca de imagens no Pexels
│   ├── visao.py             # Análise dos pixels antes de virar capa
│   ├── imagem.py            # Recorte 3:1, até 2400×800, sem ampliar
│   ├── capa.py              # Envio à biblioteca de mídia e bloco wp:cover
│   └── converter_json.py    # Utilitário para gerar o .env da service account
│
├── apps-script/             # Código que roda dentro da planilha
│   ├── Codigo.gs            # Menu, CHECAR ABAS, checagem de links
│   ├── Dialog.html          # Diálogo de edição de link quebrado
│   ├── COMO-ATUALIZAR.md
│   └── RECRIAR-DO-ZERO.md
│
├── backups/                 # Conteúdo anterior das páginas, para reverter
├── docs/
│   ├── MANUTENCAO.md        # ⭐ O que fazer quando aba/coluna muda de nome
│   └── PENDENCIAS.md        # ⭐ Divergências conhecidas e o porquê de cada decisão
└── .github/workflows/
```

---

## ⚙️ Workflows (aba Actions)

| Workflow | Quando roda | O que faz |
|---|---|---|
| **Validar planilha** | 08:00 UTC + manual | só lê; fica vermelho para avisar de aba nova |
| **Atualizar INOVA** | 10:00 UTC + manual | backup, publicação e descrição das páginas novas |
| **Criar páginas no WordPress** | manual | cria, publica, sincroniza botões, padroniza preâmbulo |
| **Capas das páginas** | manual | busca, analisa, recorta e publica capas; também o texto alternativo |
| **Descrições das páginas** | manual | propõe ou aplica as frases de apresentação |
| **Renomear slugs divergentes** | manual | padroniza endereços, com conferência e reversão |

Quase todos aceitam **`dry_run`**, que mostra o que fariam sem alterar nada. Comece sempre por ele.

O que escreve no site **faz backup antes**, em `backups/`, publicado também como artefato da execução (90 dias). Para reverter, cada script tem `--listar-backups` e `--restaurar`.

---

## 🔐 Segredos necessários

Configurados em **Settings → Secrets and variables → Actions**:

| Segredo | Para quê |
|---|---|
| `WP_USER`, `WP_APP_PASSWORD` | REST API do WordPress (senha de aplicativo) |
| `WP_URL` | endereço do site |
| `GSHEETS_KEY` | id da planilha |
| `GOOGLE_JSON` | credenciais da service account do Google |
| `GROQ_API_KEY` | descrições e termos de busca das capas |
| `PEXELS_API_KEY` | busca de imagens de capa |

Nenhuma credencial fica no repositório. Sem elas, **nada que escreve no site roda a partir de uma máquina local** — só pela Action.

---

## 🔧 Manutenção

Quando uma **aba for renomeada, criada, ou uma coluna mudar de nome** na planilha, o código precisa saber. Rode a validação:

**Actions → "Validar planilha (somente leitura)" → "Run workflow"**

Ela lê a planilha, compara com [src/config.py](src/config.py) e aponta o que está divergente — inclusive sugerindo o nome provável quando detecta uma renomeação. Não publica nada e não altera a planilha.

O passo a passo de cada situação está em [docs/MANUTENCAO.md](docs/MANUTENCAO.md).

Em [docs/PENDENCIAS.md](docs/PENDENCIAS.md) ficam as divergências conhecidas e **o motivo de cada decisão** — inclusive as que parecem erro e não são, como a aba que tem botão sem ser publicada por aqui. Vale ler antes de "consertar" algo que está assim de propósito.

---

## 🔐 Segurança

- As credenciais do WordPress e do Google estão armazenadas como GitHub Secrets, não sendo expostas no código.
- A autenticação com o WordPress é feita por senha de aplicativo, prática segura e recomendada para uso com a REST API.
- A planilha é somente leitura para a automação: nenhum script escreve nela.
- Toda escrita no site é precedida de backup, e as páginas nascem como rascunho — nada vai ao ar sem alguém publicar.

---

## 👨‍💻 Autor

Desenvolvido por **Marcos Felipe Lopes Rodrigues**, aluno de Ciências Econômicas da UFPR e integrante do projeto de extensão *Inovação e Desenvolvimento Territorial*.

---

## 📃 Licença

Este projeto é de uso acadêmico e institucional, vinculado à Universidade Federal do Paraná.

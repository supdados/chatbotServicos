import pandas as pd
import os

# --- 1. CONFIGURAÇÃO INICIAL (SIMULAÇÃO DE DADOS) ---

# Crie um DataFrame de exemplo com as colunas mencionadas:
df = pd.read_excel('2025-12-23-relatorio-servicos (1).xlsx')

# Defina o diretório onde os arquivos Markdown serão salvos
OUTPUT_DIR = 'arquivos_markdown_titulos'

# --- 2. PREPARAÇÃO DO DIRETÓRIO ---

# Cria o diretório de saída se ele ainda não existir
if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)
    print(f"Diretório '{OUTPUT_DIR}' criado com sucesso.")

# --- 3. GERAÇÃO DOS ARQUIVOS MARKDOWN ---

print("Iniciando a geração dos arquivos Markdown...")

# Itera sobre cada linha (registro) do DataFrame
# O .iterrows() retorna o índice e a série de dados para cada linha.
for index, row in df.iterrows():
    # 1. Limpeza do TÍTULO para usar como nome de arquivo
    # Substitui espaços e caracteres especiais por underscore para criar um nome de arquivo válido e limpo
    titulo_limpo = row['TÍTULO'].replace(' ', '_').replace("/",'-').replace("\"","").lower()
    file_name = f"{titulo_limpo}.md"
    file_path = os.path.join('servicos', file_name)

    # 2. Constrói o conteúdo Markdown
    # Usa a formatação Markdown (cabeçalhos, negrito)
    markdown_content = f"""## TÍTULO
{row['TÍTULO']}

## Público Específico
{row['PUBLICO ESPECÍFICO']}

## Categoria
{row['CATEGORIAS']} 

## Subcategoria
{row['SUBCATEGORIAS']}

## Órgão Responsável
{row['ÓRGÃO']}
"""

    # 3. Escreve o conteúdo no arquivo
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(markdown_content)
        print(f"Arquivo '{file_name}' criado com sucesso.")
    except Exception as e:
        print(f"Erro ao escrever o arquivo {file_name}: {e}")
        input()

print("\nProcesso concluído!")
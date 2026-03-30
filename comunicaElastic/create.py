from elasticsearch import Elasticsearch
import os
from dotenv import load_dotenv

load_dotenv()
# --- CONFIGURAÇÕES ---
# Pegue esses dados na aba "Endpoints" do console IBM Cloud
USER = os.getenv("DBUSER")
ELASTIC_PORT = os.getenv("ELASTIC_PORT")  # Verifique sua porta pública exata
ELASTIC_USER = os.getenv("ELASTIC_USER")
ELASTIC_PASSWORD = os.getenv("ELASTIC_PASSWORD") # Aquela definida em 'Settings'

# Caminho para o certificado que você baixou
CERT_PATH = "ac848ea9-9205-43ad-a6c8-84f8fea13c50(1)" 

# Criando a conexão
es = Elasticsearch(
    f"https://{ELASTIC_USER}:{ELASTIC_PASSWORD}@98a689dd-5b0d-49bf-a46c-c1a46954b986.c38qvnlz04atmdpus310.databases.appdomain.cloud:{ELASTIC_PORT}",
    verify_certs=True,
    ca_certs=CERT_PATH
)

INDEX_NAME = "servicos_rj"

def configurar_indice():
    # Definição das configurações de Português
    config = {
        "settings": {
            "analysis": {
                "filter": {
                    "portuguese_stop": {
                        "type": "stop",
                        "stopwords": "_portuguese_"
                    },
                    "portuguese_stemmer": {
                        "type": "stemmer",
                        "language": "light_portuguese"
                    }
                },
                "analyzer": {
                    "meu_analyzer_pt": {
                        "tokenizer": "standard",
                        "filter": [
                            "lowercase",       # Tudo em minúsculo
                            "asciifolding",    # Remove acentos (pão -> pao)
                            "portuguese_stop", # Remove "de", "com", "o"
                            "portuguese_stemmer" # Radicalização (vistorias -> vistori)
                        ]
                    }
                }
            }
        },
        "mappings": {
            "properties": {
                "id": {"type": "integer"},
                "slug": {"type": "keyword"},
                "titulo": {
                    "type": "text",
                    "analyzer": "meu_analyzer_pt",
                    "fields": {"keyword": {"type": "keyword"}} # Para ordenação
                },
                "descricao": {"type": "text", "analyzer": "meu_analyzer_pt"},
                "requisitos": {"type": "text", "analyzer": "meu_analyzer_pt"},
                "publico": {"type": "text", "analyzer": "meu_analyzer_pt"},
                "informacoes_extra": {"type": "text", "analyzer": "meu_analyzer_pt"},
                "orgao_nome": {"type": "keyword"},
                "categoria_slug": {"type": "keyword"},
                "total_avaliacao": {"type": "float"},
                "jornada": {
                    "type": "nested", # Permite busca independente em cada passo
                    "properties": {
                        "titulo": {"type": "text", "analyzer": "meu_analyzer_pt"},
                        "conteudo": {"type": "text", "analyzer": "meu_analyzer_pt"}
                    }
                },
                "created_at": {"type": "date"},
                "updated_at": {"type": "date"}
            }
        }
    }

    # Deleta o índice se já existir (CUIDADO: apaga os dados!)
    if es.indices.exists(index=INDEX_NAME):
        print(f"O índice {INDEX_NAME} já existe. Recriando...")
        es.indices.delete(index=INDEX_NAME)

    # Cria o índice com a configuração PT-BR
    res = es.indices.create(index=INDEX_NAME, body=config)
    print(f"Índice criado com sucesso: {res}")

if __name__ == "__main__":
    configurar_indice()

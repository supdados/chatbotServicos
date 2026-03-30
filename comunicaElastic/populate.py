import json
from elasticsearch import Elasticsearch, helpers
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

def populate_elastic():
    # Carregar o arquivo JSON
    with open("servicosApi.json", 'r', encoding='utf-8') as f:
        data = json.load(f)

    actions = []

    # O JSON fornecido é um objeto onde as chaves são "0", "1", etc.
    for key in data:
        item = data[key]
        
        # Preparar o documento conforme o mapping solicitado
        # Filtramos apenas os campos que o seu mapping espera
        documento = {
            "id": item.get("id"),
            "slug": item.get("slug"),
            "titulo": item.get("titulo"),
            "descricao": item.get("descricao") + " | custo: " + item.get("custo") + " | publico: " + item.get("publico") + " | requisitos: " + item.get("requisitos"),
            "informacoes_extra": item.get("informacoes_extra"),
            "orgao_nome": item.get("orgao_nome"),
            "categoria_slug": item.get("categoria_slug"), # No seu JSON isso é uma lista
            "total_avaliacao": item.get("total_avaliacao"),
            "created_at": item.get("created_at"),
            "updated_at": item.get("updated_at"),
            # Mapeando a jornada para conter apenas os campos do mapping
        }

        # Adicionar à lista de processamento em lote (Bulk)
        action = {
            "_index": "servicos_rj",
            "_id": documento["id"], # Usando o ID do serviço como ID do doc no ES
            "_source": documento
        }
        actions.append(action)

    # 2. Executar o Bulk Upload (mais eficiente que indexar um por um)
    try:
        success, failed = helpers.bulk(es, actions)
        print(f"Sucesso: {success} documentos inseridos.")
        if failed:
            print(f"Falhas detectadas: {failed}")
    except Exception as e:
        print(f"Erro ao inserir dados: {e}")

def testar_busca_termo(termo):
    query = {
            "query": { "multi_match":{
                "query": termo,
                "fields":["titulo", "descricao", "requisitos"]}
            }    }
    res = es.search(index="servicos_rj", body=query)
    print(f"Encontrados {res['hits']['total']['value']} resultados para: {termo}")
    for hit in res['hits']['hits']:
        print(f"- ID: {hit['_source']['id']} | Título: {hit['_source']['titulo']}")

# Exemplo de uso:
# testar_busca_texto("licenciamento")

if __name__ == "__main__":
    # Certifique-se de que o nome do arquivo esteja correto
    #populate_elastic()
    # Teste de busca
    testar_busca_termo('segunda via identidade')

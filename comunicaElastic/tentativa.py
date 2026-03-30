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

try:
    # Criando a conexão
    es = Elasticsearch(
        f"https://{ELASTIC_USER}:{ELASTIC_PASSWORD}@98a689dd-5b0d-49bf-a46c-c1a46954b986.c38qvnlz04atmdpus310.databases.appdomain.cloud:{ELASTIC_PORT}",
        verify_certs=True,
	ca_certs=CERT_PATH
    )

    # Testando a conexão
    print(es.info())
    if es.ping():
        print("✅ Conectado com sucesso ao Elasticsearch da IBM!")
        
        # Exemplo: Pegar informações do cluster
        info = es.info()
        print(f"Cluster Name: {info['cluster_name']}")
        print(f"Version: {info['version']['number']}")
    else:
        print("❌ Falha no ping. Verifique o Host/Porta.")
        print(es)

except Exception as e:
    print(f"💥 Erro ao conectar: {e}")

from langchain.document_loaders import DirectoryLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from google import genai
from google.genai import types
from dotenv import load_dotenv
import ollama
import os
import numpy as np
import json
import faiss
import time

load_dotenv()

DATA = "servicos"

def carregarDocumentos():
    loader = DirectoryLoader("servicos", glob='*.md')
    doc = loader.load()
    return doc

def dividirTexto(docs: list):
    divisor = RecursiveCharacterTextSplitter(
        chunk_size = 1000,
        chunk_overlap=500,
        length_function = len,
        add_start_index=True
    )
    chunks = divisor.split_documents(docs)
    return chunks

def pesquisar(embedded, embedding, newdict, index):
    matrix=np.empty((0,len(newdict[0]["embedding"])), dtype="float32")
    aux = ollama.embed(model = embedding, input=embedded)
    embed1 = np.array(aux.embeddings[0],dtype="float32").transpose()
    matrix = np.append(matrix, [embed1], axis=0)
    D, I = index.search(matrix, 10)
    
    return [D[0], I[0]]

def retirarServicos():
    doc = open("servicos-com-embeddings.json", "rb")
    servicos=json.load(doc)
    servi = {}
    for i in servicos:
        aux = i["embedding_text"].split("URL: ")
        servi[str(i["id"])] = ["ID: " + str(i["id"]) + '-' +aux[0], aux[1]]
    
    doc.close()
    doc = open("servicosEditados.json", "w", encoding='utf-8')
    json.dump(servi, doc)
    doc.close()
    return servi



client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
chat = client.chats.create(model="gemini-2.5-flash", config=types.GenerateContentConfig(system_instruction="Você é um chatbot do Estado do Rio de Janeiro, seu trabalho é auxiliar os cidadãos fluminenses da melhor maneira possível. Não ajude aqueles que demandam por opiniões pessoais ou informações ilegais. Seja o mais sucinto mais cordial nas respostas, não passe de 50 palavrasr"))
def fazerPergunta(pergunta, verbose= False):
    response = chat.send_message(pergunta)
    print(response.text)

def inicializarConsulta(modelo, pergunta = None, verbose = False):
    embeding = "snowflake-arctic-embed2:568m"

    doc = open("teste.json", "rb")
    newdict = json.load(doc)
    aux=np.empty((0,len(newdict[0]["embedding"])), dtype="float32")
    for i in newdict:
        aux = np.append(aux, [np.array(i["embedding"], dtype="float32")], axis=0)
    index = faiss.IndexFlatL2(aux.shape[1])
    print(aux.shape[1]) if verbose else ""
    index.add(aux)
    faiss.write_index(index, "teste.index")

    return fazerPergunta(embeding, newdict, index, pergunta,modelo, True)

   
while True:
    pergunta = input("Faça sua pergunta: ")
    if pergunta in ['tchau', 'bye', 'sair', 'exit']:
        break
    fazerPergunta(pergunta=pergunta)
import ollama
import json
import faiss
import numpy as np
from tqdm import tqdm
import os

def antigo():
    doc = open("chat3/servicos-com-embeddings.json", "rb")
    aux = json.load(doc)
    newdoc = open("chat3/teste.json", "w")
    newdict = []
    array = aux[137]
    desc, url = array['embedding_text'].split("URL")
    url = "URL"+url
    divi = int(len(array["embedding_text"])/2)
    array["embedding_text"] =array["embedding_text"][0:divi]
    array["embedding_text"] = array["embedding_text"] + " " + url
    aux[137] = array
    for i in tqdm(aux):
        if len(i["embedding_text"]) < 10:
            print(i["embedding_text"])
            input()
        newdict.append({"id": i["id"], "embedding_text":i["embedding_text"], "embedding":ollama.embed(model="bge-m3:latest", input=i["embedding_text"]).embeddings[0]})

    print(len(newdict[0]["embedding"]))


    json.dump(newdict,newdoc)

    aux=np.empty((0,len(newdict[0]["embedding"])), dtype="float32")
    for i in newdict:
        aux = np.append(aux, [np.array(i["embedding"], dtype="float32")], axis=0)
        
    index = faiss.IndexFlatIP(aux.shape[1])
    index.add(aux)
    faiss.write_index(index, "chat3/teste.index")

def novo():
    os.remove("servicosApi.index")
    fp = open("servicosApi.json", 'r', encoding="utf-8")
    servicos = json.load(fp)
    fp.close()
    for i in servicos:
        print(i," ", end="\r")
        textoEmbedding = servicos[i]['titulo'] + " " + servicos[i]['descricao']
        servicos[i]['embedding'] = ollama.embed(model="bge-m3:latest", input=textoEmbedding)['embeddings'][0]
    fp = open("servicosApiEmbedding.json", 'w', encoding="utf-8")
    json.dump(servicos, fp, indent=4)
    fp.close()
    aux=np.empty((0,len(servicos["0"]["embedding"])), dtype="float32")
    for i in servicos:
        print(i)
        aux = np.append(aux, [np.array(servicos[i]["embedding"], dtype="float32")], axis=0)

    index = faiss.IndexFlatIP(aux.shape[1])
    index.add(aux)
    faiss.write_index(index, "servicosApi.index")

def salvarUmEmbedding(servico):
    fp = open("servicosApiEmbedding.json", 'r', encoding="utf-8")
    servicos = json.load(fp)
    fp.close()
    textoEmbedding = servico['titulo'] + " " + servico['descricao']
    servico['embedding'] = ollama.embed(model="bge-m3:latest", input=textoEmbedding)['embeddings'][0]
    servicos[len(servicos)] = servico
    fp = open("servicosApiEmbedding.json", 'w', encoding="utf-8")
    json.dump(servicos, fp, indent=4)
    fp.close()

def atualizarFaiss():
    fp = open("servicosApiEmbedding.json", 'r', encoding="utf-8")
    servicos = json.load(fp)
    fp.close()
    aux=np.empty((0,len(servicos["0"]["embedding"])), dtype="float32")
    for i in servicos:
        print(i, end="\r")
        aux = np.append(aux, [np.array(servicos[i]["embedding"], dtype="float32")], axis=0)
    index = faiss.IndexFlatIP(aux.shape[1])
    index.add(aux)
    faiss.write_index(index, "testeApiServ.index")
    

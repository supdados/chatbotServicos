import ollama
import json
import faiss
import numpy as np
from tqdm import tqdm

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
    newdict.append({"id": i["id"], "embedding_text":i["embedding_text"], "embedding":ollama.embed(model="snowflake-arctic-embed2:568m", input=i["embedding_text"]).embeddings[0]})

print(len(newdict[0]["embedding"]))


json.dump(newdict,newdoc)

aux=np.empty((0,len(newdict[0]["embedding"])), dtype="float32")
for i in newdict:
    aux = np.append(aux, [np.array(i["embedding"], dtype="float32")], axis=0)
    
index = faiss.IndexFlatIP(aux.shape[1])
index.add(aux)
faiss.write_index(index, "chat3/teste.index")


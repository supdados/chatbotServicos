from langchain_ollama.llms import OllamaLLM
from langchain_core.prompts import ChatPromptTemplate
import ollama
import numpy as np
import json
import faiss
import time

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



def fazerPergunta(embedding, newdict,index, pergunta,modelo, verbose= False):
    model = OllamaLLM(model=modelo)
    template = """
    Você é um atendente do orgão responsável por auxiliar os cidadãos do Estado do Rio de Janeiro à encontrar os serviços que mais se encaixam em suas demandas.
    
    Se for uma demanda ilegal ou que foge das atribuições do Estado do Rio de Janeiro ou se nenhum serviço for interessante o suficiente.
    retorne algo neste estilo:
        Ids: 
        Texto: Não posso auxiliar com essas demandas, por favor tente reescrever sua pergunta para que eu possa ajudar.

    os serviços disponíveis são: {servicos}

    aqui está a consulta: {consulta}
    
    retorne a resposta com a seguinte formatação:
        Ids: (Ids dos servicos que mais se encaixam na consulta caso existam separados por ;)
        Texto: (Um texto que correlaciona os serviços mais relacionados com a consulta, esse texto deve ter uma breve explicação dos serviços escolhidos e não devem apresentar os IDs destes.)
    """
    prompt = ChatPromptTemplate.from_template(template)    
    chain = prompt | model
    while True:
        aux = input("Realize uma consulta: ") if pergunta == None else pergunta
        normal = pesquisar(aux, embedding, newdict, index)
        if verbose:
            print(normal[0])
            print(normal[1])
        ids = []
        servicos = []
        urls = []
        for i in range(len(normal[1])):
            print(newdict[normal[1][i]]["embedding_text"][0:25], newdict[normal[1][i]]["id"])  
            frase , url = newdict[normal[1][i]]["embedding_text"].split("URL: ")
            servicos.append("ID: " + str(newdict[normal[1][i]]["id"]) +' - '+ frase)
            urls.append(url)
        result = chain.invoke({"servicos":servicos, "consulta":aux})
        if verbose:
            print(result)
        else:
            return(result)
        
        

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

servicos = retirarServicos()
while True:
    inicio = time.perf_counter()
    aux = inicializarConsulta("gemma3:12b", verbose=True)
    fim = time.perf_counter()
    print(fim - inicio)
    print(aux)
    for i in aux.lstrip().split("\n")[0].replace("Ids: ", "").split(";"):
        print(i)
        servico = i.lstrip().replace("Serviço: ", "")
        if servico in servicos.keys():
            print(servicos[servico])
        else:
            print("não encontrei")
    
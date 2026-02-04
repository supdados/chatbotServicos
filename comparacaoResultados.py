import novoMetodo
import pandas as pd
import json

def testeComparativo():
    # Substitua 'caminho/do/seu/arquivo.csv' pelo caminho real do seu arquivo CSV
    caminho_arquivo = 'resposta_chatbot_servicos_pontuado_06.01.2026.xlsx - Dados.csv'

    # Lendo o arquivo CSV
    dados = pd.read_csv(caminho_arquivo)
    fp = open("resultadoComparação.csv",'w', encoding="utf-8")
    fp.write("id_conversa,pergunta_original,resposta,ids_retornados\n")
    # Exibindo as primeiras linhas do DataFrame
    linhas = dados.shape[0]
    agora = 0 
    for i in dados['pergunta_original']:
        agora+=1
        print(f"{int(agora/linhas*50)*"*"}{int(50-(agora/linhas*50))*"-"} | {agora/linhas*100:.2f}% ({agora}/{linhas})", end="\r")
        texto, ids = novoMetodo.perguntaSimplificada(i)
        fp.write(f"{dados['id_conversa'][agora-1]},{i.replace("\n", "")},{texto.replace("\n", "")},{ids}\n")
    fp.close()
    print()

testeComparativo()
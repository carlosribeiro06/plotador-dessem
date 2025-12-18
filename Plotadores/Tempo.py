import numpy as np
import pandas as pd
from pathlib import Path
from collections import defaultdict
import plotly.express as px
import plotly.graph_objects as go
from Leitura.leitor_arquivos import *
import os


df_milp = defaultdict(list)
df_milp["Datas"] = list(casos.keys())
df_pls = defaultdict(list)
df_pls["Datas"] = list(casos.keys())
df_leitura = defaultdict(list)
df_leitura["Datas"] = list(casos.keys())
def gera_df_tempo(caminho_sintese, casos, caso):
    for tempo in caminho_sintese.iterdir():
        if tempo.name == "TEMPO.parquet":
            tempo_parquet = caminho_sintese.joinpath(tempo.name)
            df_tempo = pd.read_parquet(tempo_parquet)
            df_leitura[caso.name].append(df_tempo.loc[df_tempo["etapa"] == "Leitura de Dados e Impressão", "tempo"].values[0]/60)
            df_milp[caso.name].append(df_tempo.loc[df_tempo["etapa"] == "MILP", "tempo"].values[0]/60)
            df_pls[caso.name].append(df_tempo.loc[(df_tempo["etapa"] == "PL") | (df_tempo["etapa"] == "PL.Int.Fix")  | (df_tempo["etapa"] == "PL.CalcCMO"), "tempo"].sum()/60)

    return df_milp, df_pls, df_leitura

def df_plot_tempo(df_milp, df_pls, df_leitura):
    y_list = list(casos.keys())
    y_list.remove("Datas")

    fig = px.bar(df_milp, x="Datas", y=y_list, title=f"Tempo MILP", barmode="group")
    fig.update_layout(
    xaxis_title='Data',  
    yaxis_title='Tempo em Minutos', 
    font=dict(family='Arial', size=12), 
    plot_bgcolor='white',
    autosize=False,   
    width=1400,      
    height=450     
    )
    fig.update_xaxes(showgrid=True, gridcolor="lightgray", gridwidth=1, type='category')
    fig.update_yaxes(showgrid=True, gridcolor="lightgray", gridwidth=1)
    out = f"grafico_MILP.html"
    caminho_arquivo = os.path.join(caminho_pasta, out)  
    fig.write_html(caminho_arquivo, include_plotlyjs="cdn")

    fig = px.bar(df_pls, x="Datas", y=y_list, title=f"Tempo PL", barmode="group")
    fig.update_layout(
    xaxis_title='Data',  
    yaxis_title='Tempo em Minutos', 
    font=dict(family='Arial', size=12), 
    plot_bgcolor='white',
    autosize=False,   
    width=1400,      
    height=450     
    )
    fig.update_xaxes(showgrid=True, gridcolor="lightgray", gridwidth=1, type='category')
    fig.update_yaxes(showgrid=True, gridcolor="lightgray", gridwidth=1)
    out = f"grafico_PL.html"
    caminho_arquivo = os.path.join(caminho_pasta, out)  
    fig.write_html(caminho_arquivo, include_plotlyjs="cdn")

    fig = px.bar(df_leitura, x="Datas", y=y_list, title=f"Tempo Leitura de Dados e Impressão", barmode="group")
    fig.update_layout(
    xaxis_title='Data',  
    yaxis_title='Tempo em Minutos', 
    font=dict(family='Arial', size=12), 
    plot_bgcolor='white',
    autosize=False,   
    width=1400,      
    height=450     
    )
    fig.update_xaxes(showgrid=True, gridcolor="lightgray", gridwidth=1, type='category')
    fig.update_yaxes(showgrid=True, gridcolor="lightgray", gridwidth=1)
    out = f"grafico_Leitura.html"
    caminho_arquivo = os.path.join(caminho_pasta, out)  
    fig.write_html(caminho_arquivo, include_plotlyjs="cdn")
    
    df_milp_resultante = pd.DataFrame(df_milp).drop(columns=["Datas"])
    df_pl_resultante = pd.DataFrame(df_pls).drop(columns=["Datas"])
    df_leitura_resultante = pd.DataFrame(df_leitura).drop(columns=["Datas"])

    df_total = df_milp_resultante + df_pl_resultante + df_leitura_resultante
    df_total["Datas"] = list(casos.keys())

    fig = px.bar(df_total, x="Datas", y=y_list, title=f"Tempo Total", barmode="group")
    fig.update_layout(
    xaxis_title='Data',  
    yaxis_title='Tempo em Minutos', 
    font=dict(family='Arial', size=12), 
    plot_bgcolor='white',
    autosize=False,   
    width=1400,      
    height=450     
    )
    fig.update_xaxes(showgrid=True, gridcolor="lightgray", gridwidth=1, type='category')
    fig.update_yaxes(showgrid=True, gridcolor="lightgray", gridwidth=1)
    out = f"grafico_total.html"
    caminho_arquivo = os.path.join(caminho_pasta, out)  
    fig.write_html(caminho_arquivo, include_plotlyjs="cdn")
  
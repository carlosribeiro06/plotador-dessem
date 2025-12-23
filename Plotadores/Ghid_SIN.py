import numpy as np
import pandas as pd
from pathlib import Path
from collections import defaultdict
import plotly.express as px
import plotly.graph_objects as go
from Leitura.leitor_arquivos import *
import os

df_ghid = defaultdict(list)
df_datas = defaultdict(list)
df_plot = defaultdict(list)
def gera_df_ghid_sin(caminho_sintese, casos, caso):
    for ghid in caminho_sintese.iterdir():
        if ghid.name == "GHID_SIN.parquet":
            ghid_parquet = caminho_sintese.joinpath(ghid.name)
            df_ghid_sin = pd.read_parquet(ghid_parquet)
            df_ghid[caso.name].append(df_ghid_sin.loc[df_ghid_sin["estagio"] <= 48])

    return df_ghid

def df_plot_ghid_sin(df_ghid):
    y_list = list(df_ghid.keys())
    for caso in y_list:
        aux = pd.concat(df_ghid[caso], ignore_index=True)
        df_plot[caso] = aux["valor"].values
        if len(df_datas) == 0:
            df_datas["Datas"] = np.unique(aux["data_inicio"])

    df_plot["Datas"] = df_datas["Datas"]
    fig = px.line(df_plot, x="Datas", y=y_list)
    fig.update_layout(
    hovermode="x unified",
    xaxis_title='Data',  
    yaxis_title='Geração Hidráulica (MW)', 
    font=dict(family='Arial', size=12), 
    plot_bgcolor='white',
    autosize=False,   
    width=1400,      
    height=450     
    )
    fig.update_xaxes(showgrid=True, gridcolor="lightgray", gridwidth=1, type='category', tickformat="%d/%m/%Y %H:%M")
    fig.update_yaxes(showgrid=True, gridcolor="lightgray", gridwidth=1)
    out = f"grafico_ghid_sin.html"
    caminho_arquivo = os.path.join(caminho_pasta, out)  
    fig.write_html(caminho_arquivo, include_plotlyjs="cdn")
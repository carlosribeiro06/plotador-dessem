import numpy as np
import pandas as pd
from pathlib import Path
from collections import defaultdict
import plotly.express as px
import plotly.graph_objects as go
from Leitura.leitor_arquivos import *
import os

df_gter = defaultdict(list)
df_datas = defaultdict(list)
df_plot = defaultdict(list)
def gera_df_gter_sin(caminho_sintese, casos, caso):
    for gter in caminho_sintese.iterdir():
        if gter.name == "GTER_SIN.parquet":
            gter_parquet = caminho_sintese.joinpath(gter.name)
            df_gter_sin = pd.read_parquet(gter_parquet)
            df_gter[caso.name].append(df_gter_sin)
            if len(df_datas) == 0:
                df_datas["Datas"] = df_gter_sin.loc[(df_gter_sin["estagio"] <= 48), "data_inicio"].values

    return df_gter, df_datas

def df_plot_gter_sin(df_gter, df_datas):
    y_list = list(df_gter.keys())
    df_plot = defaultdict(list)
    for caso in y_list:
        df_plot[caso] = df_gter[caso][0].loc[(df_gter[caso][0]["estagio"] <= 48), "valor"].values
    df_plot["Datas"] = pd.to_datetime(df_datas["Datas"])
    fig = px.line(df_plot, x="Datas", y=y_list)
    fig.update_layout(
    hovermode="x unified",
    xaxis_title='Data',  
    yaxis_title='Geração Térmica (MW)', 
    font=dict(family='Arial', size=12), 
    plot_bgcolor='white',
    autosize=False,   
    width=1400,      
    height=450     
    )
    fig.update_xaxes(showgrid=True, gridcolor="lightgray", gridwidth=1, type='category', tickformat="%d/%m/%Y %H:%M")
    fig.update_yaxes(showgrid=True, gridcolor="lightgray", gridwidth=1)
    out = f"grafico_gter_sin.html"
    caminho_arquivo = os.path.join(caminho_pasta, out)  
    fig.write_html(caminho_arquivo, include_plotlyjs="cdn")
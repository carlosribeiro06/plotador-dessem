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
submercados = [1, 2, 3, 4]
def gera_df_ghid_sbm(caminho_sintese, casos, caso):
    for ghid in caminho_sintese.iterdir():
        if ghid.name == "GHID_SBM.parquet":
            ghid_parquet = caminho_sintese.joinpath(ghid.name)
            df_ghid_sbm = pd.read_parquet(ghid_parquet)
            df_ghid[caso.name].append(df_ghid_sbm)
            if len(df_datas) == 0:
                df_datas["Datas"] = df_ghid_sbm.loc[(df_ghid_sbm["estagio"] <= 48) & (df_ghid_sbm["codigo_submercado"] == 1), "data_inicio"].values

    return df_ghid, df_datas

def df_plot_ghid_sbm(df_ghid, df_datas):
    y_list = list(df_ghid.keys())
    df_plot = defaultdict(list)
    for sbm in submercados:
        for caso in y_list:
            df_plot[caso] = df_ghid[caso][0].loc[(df_ghid[caso][0]["estagio"] <= 48) & (df_ghid[caso][0]["codigo_submercado"] == sbm), "valor"].values
        df_plot["Datas"] = pd.to_datetime(df_datas["Datas"])
        fig = px.line(df_plot, x="Datas", y=y_list, title=f"Tempo MILP")
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
        out = f"grafico_ghid_sbm{sbm}.html"
        caminho_arquivo = os.path.join(caminho_pasta, out)  
        fig.write_html(caminho_arquivo, include_plotlyjs="cdn")
import numpy as np
import pandas as pd
from pathlib import Path
from collections import defaultdict
import plotly.express as px
import plotly.graph_objects as go
from Leitura.leitor_arquivos import *
import os

df_cmo = defaultdict(list)
df_datas = defaultdict(list)
df_plot = defaultdict(list)
submercados = [1, 2, 3, 4]
def gera_df_cmo_sbm(caminho_sintese, casos, caso):
    for cmo in caminho_sintese.iterdir():
        if cmo.name == "CMO_SBM.parquet":
            cmo_parquet = caminho_sintese.joinpath(cmo.name)
            df_cmo_sbm = pd.read_parquet(cmo_parquet)
            df_cmo[caso.name].append(df_cmo_sbm)
            if len(df_datas) == 0:
                df_datas["Datas"] = df_cmo_sbm.loc[(df_cmo_sbm["estagio"] <= 48) & (df_cmo_sbm["codigo_submercado"] == 1), "data_inicio"].values

    return df_cmo, df_datas

def df_plot_cmo_sbm(df_cmo, df_datas):
    y_list = list(df_cmo.keys())
    df_plot = defaultdict(list)
    for sbm in submercados:
        for caso in y_list:
            df_plot[caso] = df_cmo[caso][0].loc[(df_cmo[caso][0]["estagio"] <= 48) & (df_cmo[caso][0]["codigo_submercado"] == sbm), "valor"].values
        df_plot["Datas"] = pd.to_datetime(df_datas["Datas"])
        fig = px.line(df_plot, x="Datas", y=y_list)
        fig.update_layout(
        hovermode="x unified",
        xaxis_title='Data',  
        yaxis_title='Custo Marginal de Operação (R$/MWh)', 
        font=dict(family='Arial', size=12), 
        plot_bgcolor='white',
        autosize=False,   
        width=1400,      
        height=450     
        )
        fig.update_xaxes(showgrid=True, gridcolor="lightgray", gridwidth=1, type='category', tickformat="%d/%m/%Y %H:%M")
        fig.update_yaxes(showgrid=True, gridcolor="lightgray", gridwidth=1)
        out = f"grafico_cmo_sbm{sbm}.html"
        caminho_arquivo = os.path.join(caminho_pasta, out)  
        fig.write_html(caminho_arquivo, include_plotlyjs="cdn")
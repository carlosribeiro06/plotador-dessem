import numpy as np
import pandas as pd
from pathlib import Path
from collections import defaultdict
import plotly.express as px
import plotly.graph_objects as go
from Leitura.leitor_arquivos import *
import os


df_cp = defaultdict(list)
df_cp["Datas"] = list(casos.keys())
df_cf = defaultdict(list)
df_cf["Datas"] = list(casos.keys())
def gera_df_custos(caminho_sintese, casos, caso):
    for custos in caminho_sintese.iterdir():
        if custos.name == "CUSTOS.parquet":
            custos_parquet = caminho_sintese.joinpath(custos.name)
            df_custos = pd.read_parquet(custos_parquet)
            df_cp[caso.name].append(df_custos.loc[df_custos["parcela"] == "PRESENTE", "valor_esperado"].values[0])
            df_cf[caso.name].append(df_custos.loc[df_custos["parcela"] == "FUTURO", "valor_esperado"].values[0])

    return df_cp, df_cf

def df_plot_custos(df_cp, df_cf):
    y_list = list(df_cp.keys())
    y_list.remove("Datas")

    fig = px.bar(df_cp, x="Datas", y=y_list, barmode="group")
    fig.update_layout(
    hovermode="x unified",
    xaxis_title='Data',  
    yaxis_title='Custo Presente (R$)', 
    font=dict(family='Arial', size=12), 
    plot_bgcolor='white',
    autosize=False,   
    width=1400,      
    height=450     
    )
    fig.update_xaxes(showgrid=True, gridcolor="lightgray", gridwidth=1, type='category')
    fig.update_yaxes(showgrid=True, gridcolor="lightgray", gridwidth=1)
    out = f"grafico_custo_presente.html"
    caminho_arquivo = os.path.join(caminho_pasta, out)  
    fig.write_html(caminho_arquivo, include_plotlyjs="cdn")

    fig = px.bar(df_cf, x="Datas", y=y_list, barmode="group")
    fig.update_layout(
    hovermode="x unified",
    xaxis_title='Data',  
    yaxis_title='Custo Futuro (R$)', 
    font=dict(family='Arial', size=12), 
    plot_bgcolor='white',
    autosize=False,   
    width=1400,      
    height=450     
    )
    fig.update_traces(textposition='outside')
    fig.update_xaxes(showgrid=True, gridcolor="lightgray", gridwidth=1, type='category')
    fig.update_yaxes(showgrid=True, gridcolor="lightgray", gridwidth=1)
    out = f"grafico_custo_futuro.html"
    caminho_arquivo = os.path.join(caminho_pasta, out)  
    fig.write_html(caminho_arquivo, include_plotlyjs="cdn")

    df_cp_resultante = pd.DataFrame(df_cp).drop(columns=["Datas"])
    df_cf_resultante = pd.DataFrame(df_cf).drop(columns=["Datas"])

    df_total = df_cp_resultante + df_cf_resultante
    df_total["Datas"] = list(casos.keys())

    fig = px.bar(df_total, x="Datas", y=y_list, barmode="group")
    fig.update_layout(
    hovermode="x unified",
    xaxis_title='Data',  
    yaxis_title='Custo Total de Operação (R$)', 
    font=dict(family='Arial', size=12), 
    plot_bgcolor='white',
    autosize=False,   
    width=1400,      
    height=450     
    )
    fig.update_traces(textposition='outside')
    fig.update_xaxes(showgrid=True, gridcolor="lightgray", gridwidth=1, type='category')
    fig.update_yaxes(showgrid=True, gridcolor="lightgray", gridwidth=1)
    out = f"grafico_custo_total.html"
    caminho_arquivo = os.path.join(caminho_pasta, out)  
    fig.write_html(caminho_arquivo, include_plotlyjs="cdn")
  
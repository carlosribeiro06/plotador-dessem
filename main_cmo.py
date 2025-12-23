import numpy as np
import pandas as pd
from pathlib import Path
from collections import defaultdict
from Plotadores.Tempo import *
from Plotadores.CMO_sbm import *
from Leitura.leitor_arquivos import *
import plotly.express as px
import plotly.graph_objects as go
import sys
import os


for pasta in caminho_pasta.iterdir():
    if pasta.name in casos.keys():
        for caso in pasta.iterdir():
            if caso.name in casos[data]:
                caminho_sintese = caso.joinpath(caso, "sintese")
                df_cmo = gera_df_cmo_sbm(caminho_sintese, casos, caso)
                
df_plot_cmo_sbm(df_cmo)



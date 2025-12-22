import numpy as np
import pandas as pd
from pathlib import Path
from collections import defaultdict
from Plotadores.Custos import *
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
                df_cp, df_cd =  gera_df_custos(caminho_sintese, casos, caso)
                
df_plot_custos(df_cp, df_cf)




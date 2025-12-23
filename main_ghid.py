import numpy as np
import pandas as pd
from pathlib import Path
from collections import defaultdict
from Plotadores.Ghid_sbm import *
from Plotadores.Ghid_SIN import *
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
                df_ghid_sbm= gera_df_ghid_sbm(caminho_sintese, casos, caso)
                df_ghid_sin = gera_df_ghid_sin(caminho_sintese, casos, caso)


df_plot_ghid_sbm(df_ghid_sbm)
df_plot_ghid_sin(df_ghid_sin)



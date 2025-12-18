import numpy as np
import pandas as pd
from pathlib import Path
from collections import defaultdict
from Plotadores.Tempo import *
from Leitura.leitor_arquivos import *
import plotly.express as px
import plotly.graph_objects as go
import sys
import os

aciona_plot_tempo = int(sys.argv[1])

for pasta in caminho_pasta.iterdir():
    if pasta.name in casos.keys():
        for caso in pasta.iterdir():
            if caso.name in casos[data]:
                caminho_sintese = caso.joinpath(caso, "sintese")
                df_tempo_milp, df_tempo_pl, df_tempo_leitura = gera_df_tempo(caminho_sintese, casos, caso)
                
if aciona_plot_tempo == 1:
    df_plot_tempo(df_tempo_milp, df_pls, df_tempo_leitura)



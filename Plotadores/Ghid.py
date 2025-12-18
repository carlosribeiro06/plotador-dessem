import numpy as np
import pandas as pd
from pathlib import Path
from collections import defaultdict
import plotly.express as px
import plotly.graph_objects as go
from Leitura.leitor_arquivos import *
import os

df_submercado = defaultdict(list)
def gera_df_ghid_sbm(caminho_sintese, casos, caso):
    for ghid in caminho_sintese.iterdir():
        if ghid.name == "GHID_SBM.parquet":
            ghid_parquet = caminho_sintese.joinpath(ghid.name)
            df_ghid = pd.read_parquet(ghid_parquet)

    return df_ghid
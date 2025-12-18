import numpy as np
import pandas as pd
from pathlib import Path
from collections import defaultdict
import plotly.express as px
import plotly.graph_objects as go

caminho_pasta = Path("C:/Users/carlo/OneDrive/Documentos/git/plotador-dessem")

casos = {}
casos = defaultdict(list)
for pasta in caminho_pasta.iterdir():
    if pasta.is_dir():
        # procura recursivamente por uma pasta chamada "sintese"
        encontrou = any(
            p.is_dir() and p.name == "sintese"
            for p in pasta.rglob("*")
        )
        if encontrou:
            data = pasta.name
            for caso in pasta.iterdir():
                # procura recursivamente por uma pasta chamada "sintese"
                encontrou = any(
                    p.is_dir() and p.name == "sintese"
                    for p in caso.rglob("*")
                )
                if encontrou:
                    casos[data].append(caso.name)
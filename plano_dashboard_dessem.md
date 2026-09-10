# Projeto: Dashboard HTML para Comparação de Resultados do DESSEM

## Objetivo

Desenvolver uma aplicação Python profissional e modular capaz de gerar um dashboard HTML interativo a partir dos arquivos Parquet de síntese produzidos pelos modelos DESSEM.

O dashboard deverá possibilitar análises comparativas entre dois ou mais casos de estudo, permitindo visualizar diferenças e tendências dos resultados através de gráficos interativos em múltiplos níveis de agregação.

---

## Escopo Funcional

### 1. Comparação simultânea de múltiplos casos

O programa deverá receber como entrada uma ou mais pastas contendo casos processados do DESSEM.

Exemplo:

```bash
python dashboard_dessem.py \
    --casos caso_oficial caso_gurobi caso_teste
```

Cada pasta representa um cenário distinto e deverá possuir a estrutura dos decks processados contendo a subpasta:

```text
<caso>/
├── deck_20260501/
│   └── sintese/
├── deck_20260502/
│   └── sintese/
...
```

O sistema deverá:

- Identificar automaticamente todos os decks existentes.
- Ler os arquivos Parquet presentes na pasta `exemplo` de cada deck.
- Consolidar os dados de todos os decks pertencentes ao mesmo caso.
- Comparar os resultados entre todos os casos informados.

Nos gráficos, cada caso deverá ser representado por uma curva distinta, utilizando como legenda o nome da pasta informada.

Exemplo:

```text
Legenda:
■ caso_oficial
■ caso_gurobi
■ caso_teste
```

---

### 2. Geração automática dos gráficos

O dashboard deverá gerar automaticamente todos os gráficos que possam ser construídos a partir dos dados disponíveis nos arquivos de síntese.

Os gráficos devem contemplar, no mínimo:

#### Nível SIN

- Geração térmica
- Geração hidrelétrica
- Geração não simulada
- Custo total
- Custo presente
- Custo futuro
- EARMF
- Volume armazenado

#### Nível de Submercado

- Carga
- Geração hidráulica
- Geração térmica
- Geração não simualada
- CMO
- Intercâmbios
- Volume armazenado

#### Nível de Usina Hidrelétrica

- Geração
- Turbinamento
- Vertimento
- Volume armazenado
- Defluência
- Vazão

#### Nível de Usina Termelétrica

- Geração

### 3. Sistema de filtros avançados

O dashboard deverá possuir mecanismos de filtragem para facilitar a navegação em bases com grande quantidade de usinas.

Para elementos identificados por código e nome (ex.: térmicas e hidrelétricas), disponibilizar simultaneamente:

#### Filtro por Nome

```text
Pesquisar usina...
```

#### Filtro por Código

```text
Código da usina...
```

Os filtros deverão funcionar de forma independente ou combinada.

Exemplo:

- Digitar o nome da usina.
- Digitar o código.
- Utilizar qualquer um dos dois para localizar o elemento desejado.

O comportamento esperado é semelhante aos mecanismos de busca encontrados em ferramentas de Business Intelligence.

---

### 4. Eixo temporal dos gráficos

Os gráficos não devem utilizar o número do período como eixo horizontal.

O eixo X deverá apresentar:

```text
Data + Hora
```

Exemplo:

```text
01/05/2026 00:00
01/05/2026 01:00
01/05/2026 02:00
...
```

O objetivo é que o usuário visualize diretamente a evolução temporal dos resultados.

Durante o desenvolvimento, deverá ser avaliado se os arquivos de síntese já possuem informações suficientes para reconstruir o timestamp real ou se será necessário utilizar informações adicionais dos decks originais.

---

## Arquitetura e Qualidade do Código

O repositório deverá ser refatorado para seguir padrões profissionais de desenvolvimento.

### Objetivos da refatoração

- Código modular.
- Separação clara de responsabilidades.
- Facilidade de manutenção.
- Facilidade para inclusão de novos gráficos.
- Facilidade para inclusão de novos arquivos de síntese.

Sugestão de estrutura:

```text
src/
├── cli/
├── data/
├── parsers/
├── models/
├── dashboard/
├── visualizacao/
├── assets/
└── utils/
```

---

## Dashboard

### Tecnologia

O resultado final deverá ser um único arquivo HTML contendo:

- Todos os gráficos.
- Todos os filtros.
- Todos os dados necessários para navegação.

O dashboard deverá funcionar sem necessidade de servidor.

Exemplo:

```bash
python dashboard_dessem.py ...
```

Saída:

```text
dashboard_dessem.html
```

---

## Identidade Visual

O dashboard deverá possuir identidade visual institucional alinhada ao ONS.

### Diretrizes

Utilizar exclusivamente:

```text
/logo
```

presente no repositório.

Não utilizar logotipos externos ou versões não fornecidas.

### Manual da Marca

Seguir as orientações do documento:

```text
UsoCorreto da Marca_VR_dezembro2018.pdf
```

Localização:

```text
/home/carlosribeiro/git/plotador-dessem/UsoCorreto da Marca_VR_dezembro2018.pdf
```

### Rodapé

Adicionar obrigatoriamente a inscrição:

```text
Gerência de Ferramentas Energéticas - FEN
```

---

## Tratamento da Pasta de Síntese

Os arquivos de síntese serão utilizados apenas como dados de entrada e não deverão ser versionados.

Criar um arquivo `.gitignore` contendo:

```gitignore
exemplo/
*.pdf
logo/
*.md
```

ou a regra equivalente necessária para impedir o versionamento dos arquivos gerados.

---

## Entradas

O programa deverá aceitar:

```text
1 ou mais casos
```

Exemplo:

```bash
python dashboard_dessem.py \
    --casos caso_oficial caso_gurobi
```

ou

```bash
python dashboard_dessem.py \
    --casos caso_oficial caso_gurobi caso_teste
```

---

## Saída

Gerar um dashboard HTML único:

```text
dashboard_dessem.html
```

com:

- Comparação entre casos;
- Filtros interativos;
- Navegação por nível de agregação;
- Gráficos temporais;
- Identidade visual institucional;
- Funcionamento offline.

---

# Critérios de Sucesso

O projeto será considerado concluído quando:

1. For possível comparar dois ou mais casos simultaneamente.
2. Todos os Parquets de síntese forem processados automaticamente.
3. Os gráficos forem gerados para todos os níveis de agregação disponíveis.
4. Os filtros por nome e código funcionarem corretamente.
5. O eixo temporal apresentar data e hora reais.
6. O dashboard HTML operar sem dependência de servidor.
7. A identidade visual seguir as diretrizes da marca ONS.
8. O código estiver modularizado e preparado para futuras expansões.

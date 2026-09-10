# Handoff prompt — start plan execution in a new chat

Copy everything inside the fenced block below into a **new Claude Code chat opened at the repository
root** (`/home/carlosribeiro/git/plotador-dessem` in WSL, or its UNC path
`\\wsl.localhost\Ubuntu\home\carlosribeiro\git\plotador-dessem` from Windows). It carries every
decision needed to run `/implement-plan` without re-asking what was settled on 2026-09-10.

```text
Execute o plano de implementação em plans/dashboard-dessem/ com o skill /implement-plan:

/implement-plan plans/dashboard-dessem

Contexto do plano (criado em 10/09/2026 pelo /plan a partir de plano_dashboard_dessem.md):
- Feature: dashboard HTML único e offline para comparar resultados de síntese do DESSEM entre
  cenários (--casos), com dois modos de visualização (Por deck / Encadeado), toggle
  Absoluto/Diferença, filtros por nome e código de usina e identidade visual ONS.
- 5 épicos, 38 tickets: épicos 1–2 detalhados (tickets 001–018, prontidão ≥ 0,94), épicos 3–5 em
  outline (019–038), a refinar just-in-time com o aprendizado dos anteriores.
- Tier de rigor: Full (guardian após cada ticket, simplify + review nas fronteiras de épico).
- Scaffolding do projeto (pyproject com uv, settings.json validado, logging rich + arquivo rotativo,
  run manifest, layout src/tests) é o Épico 1, aplicado na raiz do repositório atual.

Leitura obrigatória ANTES do primeiro ticket, nesta ordem:
1. plans/dashboard-dessem/README.md (navegação, grafo de dependências, ordem de execução, fases)
2. plans/dashboard-dessem/planning-context.md (decisões vinculantes 1–17; nunca contradizer)
3. plans/dashboard-dessem/00-master-plan.md (decisões de projeto, Apêndice A = modelo de dados dos
   Parquet, Apêndice B = contrato do settings.json)
4. plans/dashboard-dessem/reference/parquet-schemas.txt só se o Apêndice A não bastar

Modo de implementação: Rigoroso — follow the mode policy in CLAUDE.md. Identificadores,
comentários, docstrings, README e testes em inglês, comentários mínimos. Textos voltados ao
usuário em português: flags e --help da CLI (--casos, conforme a spec), mensagens de log, mensagens
de erro no terminal e toda a interface do dashboard. Inclua a linha
"Implementation mode: Rigoroso — follow the mode policy in CLAUDE.md." em todo dispatch de agente.

Estratégia de execução: AINDA NÃO ESCOLHIDA. Antes de despachar o ticket-001, pergunte-me
(AskUserQuestion) Phased ou Continuous — recomendação: Phased, com Phase Checkpoint e parada de
aprovação ao fim de cada épico — e registre a escolha em .implementation-state.json
(execution_strategy) e na seção "Phases & Estimates" do README do plano.

Ambiente:
- Repositório em WSL Ubuntu: /home/carlosribeiro/git/plotador-dessem. Python de sistema 3.14.4
  (/usr/bin/python3) SEM pandas/pyarrow/plotly; uv disponível em /snap/bin/uv. Crie o .venv com uv
  (uv venv; uv pip install -e ".[dev]") — o pyproject nasce no ticket-002.
- Se a sessão estiver rodando do lado Windows, execute os comandos do WSL via
  wsl.exe -e bash -lc '<comando>' e escreva arquivos pelo caminho UNC.
- Alvo: requires-python >= 3.12; pandas >= 3.0 (colunas de texto vêm como dtype str), pyarrow,
  plotly >= 6 (apenas como fonte do plotly.min.js via plotly.offline.get_plotlyjs()), rich;
  dev: pytest, pytest-cov, ruff, mypy --strict.

Git — você tem liberdade para commitar e fazer push:
- Remoto: origin = git@github.com:carlosribeiro06/plotador-dessem.git, branch main. Faça um commit
  por ticket concluído (após o guardian aprovar) e push para origin main logo em seguida. Commits
  convencionais (feat:, fix:, chore:, docs:, test:, refactor:), mensagem em português focada no
  "porquê", terminando com a linha:
  Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
- Primeiro commit da sessão, antes do ticket-001: adicione POR CAMINHO EXPLÍCITO plans/,
  plano_dashboard_dessem.md e logo/ (chore: adiciona plano do dashboard DESSEM) e faça push.
  Nunca use git add -A antes de o .gitignore existir: a raiz tem um PDF e exemplo/ com 300 Parquet
  locais que não podem ser versionados.
- A árvore tem 240 exclusões intencionais em exemplo/ (reestruturei a pasta). O ticket-001 cria o
  .gitignore (inclua .claude/settings.local.json nele), faz git rm -r --cached de exemplo/ e dos
  __pycache__, commita tudo junto e faz push. Nunca use git checkout, git clean ou git rm sem
  --cached nessa pasta.
- Nunca force-push; nunca commite exemplo/, HTML gerado, logs, .venv ou segredos. Se um push for
  rejeitado, mostre o erro e pare.
- logo/ e *.md ficam versionados (a sugestão da spec de ignorá-los foi rejeitada).

Dados de exemplo (locais, ignorados pelo git): exemplo/caso_oficial/{2024-03-03,2024-03-04}/sintese
e exemplo/caso_gurobi/{2024-03-03,2024-03-04}/sintese (60 Parquet cada, reconstruídos do histórico
git); exemplo/sintese/ é só uma amostra plana da estrutura e NÃO é um cenário válido. Comando de
exemplo para o README e para o teste de integração:
  dessem-dashboard --casos exemplo/caso_oficial exemplo/caso_gurobi

Questões abertas do master plan: 1–3 têm defaults declarados (custo total = PRESENTE + FUTURO;
UHE "Volume armazenado" entrega VARMF e VARPF; UHE "Vazão" entrega QAFL e QINC) e não bloqueiam;
4 e 5 estão resolvidas (ver planning-context.md, itens 14–17).

Regras de trabalho:
- Anti-simplificação (CLAUDE.md): ao encontrar ambiguidade ou bloqueio não coberto pelo
  planning-context.md, PARE, liste opções com trade-offs e recomendação, e aguarde minha escolha.
  Nunca interprete silenciosamente nem remova funcionalidade para fazer algo passar.
- Após cada ticket, atualize .implementation-state.json e o README do plano (invariante do
  /implement-plan) e inclua essa atualização no commit do ticket. Nas fronteiras de épico, extraia
  os aprendizados (epic-XX-learnings.md) e refine os outlines do épico seguinte antes de
  despachá-los.
- Logs de auditoria (console rich + arquivo) e run_manifest.json em toda execução da CLI.
```

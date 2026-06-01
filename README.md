# TasksDia — Relatório diário de Azure DevOps

Gera um relatório dos work items movimentados **hoje** por um usuário no Azure
DevOps, agrupados pelo **card pai** (Product Backlog Item / User Story / Bug /
Feature). O card é trazido como contexto **mesmo quando ele não foi movimentado
no dia** — resolvendo o caso em que só a Task é mexida e o card relacionado some
do relatório.

## Pré-requisitos

- Python 3.8+ (somente biblioteca padrão, sem dependências externas).
- Um **Personal Access Token (PAT)** do Azure DevOps com o escopo
  **Work Items (Read)**.

## Uso

```bash
export AZURE_DEVOPS_PAT="<seu_pat_com_escopo_Work_Items_Read>"
python3 relatorio_azdo.py

# salvando também em Markdown:
python3 relatorio_azdo.py --md relatorio.md
```

### Variáveis de ambiente

| Variável            | Obrigatória | Padrão                                          |
|---------------------|-------------|-------------------------------------------------|
| `AZURE_DEVOPS_PAT`  | Sim         | —                                               |
| `AZDO_ORG`          | Não         | `https://dev.azure.com/automindautomacao`       |
| `AZDO_USER`         | Não         | `hidelbrando.abreu@automind.com.br`             |

## Como funciona

1. Executa uma query **WIQL** na organização (cobre todos os projetos) buscando
   itens com `ChangedBy = usuário` e `ChangedDate >= @today`.
2. Carrega os detalhes via batch e **resolve a hierarquia de pais**
   (`System.Parent`) recursivamente.
3. Agrupa cada item movimentado sob seu **card pai**; itens tipo Task sobem até
   o primeiro ancestral que seja um card.
4. Imprime o relatório. O símbolo `★` marca o que foi movido hoje; um card sem
   `★` foi trazido apenas como contexto.

## Observações sobre execução agendada (Claude Code on the web)

- **Não** deixe o PAT hardcoded no prompt da tarefa. Guarde-o na configuração do
  ambiente (idealmente em *Secrets*) e referencie via `AZURE_DEVOPS_PAT`.
- Use `api-version=6.0` (estável). A `7.0` exige o sufixo `-preview`.
- O escopo do PAT precisa incluir **Work Items (Read)** — sem isso a query WIQL
  retorna `401`.

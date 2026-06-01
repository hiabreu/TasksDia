#!/usr/bin/env python3
"""
Relatório diário de work items movimentados no Azure DevOps.

Busca todos os work items alterados HOJE por um usuário e gera um relatório
agrupado pelo CARD pai (Product Backlog Item / User Story / Bug / Feature),
trazendo o card como contexto mesmo quando ele NÃO foi movimentado no dia.

Uso:
    export AZURE_DEVOPS_PAT="<seu_pat_com_escopo_Work_Items_Read>"
    python3 relatorio_azdo.py
    python3 relatorio_azdo.py --md relatorio.md   # também salva em Markdown

Requisitos: Python 3.8+ (somente biblioteca padrão).
O PAT precisa do escopo "Work Items (Read)".
"""
import os
import sys
import json
import base64
import argparse
import urllib.request
import urllib.error
from datetime import datetime, timezone, timedelta

# ----------------------------------------------------------------------------
# Configuração
# ----------------------------------------------------------------------------
ORG = os.environ.get("AZDO_ORG", "https://dev.azure.com/automindautomacao")
USER = os.environ.get("AZDO_USER", "hidelbrando.abreu@automind.com.br")
PAT = os.environ.get("AZURE_DEVOPS_PAT", "")

BRT = timezone(timedelta(hours=-3))  # America/Sao_Paulo (sem horário de verão)
CARD_TYPES = {"Product Backlog Item", "User Story", "Bug", "Feature", "Issue"}
FIELDS = ",".join([
    "System.Id", "System.Title", "System.State", "System.WorkItemType",
    "System.ChangedDate", "System.TeamProject", "System.Parent",
])

if not PAT:
    sys.exit("ERRO: variável de ambiente AZURE_DEVOPS_PAT não definida.")

AUTH = "Basic " + base64.b64encode(f":{PAT}".encode()).decode()


# ----------------------------------------------------------------------------
# Cliente da API REST
# ----------------------------------------------------------------------------
def api(method, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(f"{ORG}/{path}", data=data, method=method)
    req.add_header("Authorization", AUTH)
    if body is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="replace")[:500]
        sys.exit(f"ERRO HTTP {e.code} em {path}\n{detail}")


def get_items(ids):
    """Busca work items em lotes de 50 (limite do batch da API)."""
    out, ids = [], list(ids)
    for i in range(0, len(ids), 50):
        chunk = ",".join(str(x) for x in ids[i:i + 50])
        r = api("GET", f"_apis/wit/workitems?ids={chunk}&fields={FIELDS}&api-version=6.0")
        out += r.get("value", [])
    return out


# ----------------------------------------------------------------------------
# Coleta de dados
# ----------------------------------------------------------------------------
def coletar():
    # 1. IDs movimentados hoje (query cobre toda a organização)
    wiql = {"query": (
        "SELECT [System.Id] FROM WorkItems "
        f"WHERE [System.ChangedBy] = '{USER}' "
        "AND [System.ChangedDate] >= @today "
        "ORDER BY [System.ChangedDate] DESC"
    )}
    res = api("POST", "_apis/wit/wiql?api-version=6.0", wiql)
    today_ids = [w["id"] for w in res.get("workItems", [])][:50]

    # 2. Carrega itens de hoje + resolve ancestrais (pais) recursivamente
    cache = {}

    def load(ids):
        need = [i for i in ids if i not in cache]
        for it in get_items(need):
            cache[it["fields"]["System.Id"]] = it

    load(today_ids)
    frontier = set(today_ids)
    while frontier:
        parents = {cache[i]["fields"].get("System.Parent")
                   for i in frontier if i in cache}
        parents = {p for p in parents if p and p not in cache}
        if not parents:
            break
        load(parents)
        frontier = parents

    return today_ids, cache


# ----------------------------------------------------------------------------
# Montagem do relatório
# ----------------------------------------------------------------------------
def field(cache, i, key, default=""):
    return cache.get(i, {}).get("fields", {}).get(key, default)


def fmt_dt(s):
    if not s:
        return "—"
    dt = datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(BRT)
    return dt.strftime("%d/%m/%Y %H:%M")


def card_of(cache, i):
    """Sobe a hierarquia até o primeiro item tipo-card; senão, usa o pai direto."""
    if field(cache, i, "System.WorkItemType") in CARD_TYPES:
        return i
    cur = i
    p = field(cache, i, "System.Parent")
    while p and p in cache:
        if field(cache, p, "System.WorkItemType") in CARD_TYPES:
            return p
        cur, p = p, field(cache, p, "System.Parent")
    return field(cache, i, "System.Parent") or i


def gerar_relatorio(today_ids, cache):
    today_set = set(today_ids)
    groups = {}
    for i in today_ids:
        groups.setdefault(card_of(cache, i), []).append(i)

    now = datetime.now(BRT)
    L = []  # linhas do relatório
    L.append("=" * 64)
    L.append(f"SESSÃO DO DIA - {now.strftime('%d/%m/%Y')} {now.strftime('%H:%M')} (BRT)")
    L.append(f"Usuário: {USER}")
    L.append("=" * 64)
    L.append("")

    if not today_ids:
        L.append("Nenhuma tarefa movimentada hoje.")
        L.append("=" * 64)
        return "\n".join(L)

    projetos = set()
    ordenado = sorted(groups.items(),
                      key=lambda kv: (field(cache, kv[0], "System.TeamProject"), kv[0]))
    for card, ids in ordenado:
        proj = field(cache, card, "System.TeamProject")
        projetos.add(proj)
        moved = "★ movido hoje" if card in today_set else "contexto (não movido hoje)"
        epic = field(cache, card, "System.Parent")
        epic_txt = (f" | Epic: #{epic} {field(cache, epic, 'System.Title')}"
                    if epic in cache else "")
        L.append(f"Projeto: {proj}")
        L.append(f"┌─ CARD #{card} [{field(cache, card, 'System.WorkItemType')}] "
                 f"· {field(cache, card, 'System.State')} · {moved}")
        L.append(f"│  {field(cache, card, 'System.Title')}{epic_txt}")
        L.append("│")
        for i in sorted(c for c in ids if c != card):
            m = "★" if i in today_set else " "
            L.append(f"│  {m} #{i:<6} [{field(cache, i, 'System.WorkItemType'):<5}] "
                     f"{field(cache, i, 'System.State'):<22} "
                     f"{field(cache, i, 'System.Title')[:46]}")
        movs = [field(cache, i, "System.ChangedDate") for i in ids if i in today_set]
        if movs:
            L.append("│")
            L.append(f"└─ Última movimentação: {fmt_dt(max(movs))} (BRT)")
        L.append("")

    L.append("=" * 64)
    L.append(f"Total geral: {len(today_ids)} tarefa(s) movimentada(s) "
             f"em {len(projetos)} projeto(s)")
    L.append("★ = movido hoje · CARD sem ★ = pai trazido como contexto")
    L.append("=" * 64)
    return "\n".join(L)


# ----------------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description="Relatório diário Azure DevOps")
    ap.add_argument("--md", metavar="ARQUIVO",
                    help="salva uma cópia do relatório em Markdown")
    args = ap.parse_args()

    today_ids, cache = coletar()
    relatorio = gerar_relatorio(today_ids, cache)
    print(relatorio)

    if args.md:
        with open(args.md, "w", encoding="utf-8") as f:
            f.write("```\n" + relatorio + "\n```\n")
        print(f"\n[salvo em {args.md}]")


if __name__ == "__main__":
    main()

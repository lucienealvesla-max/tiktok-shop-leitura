# -*- coding: utf-8 -*-
"""As vendas, de onde vierem, numa forma só.

DUAS FONTES, UM FORMATO. A API de afiliado (afiliado.py) entrega pedidos
crus com nomes de campo que não estão verificados; a Central de Afiliados no
app exporta CSV com colunas em português que mudam de tela para tela. Este
arquivo lê as duas e devolve "linhas de venda" iguais:

    {"quando": "AAAA-MM-DD", "pedido_id": ..., "video_id": ..., "video_url": ...,
     "video_titulo": ..., "produto_id": ..., "produto": ..., "pedidos": n,
     "valor": R$, "comissao": R$, "status": ..., "fonte": "api" | "csv:nome"}

Uma linha da API é um pedido (pedidos = 1). Uma linha de CSV pode ser um
agregado (um vídeo num período) — por isso `pedidos` é um número e não um
booleano. Os painéis somam `pedidos`, `valor` e `comissao`; nunca contam
linhas.

TOLERÂNCIA, NÃO ADIVINHAÇÃO. Cada campo é procurado por uma lista de nomes
prováveis; o que não for encontrado fica `None`, e `fontes()` diz para a tela
o que cada arquivo tinha e o que faltou ("CSV sem coluna de vídeo"). Um painel
que não tem o dado diz que não tem; não inventa.
"""

import csv
import json
import os
import re
import sys
import unicodedata
from datetime import datetime
from pathlib import Path

PASTA = Path(__file__).resolve().parent
sys.path.insert(0, str(PASTA))

BASE = Path(os.environ.get("TIKTOK_SHOP_DADOS") or PASTA)
VENDAS = BASE / "vendas"
VENDAS_API = VENDAS / "api"


# --------------------------------------------------------------- utilidades

def _sem_acento(s):
    return "".join(c for c in unicodedata.normalize("NFD", str(s or ""))
                   if unicodedata.category(c) != "Mn").lower().strip()


def _numero(x):
    """'R$ 1.234,56' → 1234.56; '1,234.56' → 1234.56; None → None.

    Dinheiro na API vem como {"amount": "39.90", "currency": "BRL"}: o valor
    está em `amount`. Passar o dicionário inteiro pelo caminho de texto
    transformava 39,90 em 3.990 — a vírgula do JSON entrava na conta.
    """
    if x is None:
        return None
    if isinstance(x, bool):
        return None
    if isinstance(x, (int, float)):
        return float(x)
    if isinstance(x, dict):
        for k in ("amount", "value", "total", "price"):
            if x.get(k) is not None:
                return _numero(x[k])
        return None
    s = re.sub(r"[^\d,.\-]", "", str(x)).strip(",.")
    if not s:
        return None
    if "," in s and "." in s:
        # decide pelo último separador
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif "," in s:
        s = s.replace(",", ".") if len(s.split(",")[-1]) <= 2 else s.replace(",", "")
    try:
        return float(s)
    except ValueError:
        return None


def _dia(x):
    """Qualquer coisa que pareça data → 'AAAA-MM-DD', ou None."""
    if x is None or x == "":
        return None
    if isinstance(x, (int, float)):
        v = float(x)
        if v > 10 ** 12:
            v /= 1000.0
        try:
            return datetime.fromtimestamp(v).strftime("%Y-%m-%d")
        except (ValueError, OSError, OverflowError):
            return None
    s = str(x).strip()
    if re.fullmatch(r"\d{10}(\d{3})?", s):
        return _dia(int(s))
    for fmt in ("%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%d/%m/%Y",
                "%d/%m/%Y %H:%M", "%d/%m/%Y %H:%M:%S", "%Y/%m/%d", "%m/%d/%Y"):
        try:
            return datetime.strptime(s[:len(fmt) + 2] if "T" in fmt else s, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", s)
    return "%s-%s-%s" % m.groups() if m else None


def _acha(d, nomes, profundidade=3):
    """O primeiro valor cujo nome de chave (sem acento, minúsculo) esteja em
    `nomes`, procurando também dentro de dicionários aninhados."""
    if not isinstance(d, dict) or profundidade < 0:
        return None
    alvo = [_sem_acento(n) for n in nomes]
    for k, v in d.items():
        if _sem_acento(k) in alvo and v not in (None, "", []):
            return v
    for k, v in d.items():
        if isinstance(v, dict):
            r = _acha(v, nomes, profundidade - 1)
            if r is not None:
                return r
    return None


def _id_do_video_na_url(url):
    m = re.search(r"/video/(\d+)", str(url or ""))
    return m.group(1) if m else None


# ------------------------------------------------------------------- da API

NOMES = {
    "pedido_id": ["order_id", "id", "affiliate_order_id"],
    "quando": ["create_time", "order_create_time", "paid_time", "pay_time", "update_time"],
    "status": ["order_status", "status", "commission_status", "affiliate_order_status"],
    "video_id": ["content_id", "video_id", "item_id", "post_id", "aweme_id"],
    "video_url": ["content_url", "video_url", "share_url"],
    "produto_id": ["product_id", "spu_id"],
    "produto": ["product_name", "name", "title"],
    "sku": ["sku_id", "sku_name"],
    "valor": ["gmv", "order_amount", "amount", "sale_price", "price", "sub_total", "total_amount"],
    "comissao": ["estimated_commission", "commission", "commission_amount", "actual_commission",
                 "expected_commission", "affiliate_commission"],
    "itens": ["line_items", "items", "order_line_items", "skus", "products"],
}


def _linha_da_api(pedido, item=None, dia_da_leitura=None):
    def busca(nomes):
        # O item (linha do pedido) manda; o que ele não tiver vem do pedido.
        v = _acha(item, nomes) if item is not None else None
        return v if v is not None else _acha(pedido, nomes)
    url = busca(NOMES["video_url"])
    vid = busca(NOMES["video_id"]) or _id_do_video_na_url(url)
    valor = _numero(busca(NOMES["valor"]))
    comissao = _numero(busca(NOMES["comissao"]))
    return {
        "quando": _dia(busca(NOMES["quando"])) or dia_da_leitura,
        "pedido_id": str(busca(NOMES["pedido_id"]) or ""),
        "video_id": str(vid) if vid else None,
        "video_url": url,
        "video_titulo": None,
        "produto_id": str(busca(NOMES["produto_id"]) or "") or None,
        "produto": busca(NOMES["produto"]),
        "pedidos": 1,
        "valor": valor,
        "comissao": comissao,
        "status": busca(NOMES["status"]),
        "fonte": "api",
    }


def da_api():
    """As linhas de venda das respostas cruas. Pedido repetido em dois dias
    (a janela sobrepõe 7 dias de propósito) fica com a versão mais recente."""
    if not VENDAS_API.is_dir():
        return [], []
    por_pedido, avisos = {}, []
    for p in sorted(VENDAS_API.glob("*.json")):
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            avisos.append("%s ilegível" % p.name)
            continue
        for ped in d.get("pedidos") or []:
            if not isinstance(ped, dict):
                continue
            itens = _acha(ped, NOMES["itens"])
            linhas = ([_linha_da_api(ped, i, p.stem) for i in itens if isinstance(i, dict)]
                      if isinstance(itens, list) and itens else [_linha_da_api(ped, None, p.stem)])
            for n, l in enumerate(linhas):
                chave = (l["pedido_id"] or (p.stem + ":" + str(id(ped)))) + "#" + str(n)
                por_pedido[chave] = l          # o dia mais novo sobrescreve
    return list(por_pedido.values()), avisos


# ------------------------------------------------------------------ do CSV

COLUNAS = {
    "quando": ["data", "date", "dia", "periodo", "period", "data do pedido", "order time",
               "hora do pedido", "created time"],
    "video_id": ["video id", "id do video", "content id", "id do conteudo", "item id", "post id"],
    "video_url": ["link do video", "video link", "video url", "url", "link"],
    "video_titulo": ["video", "titulo do video", "video title", "conteudo", "content", "nome do video",
                     "titulo"],
    "produto_id": ["product id", "id do produto", "sku id"],
    "produto": ["produto", "product", "product name", "nome do produto", "item"],
    "pedidos": ["pedidos", "orders", "qtd pedidos", "numero de pedidos", "itens vendidos",
                "items sold", "unidades"],
    "valor": ["gmv", "receita", "revenue", "valor", "vendas", "sales", "valor do pedido",
              "video gmv"],
    "comissao": ["comissao", "commission", "comissao estimada", "estimated commission",
                 "comissao paga", "ganhos", "earnings"],
    "status": ["status", "situacao", "order status"],
}


def _mapa_de_colunas(cabecalho):
    """Que coluna do CSV responde por cada campo. Primeira que bater, na ordem
    de `COLUNAS`, comparando sem acento e sem caixa."""
    limpo = {_sem_acento(c): c for c in cabecalho}
    mapa = {}
    for campo, nomes in COLUNAS.items():
        for n in nomes:
            if n in limpo and limpo[n] not in mapa.values():
                mapa[campo] = limpo[n]
                break
    return mapa


def do_csv():
    """As linhas de venda de todos os CSVs em vendas/. (linhas, fontes)

    `fontes` diz, por arquivo, quantas linhas vieram e que campos faltaram:
    é o que a tela mostra para ela saber se o export que fez serve.
    """
    if not VENDAS.is_dir():
        return [], []
    linhas, fontes = [], []
    for p in sorted(VENDAS.glob("*.csv")):
        try:
            texto = p.read_text(encoding="utf-8-sig")
        except (OSError, UnicodeDecodeError):
            try:
                texto = p.read_text(encoding="latin-1")
            except OSError:
                fontes.append({"arquivo": p.name, "linhas": 0, "erro": "ilegível"})
                continue
        try:
            dialeto = csv.Sniffer().sniff(texto[:4096], delimiters=",;\t")
        except csv.Error:
            dialeto = csv.excel
        leitor = csv.DictReader(texto.splitlines(), dialect=dialeto)
        mapa = _mapa_de_colunas(leitor.fieldnames or [])
        n = 0
        for row in leitor:
            g = lambda campo: row.get(mapa[campo]) if campo in mapa else None
            url = g("video_url")
            vid = g("video_id") or _id_do_video_na_url(url) or _id_do_video_na_url(g("video_titulo"))
            pedidos = _numero(g("pedidos"))
            linhas.append({
                "quando": _dia(g("quando")) or datetime.fromtimestamp(p.stat().st_mtime).strftime("%Y-%m-%d"),
                "pedido_id": None,
                "video_id": str(vid).strip() if vid else None,
                "video_url": url,
                "video_titulo": g("video_titulo"),
                "produto_id": g("produto_id"),
                "produto": g("produto"),
                "pedidos": int(pedidos) if pedidos is not None else (1 if "pedidos" not in mapa else 0),
                "valor": _numero(g("valor")),
                "comissao": _numero(g("comissao")),
                "status": g("status"),
                "fonte": "csv:" + p.name,
            })
            n += 1
        faltam = [c for c in ("quando", "video_id", "produto", "pedidos", "comissao") if c not in mapa]
        if "video_id" in faltam and ("video_url" in mapa or "video_titulo" in mapa):
            faltam.remove("video_id")
        fontes.append({"arquivo": p.name, "linhas": n, "colunas": mapa,
                       "faltam": faltam})
    return linhas, fontes


# ------------------------------------------------------------------- tudo

def todas():
    """Todas as linhas de venda, das duas fontes, e o relatório das fontes."""
    api, avisos = da_api()
    csv_, fontes = do_csv()
    if VENDAS_API.is_dir() and list(VENDAS_API.glob("*.json")):
        fontes.insert(0, {"arquivo": "api", "linhas": len(api),
                          "faltam": [c for c in ("video_id", "produto", "comissao")
                                     if api and all(l.get(c) is None for l in api)],
                          "avisos": avisos})
    return api + csv_, fontes

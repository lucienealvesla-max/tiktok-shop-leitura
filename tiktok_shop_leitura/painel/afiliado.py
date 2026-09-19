# -*- coding: utf-8 -*-
"""A Central de Afiliados do TikTok Shop: pedidos e comissão, pela API.

POR QUE ISTO EXISTE (19/09/2026). Tudo que o painel media até aqui era
audiência: views, likes, largada. Para quem vende, view é proxy — um vídeo de
300 views que vendeu 8 unidades vale mais que um de 50 mil que não vendeu, e
a tela dizia o contrário. A Display API não tem pedido nenhum; isso mora na
API de afiliado do TikTok Shop, que é OUTRO app, OUTRO portal (Partner
Center), OUTRA autorização — feita pela própria criadora com a conta de
afiliada.

O QUE ESTÁ VERIFICADO e o que não está, porque a diferença decide o desenho:

  VERIFICADO (fixture da própria doc do TikTok, no teste deste arquivo):
    - a assinatura: HMAC-SHA256 com o app_secret como chave sobre
      app_secret + path + parâmetros ordenados (sem `sign`/`access_token`)
      + corpo JSON + app_secret, em hexadecimal;
    - a origem `open-api.tiktokglobalshop.com`, o cabeçalho
      `x-tts-access-token`, os parâmetros `app_key`/`timestamp`/`sign`;
    - a troca e a renovação do token em `auth.tiktok-shops.com/api/v2/token/`.

  NÃO VERIFICADO (a doc do Partner Center só abre com JavaScript):
    - o corpo exato e os campos da resposta de
      `/affiliate_creator/202405/orders/search`;
    - se o pedido traz o id do VÍDEO que vendeu (é a pergunta 1 do plano).

Por isso este módulo GUARDA A RESPOSTA CRUA de cada dia em
`/share/tiktok-shop/vendas/api/AAAA-MM-DD.json` antes de tentar entender
qualquer coisa — o mesmo princípio das fotografias de vídeos: métrica que eu
inventar depois pode ser calculada sobre este passado, e um campo que eu
adivinhei errado hoje não perde o dado. A normalização (`vendas.py`) é
tolerante a nomes, e o log diz quais campos vieram na primeira leitura.

DESLIGADO POR PADRÃO: sem `/share/tiktok-shop/afiliado.json` nada aqui roda.
"""

import hashlib
import hmac
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path

PASTA = Path(__file__).resolve().parent
sys.path.insert(0, str(PASTA))

BASE = Path(os.environ.get("TIKTOK_SHOP_DADOS") or PASTA)
CONFIG = BASE / "afiliado.json"
VENDAS = BASE / "vendas"            # CSVs exportados à mão ficam aqui
VENDAS_API = VENDAS / "api"         # respostas cruas da API, uma por dia

API = "https://open-api.tiktokglobalshop.com"
TOKEN = "https://auth.tiktok-shops.com"
VERSAO_API = "202405"
CAMINHO_PEDIDOS = "/affiliate_creator/{versao}/orders/search"

# QUANTOS DIAS PARA TRÁS na primeira leitura. Pedido tem histórico na API
# (ao contrário de view, que só existe se alguém fotografou), então a
# primeira leitura puxa o que der. 90 é o que o Creator Center mostra.
JANELA_INICIAL_DIAS = 90


# ------------------------------------------------------------------ config

def _config():
    try:
        return json.loads(CONFIG.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _gravar_config(cfg):
    temp = CONFIG.with_suffix(".json.novo")
    temp.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(CONFIG)
    try:
        os.chmod(CONFIG, 0o600)
    except OSError:
        pass


def configurado():
    """Tem app_key e app_secret. Sem isso, nada aqui fala com a internet."""
    cfg = _config()
    return bool((cfg.get("app_key") or "").strip() and (cfg.get("app_secret") or "").strip())


def conectado():
    """Tem token de acesso. Configurado sem token = falta autorizar."""
    return bool((_config().get("access_token") or "").strip())


def estado():
    """O que a tela precisa saber. Nunca levanta, nunca expõe segredo."""
    cfg = _config()
    ultimo = None
    try:
        arquivos = sorted(VENDAS_API.glob("*.json")) if VENDAS_API.is_dir() else []
        ultimo = arquivos[-1].stem if arquivos else None
    except OSError:
        pass
    return {"configurado": configurado(), "conectado": conectado(),
            "ultima_leitura": ultimo,
            "ultimo_erro": cfg.get("ultimo_erro"),
            "versao_api": cfg.get("versao_api") or VERSAO_API}


# -------------------------------------------------------------- assinatura

def assinar(path, query, corpo, app_secret):
    """A assinatura do TikTok Shop Open Platform. Verificada contra a fixture
    da doc: path /authorization/202309/shops, app_key 29a39d, timestamp
    1623812664, secret e59af819cc → b596b73e0cc6de07ac26f036364178ab16b0a907
    af13d43f0a0cd2345f582dc8. `corpo` é o TEXTO exato que vai no pedido."""
    partes = "".join("%s%s" % (k, query[k]) for k in sorted(query)
                     if k not in ("sign", "access_token") and query[k] is not None)
    mensagem = app_secret + path + partes + (corpo or "") + app_secret
    return hmac.new(app_secret.encode("utf-8"), mensagem.encode("utf-8"),
                    hashlib.sha256).hexdigest()


def _corpo(obj):
    # O mesmo texto assinado e enviado: sem espaços, sem escapar acento —
    # igual ao JSON.stringify que a fixture do TikTok usa.
    return json.dumps(obj, separators=(",", ":"), ensure_ascii=False) if obj is not None else ""


def _pedir(url, corpo=None, cabecalhos=None, metodo="GET"):
    """(ok, dados). Nunca levanta."""
    dados = corpo.encode("utf-8") if corpo else None
    req = urllib.request.Request(url, data=dados, method=metodo)
    for k, v in (cabecalhos or {}).items():
        req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=40) as r:
            return True, json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            return False, json.loads(e.read().decode("utf-8"))
        except Exception:
            return False, {"erro": "HTTP %s" % e.code}
    except Exception as e:
        return False, {"erro": str(e)}


def chamar(path, query=None, corpo_obj=None, metodo="GET"):
    """Um pedido assinado à API, com o token válido. (ok, resposta).

    A resposta do TikTok Shop vem sempre como {"code": 0, "message": "Success",
    "data": {...}}; `code` diferente de zero é erro mesmo com HTTP 200.
    """
    cfg = _config()
    token, erro = _token_valido(cfg)
    if not token:
        return False, {"erro": erro}
    query = dict(query or {})
    query["app_key"] = cfg["app_key"]
    query["timestamp"] = int(time.time())
    if cfg.get("shop_cipher"):
        query["shop_cipher"] = cfg["shop_cipher"]
    corpo = _corpo(corpo_obj) if corpo_obj is not None else ""
    query["sign"] = assinar(path, query, corpo, cfg["app_secret"])
    url = API + path + "?" + urllib.parse.urlencode(query)
    ok, d = _pedir(url, corpo or None,
                   {"content-type": "application/json", "x-tts-access-token": token},
                   metodo)
    d = d if isinstance(d, dict) else {"erro": str(d)}
    if ok and d.get("code") not in (0, "0", None):
        return False, {"erro": "%s (code %s)" % (d.get("message"), d.get("code")),
                       "code": d.get("code"), "request_id": d.get("request_id")}
    return ok, d


# ------------------------------------------------------------------ token

def _token_valido(cfg):
    """(access_token, erro). Renova quando faltar menos de 5 min.

    `access_token_expire_in` no TikTok Shop é um INSTANTE (epoch em segundos),
    não uma duração — ao contrário do nome. Valor pequeno (< 10^9) é tratado
    como duração a partir de `obtido_em`, por garantia.
    """
    if not cfg.get("access_token"):
        return None, "Central de Afiliados não autorizada"
    vence = cfg.get("access_token_expire_in") or 0
    try:
        vence = float(vence)
    except (TypeError, ValueError):
        vence = 0
    if 0 < vence < 10 ** 9:
        vence = float(cfg.get("obtido_em") or 0) + vence
    if not vence or time.time() < vence - 300:
        return cfg["access_token"], None
    ok, d = renovar()
    if not ok:
        return None, d.get("erro")
    return d["access_token"], None


def _guardar_token(dados):
    cfg = _config()
    for k in ("access_token", "refresh_token", "access_token_expire_in",
              "refresh_token_expire_in", "open_id", "seller_name", "granted_scopes"):
        if dados.get(k) is not None:
            cfg[k] = dados[k]
    cfg["obtido_em"] = int(time.time())
    cfg.pop("ultimo_erro", None)
    _gravar_config(cfg)


def trocar_codigo(auth_code):
    """Troca o `code` do retorno da autorização pelo token. (ok, mensagem)

    A autorização é feita pela criadora no navegador (link do Partner Center
    → seu app → Authorize). O TikTok devolve para o endereço de retorno do
    app com `?code=...`; esse código é colado aqui, como no login do TikTok.
    """
    cfg = _config()
    if not configurado():
        return False, "falta app_key/app_secret em %s" % CONFIG
    q = urllib.parse.urlencode({"app_key": cfg["app_key"], "app_secret": cfg["app_secret"],
                                "auth_code": auth_code, "grant_type": "authorized_code"})
    ok, d = _pedir(TOKEN + "/api/v2/token/get?" + q)
    dados = (d or {}).get("data") or {}
    if not ok or not dados.get("access_token"):
        return False, str((d or {}).get("message") or (d or {}).get("erro") or d)
    _guardar_token(dados)
    return True, "autorizado%s" % ((": " + str(dados.get("seller_name")))
                                    if dados.get("seller_name") else "")


def renovar():
    """(ok, dados|erro). O refresh_token PODE mudar; guardar o novo é obrigatório."""
    cfg = _config()
    if not cfg.get("refresh_token"):
        return False, {"erro": "sem refresh_token: autorize de novo"}
    q = urllib.parse.urlencode({"app_key": cfg["app_key"], "app_secret": cfg["app_secret"],
                                "refresh_token": cfg["refresh_token"],
                                "grant_type": "refresh_token"})
    ok, d = _pedir(TOKEN + "/api/v2/token/refresh?" + q)
    dados = (d or {}).get("data") or {}
    if not ok or not dados.get("access_token"):
        return False, {"erro": "não consegui renovar: %s"
                       % ((d or {}).get("message") or (d or {}).get("erro") or d)}
    _guardar_token(dados)
    return True, dados


# ---------------------------------------------------------------- pedidos

def _lista_de_pedidos(data):
    """Onde está a lista na resposta. Nome não verificado: tenta os usuais e,
    se nenhum bater, a primeira lista de dicionários que houver."""
    for k in ("orders", "order_list", "affiliate_orders", "list", "items"):
        if isinstance(data.get(k), list):
            return data[k], k
    for k, v in data.items():
        if isinstance(v, list) and v and isinstance(v[0], dict):
            return v, k
    return [], None


def puxar_pedidos(desde, ate, versao=None, tamanho=50, paginas_max=200):
    """Todos os pedidos entre dois instantes (epoch s). (ok, dados)

    `dados` traz `pedidos` (lista crua, como veio), `paginas`, `parcial` e
    `motivo`, e `campos` — os nomes de campo do primeiro pedido, para o log
    dizer o que a API entregou de verdade.
    """
    versao = versao or _config().get("versao_api") or VERSAO_API
    path = CAMINHO_PEDIDOS.format(versao=versao)
    pedidos, pagina, token_pagina = [], 0, None
    chave_lista = None
    while pagina < paginas_max:
        query = {"page_size": tamanho}
        if token_pagina:
            query["page_token"] = token_pagina
        corpo = {"create_time_ge": int(desde), "create_time_lt": int(ate)}
        ok, d = chamar(path, query, corpo, "POST")
        if not ok:
            return bool(pedidos), {"pedidos": pedidos, "paginas": pagina, "parcial": True,
                                   "motivo": "a API recusou a página %d: %s"
                                             % (pagina + 1, d.get("erro")),
                                   "erro": d.get("erro"), "caminho": path}
        data = d.get("data") or {}
        lista, chave_lista = _lista_de_pedidos(data)
        pedidos.extend(lista)
        pagina += 1
        token_pagina = data.get("next_page_token") or data.get("next_cursor") or data.get("cursor")
        if not token_pagina or not lista:
            break
    return True, {"pedidos": pedidos, "paginas": pagina, "parcial": False,
                  "motivo": "fim da lista", "caminho": path,
                  "chave_lista": chave_lista,
                  "campos": sorted((pedidos[0] if pedidos else {}).keys())}


def guardar_resposta(dados, dia=None):
    """A resposta crua do dia, em vendas/api/AAAA-MM-DD.json. (ok, caminho)"""
    dia = dia or datetime.now().strftime("%Y-%m-%d")
    try:
        VENDAS_API.mkdir(parents=True, exist_ok=True)
        alvo = VENDAS_API / (dia + ".json")
        registro = dict(dados)
        registro["lido_em"] = int(time.time())
        temp = alvo.with_suffix(".json.novo")
        temp.write_text(json.dumps(registro, ensure_ascii=False), encoding="utf-8")
        temp.replace(alvo)
        return True, str(alvo)
    except OSError as e:
        return False, str(e)


def leitura_diaria():
    """Puxa os pedidos e guarda a resposta crua. (ok, recado). Nunca levanta.

    Janela: da última leitura (menos 7 dias, porque pedido muda de status e
    a API pode recontar) até agora; na primeira vez, 90 dias. Sobrepor dias é
    barato e é o que evita buraco quando o Pi ficou desligado.
    """
    try:
        if not configurado():
            return False, "Central de Afiliados não configurada (sem afiliado.json)"
        if not conectado():
            return False, "Central de Afiliados não autorizada"
        agora = int(time.time())
        cfg = _config()
        ultima = cfg.get("ultima_leitura_em")
        desde = (int(ultima) - 7 * 86400) if ultima else (agora - JANELA_INICIAL_DIAS * 86400)
        ok, d = puxar_pedidos(desde, agora)
        d["desde"] = desde
        d["ate"] = agora
        guardou, onde = guardar_resposta(d)
        cfg = _config()
        if ok:
            cfg["ultima_leitura_em"] = agora
            cfg.pop("ultimo_erro", None)
        else:
            cfg["ultimo_erro"] = d.get("erro")
        _gravar_config(cfg)
        recado = "%d pedido(s) em %d página(s)%s" % (
            len(d.get("pedidos") or []), d.get("paginas") or 0,
            "" if not d.get("parcial") else " — PELA METADE: " + str(d.get("motivo")))
        if d.get("campos"):
            recado += " · campos: " + ",".join(d["campos"][:12])
        if not guardou:
            recado += " · NÃO GRAVOU: " + onde
        return ok, recado
    except Exception as e:
        return False, "leitura de pedidos quebrou: %s" % e


# ------------------------------------------------------------------- CLI

def _teste_de_assinatura():
    esperado = "b596b73e0cc6de07ac26f036364178ab16b0a907af13d43f0a0cd2345f582dc8"
    saiu = assinar("/authorization/202309/shops",
                   {"app_key": "29a39d", "timestamp": 1623812664}, "", "e59af819cc")
    return saiu == esperado, saiu


if __name__ == "__main__":
    # python3 afiliado.py testar            -> confere a assinatura
    # python3 afiliado.py conectar <code>   -> troca o codigo pelo token
    # python3 afiliado.py ler               -> leitura de hoje
    acao = sys.argv[1] if len(sys.argv) > 1 else "testar"
    if acao == "testar":
        ok, saiu = _teste_de_assinatura()
        print("assinatura:", "ok" if ok else "ERRADA (%s)" % saiu)
        print("estado:", json.dumps(estado(), ensure_ascii=False))
    elif acao == "conectar" and len(sys.argv) > 2:
        print(trocar_codigo(sys.argv[2]))
    elif acao == "ler":
        print(leitura_diaria())
    else:
        print("uso: afiliado.py testar | conectar <code> | ler")

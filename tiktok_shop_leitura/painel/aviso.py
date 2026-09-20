# -*- coding: utf-8 -*-
"""O resumo do dia no celular, pelo Home Assistant.

POR QUE ISTO EXISTE (19/09/2026, fase C.1). A Owra vende "aviso de vídeo
decolando" e "alerta de produto tracionando". O painel já sabe as duas coisas
— estão na pauta todo dia — mas só para quem abre a tela. Um aviso no celular
é o que faz a informação chegar na hora em que ainda dá para reagir, e o
Home Assistant já entrega push de graça (`notify.mobile_app_*`).

UMA VEZ POR DIA, NA HORA DO AVISO — não na hora da leitura. A leitura roda à
1h da manhã porque o dia anterior está inteiro; ninguém quer push à 1h. O
relógio acorda de novo à `hora_do_aviso` (padrão 8h), lê o painel pronto e
manda. Um arquivo por conta guarda o dia já avisado: reinício do add-on não
manda o mesmo resumo duas vezes.

O QUE VAI NO AVISO: só o que muda decisão — seguidores e quanto mudaram,
ritmo de views contra a regra, as primeiras linhas da pauta (é onde "vídeo
decolou" e "produto vendeu" já moram) e as vendas de 7 dias se houver fonte.
Sem enfeite: a tela inteira está a um toque.

COMO CHEGA: `POST http://supervisor/core/api/services/notify/<serviço>` com
o SUPERVISOR_TOKEN — exige `homeassistant_api: true` no config.yaml. Sem
serviço configurado (opção `avisar` vazia), nada aqui roda.
"""

import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

PASTA = Path(__file__).resolve().parent
sys.path.insert(0, str(PASTA))

CORE = "http://supervisor/core/api"
ARQUIVO = "aviso.json"


def servicos():
    """Os serviços de notificação, da opção `avisar` do add-on. Aceita
    'notify.mobile_app_x' ou só 'mobile_app_x'."""
    bruto = os.environ.get("TIKTOK_SHOP_AVISAR") or ""
    fora = []
    for s in bruto.replace(";", ",").split(","):
        s = s.strip()
        if not s:
            continue
        fora.append(s[len("notify."):] if s.startswith("notify.") else s)
    return fora


def configurado():
    return bool(servicos()) and bool(os.environ.get("SUPERVISOR_TOKEN"))


def _milhar(x, casas=0):
    if x is None:
        return "—"
    s = ("{:,.%df}" % casas).format(float(x))
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


def montar(painel, nome):
    """(título, mensagem) a partir do painel pronto. Curto de propósito."""
    m = painel.get("monetizacao") or {}
    v = painel.get("vendas") or {}
    linhas = []

    seg = m.get("seguidores")
    if seg is not None:
        delta = m.get("seguidores_ganho_ultimo")
        linhas.append("Seguidores: %s%s" % (
            _milhar(seg),
            (" (%s%s)" % ("+" if delta >= 0 else "", _milhar(delta))) if delta is not None else ""))
    if m.get("pronto") and m.get("views_30d") is not None:
        linhas.append("Views/30 d: %s (%sx a regra%s)" % (
            _milhar(m["views_30d"]), m.get("views_vezes"),
            ", projetado" if m.get("projetado") else ""))

    if v.get("tem_dados"):
        linhas.append("Vendas 7 d: R$ %s em %s pedido(s)" % (
            _milhar(v.get("d7_comissao"), 2), _milhar(v.get("d7_pedidos"))))
        if v.get("meta_mensal"):
            linhas.append("Mês: R$ %s de R$ %s (%s%%)" % (
                _milhar(v.get("mes_comissao"), 2), _milhar(v["meta_mensal"], 2),
                _milhar(v.get("meta_pct"), 0)))

    pauta = (painel.get("pauta") or {}).get("itens") or []
    # As linhas de AÇÃO primeiro: o que decola e o que vende. As de contexto
    # (RECOMPENSAS: NADA ELEGÍVEL) não precisam chegar todo dia no celular.
    prioridade = ("EMPURRE O QUE VENDE", "EMPURRE HOJE", "FALTAM SEGUIDORES",
                  "FORA DA REGRA", "REFAÇA", "GRAVE MAIS LONGO")
    escolhidas = [i for p in prioridade for i in pauta if i.get("acao") == p][:3]
    for i in escolhidas:
        texto = (i.get("texto") or "").strip()
        if len(texto) > 140:
            texto = texto[:137].rstrip() + "…"
        linhas.append("• %s: %s" % (i.get("acao"), texto))

    titulo = "TikTok Shop · %s" % (nome or "resumo do dia")
    return titulo, "\n".join(linhas) if linhas else "Sem novidade na leitura de hoje."


def enviar(servico, titulo, mensagem):
    """(ok, detalhe). Nunca levanta."""
    token = os.environ.get("SUPERVISOR_TOKEN")
    if not token:
        return False, "sem SUPERVISOR_TOKEN (homeassistant_api: true no config.yaml?)"
    corpo = json.dumps({"title": titulo, "message": mensagem}).encode("utf-8")
    req = urllib.request.Request(CORE + "/services/notify/" + servico, data=corpo,
                                 method="POST")
    req.add_header("Authorization", "Bearer " + token)
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return True, "HTTP %s" % r.status
    except urllib.error.HTTPError as e:
        try:
            return False, "HTTP %s: %s" % (e.code, e.read().decode("utf-8")[:200])
        except Exception:
            return False, "HTTP %s" % e.code
    except Exception as e:
        return False, str(e)


def _ja_avisado(pasta, dia):
    try:
        return json.loads((pasta / ARQUIVO).read_text(encoding="utf-8")).get("dia") == dia
    except (OSError, ValueError):
        return False


def _marcar(pasta, dia, detalhe):
    try:
        (pasta / ARQUIVO).write_text(json.dumps({"dia": dia, "quando": int(time.time()),
                                                 "detalhe": detalhe}), encoding="utf-8")
    except OSError:
        pass


def avisar_todas(tk, motivo="", forcar=False):
    """Manda o resumo de cada conta com painel, uma vez por dia. Nunca levanta."""
    if not configurado():
        return
    import pronto
    dia = datetime.now().strftime("%Y-%m-%d")
    try:
        contas = tk.contas()
    except Exception as e:
        print("aviso: nao consegui listar as contas: %s" % e)
        return
    for c in contas:
        pasta = tk.pasta_da_conta(c["open_id"])
        if not forcar and _ja_avisado(pasta, dia):
            continue
        try:
            painel = pronto.ler(tk, c["open_id"]) or pronto.preparar(tk, c["open_id"], " (para o aviso)")
        except Exception as e:
            print("aviso: painel de %s indisponivel: %s" % (c["nome"], e))
            continue
        if not painel or not painel.get("tem_dados"):
            continue
        titulo, mensagem = montar(painel, c["nome"])
        detalhes = []
        for s in servicos():
            ok, det = enviar(s, titulo, mensagem)
            detalhes.append("%s: %s" % (s, det))
            print("aviso%s -> %s: %s" % (motivo, s, "enviado" if ok else "falhou (" + det + ")"))
        _marcar(pasta, dia, detalhes)


if __name__ == "__main__":
    # python3 aviso.py mostrar   -> imprime o resumo sem enviar
    # python3 aviso.py enviar    -> envia agora (mesmo que ja tenha enviado hoje)
    import tiktok
    acao = sys.argv[1] if len(sys.argv) > 1 else "mostrar"
    if acao == "enviar":
        avisar_todas(tiktok, " (manual)", forcar=True)
    else:
        import pronto
        for c in tiktok.contas():
            # Calcula se o arquivo pronto nao valer mais (versao nova, dia
            # novo): "mostrar" tem que mostrar, nao ficar mudo.
            p = pronto.ler(tiktok, c["open_id"]) or pronto.preparar(tiktok, c["open_id"], " (mostrar)")
            if p and p.get("tem_dados"):
                t, msg = montar(p, c["nome"])
                print(t); print(msg); print()

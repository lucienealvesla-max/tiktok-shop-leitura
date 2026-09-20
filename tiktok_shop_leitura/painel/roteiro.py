# -*- coding: utf-8 -*-
"""Roteiro pronto para gravar, pelo agente de IA do Home Assistant.

POR QUE ISTO EXISTE (19/09/2026, fase C.4). A Owra vende "roteiro pronto para
gravar" e "modele conteúdos vencedores" com IA. O Home Assistant desta casa
já tem um agente de conversa configurado (Google Generative AI); o add-on
está dentro do HA e pode pedir a ele pelo serviço `conversation.process` —
sem chave nova, sem biblioteca nova.

O QUE SE PEDE, E PARA QUAIS VÍDEOS. Só para os vídeos que a pauta apontou
(EMPURRE HOJE, REFAÇA, EMPURRE O QUE VENDE): são os que ela vai gravar de
novo amanhã. No máximo `POR_DIA` por conta, uma vez por dia, depois da
leitura da 1h — a conta de IA é limitada (a Owra cobra por uso), e três
roteiros por dia cabem em qualquer plano. O pedido vai com o que se sabe do
vídeo: título, descrição, duração, views, e POR QUE a pauta o escolheu. O
que volta é texto, guardado cru em `<conta>/roteiros.json`, e a tela mostra
sob a linha da pauta.

DESLIGADO POR PADRÃO: sem a opção `agente_ia` (ex.:
conversation.google_ai_conversation), nada aqui roda. Uma falha do agente
não derruba nada — o roteiro simplesmente não aparece naquele dia.
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
ARQUIVO = "roteiros.json"
POR_DIA = 3
GUARDAR = 40           # quantos roteiros ficam no arquivo
ACOES = ("EMPURRE O QUE VENDE", "EMPURRE HOJE", "REFAÇA")


def agente():
    return (os.environ.get("TIKTOK_SHOP_AGENTE") or "").strip()


def configurado():
    return bool(agente()) and bool(os.environ.get("SUPERVISOR_TOKEN"))


def _pedido(video, acao, motivo):
    """O texto que vai para o agente. Em português, curto, com o dado."""
    partes = [
        "Você escreve roteiros para vídeos curtos de TikTok Shop (afiliada que "
        "vende produtos de terceiros mostrando o produto). Responda em português "
        "do Brasil, em texto simples, sem markdown, no máximo 220 palavras.",
        "",
        "Vídeo de referência:",
        "- Título: %s" % (video.get("titulo") or video.get("title") or "(sem título)"),
    ]
    desc = (video.get("video_description") or "").strip()
    if desc:
        partes.append("- Descrição: %s" % desc[:300])
    if video.get("duration"):
        partes.append("- Duração: %s s" % video.get("duration"))
    if video.get("view_count") is not None:
        partes.append("- Views: %s" % video.get("view_count"))
    partes += [
        "- Por que foi escolhido: %s — %s" % (acao, motivo),
        "",
        "Entregue, nesta ordem e com estes rótulos:",
        "GANCHOS: três frases de abertura diferentes (os primeiros 3 segundos), "
        "uma por linha.",
        "ROTEIRO: um roteiro de 60 a 90 segundos em cinco blocos curtos — gancho, "
        "problema, produto, prova, chamada para ação — cada bloco em uma linha "
        "começando com o nome do bloco.",
        "TÍTULO: um título de até 60 caracteres, sem hashtags.",
        "REGRA: não invente característica do produto que não esteja no título ou "
        "na descrição. Se não houver informação para o bloco PROVA, escreva nele "
        "uma lacuna entre colchetes para a criadora preencher com o que ela viu ao "
        "usar o produto, por exemplo: PROVA: [conte o que você notou ao usar]. "
        "O mesmo vale para preço, material, tamanho ou qualquer dado que não "
        "esteja no texto.",
    ]
    return "\n".join(partes)


def perguntar(texto):
    """(ok, resposta). Chama conversation.process pelo Supervisor. Nunca levanta."""
    token = os.environ.get("SUPERVISOR_TOKEN")
    if not token:
        return False, "sem SUPERVISOR_TOKEN"
    corpo = json.dumps({"text": texto, "agent_id": agente(), "language": "pt-BR"}).encode("utf-8")
    req = urllib.request.Request(CORE + "/services/conversation/process?return_response",
                                 data=corpo, method="POST")
    req.add_header("Authorization", "Bearer " + token)
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            d = json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            return False, "HTTP %s: %s" % (e.code, e.read().decode("utf-8")[:200])
        except Exception:
            return False, "HTTP %s" % e.code
    except Exception as e:
        return False, str(e)
    resp = ((d.get("service_response") or {}).get("response") or {})
    fala = ((resp.get("speech") or {}).get("plain") or {}).get("speech")
    if resp.get("response_type") == "error" or not fala:
        return False, str((resp.get("data") or {}).get("code") or "resposta vazia")
    return True, fala.strip()


def _caminho(tk, open_id):
    return tk.pasta_da_conta(open_id) / ARQUIVO


def ler(tk, open_id):
    """{video_id: {texto, quando, acao, titulo}}. {} se não houver."""
    try:
        return json.loads(_caminho(tk, open_id).read_text(encoding="utf-8")) or {}
    except (OSError, ValueError):
        return {}


def _gravar(tk, open_id, dados):
    # Mantém os mais recentes; o arquivo não cresce para sempre.
    if len(dados) > GUARDAR:
        ordem = sorted(dados.items(), key=lambda kv: kv[1].get("quando") or 0)
        dados = dict(ordem[-GUARDAR:])
    alvo = _caminho(tk, open_id)
    temp = alvo.with_suffix(".json.novo.%d" % os.getpid())
    temp.write_text(json.dumps(dados, ensure_ascii=False), encoding="utf-8")
    temp.replace(alvo)


def preparar_todas(tk, motivo="", limite=POR_DIA):
    """Um roteiro para cada vídeo apontado pela pauta, até `limite` por
    conta e por dia. Vídeo que já tem roteiro dos últimos 7 dias não gasta
    outra chamada. Nunca levanta."""
    if not configurado():
        return
    import pronto
    agora = int(time.time())
    try:
        contas = tk.contas()
    except Exception as e:
        print("roteiro: nao consegui listar as contas: %s" % e)
        return
    for c in contas:
        try:
            painel = pronto.ler(tk, c["open_id"]) or pronto.preparar(tk, c["open_id"], " (para o roteiro)")
        except Exception as e:
            print("roteiro: painel de %s indisponivel: %s" % (c["nome"], e))
            continue
        if not painel or not painel.get("tem_dados"):
            continue
        feitos = ler(tk, c["open_id"])
        hoje = datetime.now().strftime("%Y-%m-%d")
        ja_hoje = sum(1 for r in feitos.values() if r.get("dia") == hoje)
        if ja_hoje >= limite:
            continue
        try:
            import catalogo
            por_id = {v.get("id"): v for v in catalogo.videos(tk.pasta_da_conta(c["open_id"]))}
        except Exception:
            por_id = {}
        pedidos = 0
        for item in (painel.get("pauta") or {}).get("itens") or []:
            if pedidos + ja_hoje >= limite:
                break
            vid = item.get("id")
            if item.get("acao") not in ACOES or not vid:
                continue
            antigo = feitos.get(vid)
            if antigo and agora - (antigo.get("quando") or 0) < 7 * 86400:
                continue
            v = dict(por_id.get(vid) or {})
            v.setdefault("titulo", item.get("texto", "")[:80])
            ok, resposta = perguntar(_pedido(v, item["acao"], item.get("de_onde") or ""))
            pedidos += 1
            if not ok:
                print("roteiro: %s / %s falhou: %s" % (c["nome"], vid, resposta))
                continue
            feitos[vid] = {"texto": resposta, "quando": agora, "dia": hoje,
                           "acao": item["acao"], "titulo": v.get("title") or v.get("titulo")}
            print("roteiro: %s / %s pronto%s (%d palavras)"
                  % (c["nome"], vid, motivo, len(resposta.split())))
        if pedidos:
            try:
                _gravar(tk, c["open_id"], feitos)
            except OSError as e:
                print("roteiro: nao gravou: %s" % e)


if __name__ == "__main__":
    # python3 roteiro.py gerar  -> gera os de hoje agora
    # python3 roteiro.py ver    -> imprime os guardados
    import tiktok
    acao = sys.argv[1] if len(sys.argv) > 1 else "ver"
    if acao == "gerar":
        preparar_todas(tiktok, " (manual)")
    for c in tiktok.contas():
        for vid, r in ler(tk=tiktok, open_id=c["open_id"]).items():
            print("== %s · %s · %s (%s)" % (c["nome"], vid, r.get("acao"), r.get("dia")))
            print(r.get("texto")); print()

# -*- coding: utf-8 -*-
"""O catálogo: tudo que já foi visto, com o número mais recente de cada vídeo.

POR QUE ISTO NASCEU (07/09/2026). A leitura da API **encolheu sozinha** e nada
avisou:

    04/09 -> 2.328 vídeos, desde 28/08/2024
    05/09 -> 1.478 vídeos, só desde 02/04/2026
    06/09 ->   958 vídeos, só desde 02/06/2026
    07/09 ->   958 vídeos, só desde 03/06/2026

No dia 06 o vídeo de **2.102.442 views** — o maior da conta inteira — parou de
vir. A tela passou a dizer que o melhor vídeo dela tinha 277 mil, e a mediana,
os assuntos e o "melhor horário" passaram a ser calculados sobre os últimos três
meses fingindo ser a conta toda. Nenhum erro apareceu: `puxar_videos` devolve o
que conseguiu, `guardar_foto` grava, e a tela lê a última fotografia.

A causa (limite da API, corte por tempo, ou pedido que falhou no meio) muda de
dia para dia e não está sob nosso controle. O que está sob nosso controle é
**não esquecer o que já foi visto uma vez**. É isto aqui.

O QUE ELE É: um arquivo por conta com o último número conhecido de CADA vídeo
que já apareceu em alguma leitura, e a data em que aquele número foi lido.

    catalogo.json = {"videos": {id: {...campos..., "visto_em": "AAAA-MM-DD"}}}

O QUE ELE NÃO É: não é a série. A trajetória continua saindo das fotografias
diárias, que ficam **cruas e honestas** — fotografia é o que foi lido naquele
dia, e misturar leitura de hoje com número de anteontem ali dentro inventaria
ganho que não houve. O catálogo serve às contas que perguntam "como é a conta
dela" (mediana, assuntos, horário, duração); a série serve às que perguntam
"o que mudou desde ontem".

O PREÇO, dito na tela: um vídeo lido pela última vez há 3 dias entra com o
número de 3 dias atrás. Para mediana e ranking de assunto isso é ruído pequeno;
sumir da conta inteira era um erro grande.
"""

import json
import time
from datetime import datetime
from pathlib import Path

# Os campos que a fotografia guarda. O catálogo guarda os mesmos: qualquer
# métrica que hoje roda sobre a fotografia tem que rodar sobre ele sem adaptar.
CAMPOS = ("id", "create_time", "duration", "view_count", "like_count",
          "comment_count", "share_count", "title", "video_description",
          # O link e a capa: é o que faz a tela dizer QUAL vídeo é. A capa só
          # existe aqui - o endereço dela expira, e uma fotografia por dia de
          # endereço vencido seria peso morto no cartão do Raspberry.
          "share_url", "cover_image_url")


def caminho(pasta_da_conta):
    return Path(pasta_da_conta) / "catalogo.json"


def _magro(v, dia):
    d = {k: v.get(k) for k in CAMPOS}
    d["visto_em"] = dia
    return d


def ler(pasta_da_conta):
    """O catálogo como está no disco. {} se não houver. Nunca levanta."""
    try:
        d = json.loads(caminho(pasta_da_conta).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return d.get("videos") or {}


def gravar(pasta_da_conta, videos_por_id):
    """Grava o catálogo. (ok, mensagem)"""
    alvo = caminho(pasta_da_conta)
    try:
        alvo.parent.mkdir(parents=True, exist_ok=True)
        # Arquivo temporário e troca: o catálogo é reescrito inteiro a cada
        # leitura, e uma queda de energia no meio da escrita deixaria um JSON
        # pela metade — que `ler` descartaria, apagando o histórico acumulado
        # justamente na hora em que ele é a única cópia do que sumiu da API.
        temp = alvo.with_suffix(".json.novo")
        temp.write_text(json.dumps({"atualizado_em": int(time.time()),
                                    "videos": videos_por_id}),
                        encoding="utf-8")
        temp.replace(alvo)
    except OSError as e:
        return False, str(e)
    return True, "%d vídeo(s) no catálogo" % len(videos_por_id)


def juntar(videos_por_id, videos, dia):
    """Soma uma leitura ao catálogo, em memória. Devolve o dicionário novo.

    QUEM GANHA O EMPATE: a leitura mais recente. `dia` é a data da fotografia de
    onde estes vídeos vieram, e uma reconstrução varre as fotografias da mais
    antiga para a mais nova — então o último a escrever é sempre o mais atual.
    Comparar as datas em vez de confiar na ordem protege quem chamar fora de
    ordem: número velho nunca sobrescreve número novo.
    """
    fora = dict(videos_por_id)
    for v in videos or []:
        vid = v.get("id")
        if not vid:
            continue
        antigo = fora.get(vid)
        if antigo and (antigo.get("visto_em") or "") > (dia or ""):
            continue
        novo = _magro(v, dia)
        # A data da PRIMEIRA vez que o vídeo apareceu por aqui. É o que permite
        # dizer "este vídeo é novo no catálogo" sem confundir com a data de
        # publicação — vídeo antigo pode aparecer pela primeira vez hoje.
        novo["catalogado_em"] = (antigo or {}).get("catalogado_em") or dia
        # O QUE NÃO VEIO AGORA, NÃO SE APAGA. Uma reconstrução a partir das
        # fotografias não tem capa nenhuma (a capa nunca é guardada lá), e sem
        # esta linha ela apagaria as capas que a leitura de hoje trouxe.
        for campo in ("share_url", "cover_image_url"):
            if not novo.get(campo) and (antigo or {}).get(campo):
                novo[campo] = antigo[campo]
        fora[vid] = novo
    return fora


def reconstruir(pasta_da_conta):
    """Refaz o catálogo do zero a partir de TODAS as fotografias no disco.

    É o que traz de volta o que já se perdeu: as fotografias antigas continuam
    inteiras no disco, e o vídeo de 2,1 milhão está lá dentro na de 04/09.
    Roda uma vez e o catálogo nasce completo — sem depender de a API voltar a
    entregar a conta inteira algum dia.
    """
    pasta = Path(pasta_da_conta) / "fotos"
    videos_por_id = {}
    if not pasta.is_dir():
        return videos_por_id
    for p in sorted(pasta.glob("*.json")):      # da mais antiga para a mais nova
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        videos_por_id = juntar(videos_por_id, d.get("videos") or [], p.stem)
    return videos_por_id


def atualizar(pasta_da_conta, videos, dia=None):
    """Soma a leitura de hoje ao catálogo e grava. (ok, mensagem)

    Se o catálogo ainda não existe, reconstrói do disco ANTES de somar: sem
    isso, o primeiro dia depois da atualização nasceria com o mesmo buraco que
    esta classe inteira existe para tapar.
    """
    dia = dia or datetime.now().strftime("%Y-%m-%d")
    atual = ler(pasta_da_conta) or reconstruir(pasta_da_conta)
    return gravar(pasta_da_conta, juntar(atual, videos, dia))


def videos(pasta_da_conta):
    """A lista do catálogo, do mais visto para o menos. Reconstrói se faltar.

    Reconstruir na leitura (e não só na escrita) é o que faz a atualização
    valer já na primeira vez que ela abre a tela, sem esperar a leitura das 21h.
    """
    d = ler(pasta_da_conta)
    if not d:
        d = reconstruir(pasta_da_conta)
        if d:
            gravar(pasta_da_conta, d)
    return sorted(d.values(), key=lambda v: -(v.get("view_count") or 0))


def cobertura(pasta_da_conta, videos_de_hoje=None):
    """O que a última leitura trouxe, contra o que o catálogo conhece.

    ISTO VAI PARA A TELA. O erro que originou este arquivo era invisível: a
    leitura encolheu 60% e a página continuou com cara de normal. Um número
    ao lado do outro faz a próxima vez aparecer no dia, não em três meses.
    """
    cat = ler(pasta_da_conta) or reconstruir(pasta_da_conta)
    conhecidos = len(cat)
    if videos_de_hoje is None:
        pasta = Path(pasta_da_conta) / "fotos"
        ultimos = sorted(pasta.glob("*.json")) if pasta.is_dir() else []
        videos_de_hoje = []
        if ultimos:
            try:
                videos_de_hoje = (json.loads(
                    ultimos[-1].read_text(encoding="utf-8")).get("videos") or [])
            except (OSError, ValueError):
                videos_de_hoje = []
    lidos = len(videos_de_hoje)
    # "Sumiram" são os vídeos que o catálogo conhece e a última leitura não
    # trouxe. Alguns podem ter sido apagados por ela de propósito - por isso a
    # tela fala em "não vieram na última leitura", e nunca em "perdidos".
    return {"conhecidos": conhecidos, "na_ultima_leitura": lidos,
            "nao_vieram": max(0, conhecidos - lidos),
            "completa": lidos >= conhecidos}

# -*- coding: utf-8 -*-
"""Os painéis que o app do TikTok não tem, feitos com o que a Display API dá.

POR QUE ISTO EXISTE (31/08/2026). Pedido dele: *"dashboards que não existam na
interface do TikTok e que sejam de suma importância para creators"*.

A IDEIA QUE SUSTENTA O ARQUIVO INTEIRO: **o TikTok mostra o número de agora; ele
nunca mostra a trajetória.** No app ela vê "12.400 visualizações". Não vê quantas
o vídeo ganhou ontem, se está acelerando ou parando, nem se um vídeo de três
semanas voltou a crescer. A API também devolve só o acumulado do momento — a
dimensão de tempo **não existe em lugar nenhum** até alguém guardar leituras
sucessivas. É o que `tiktok.guardar_foto()` faz, uma por dia.

O CORTE DE 18/09/2026 (1.4.0). A tela tinha 21 painéis e levava **44 segundos**
para abrir no Raspberry. Medido painel por painel: o "Resumo" sozinho eram 18 s
porque recalculava acelerando, ressurreições, meia-vida, hashtags e a pauta por
dentro; acelerando e ressurreições montavam a mesma série de 2.430 vídeos × 15
dias duas vezes. Treze painéis saíram, por um critério só: **responde alguma
coisa que o app do TikTok não responde?** Trajetória responde — o app só tem o
acumulado. Ranking de hashtag, "melhor horário", mediana da conta, ritmo
semanal, meia-vida, comentado/compartilhado por view: ou o Analytics do TikTok
já mostra, ou saía de 4 vídeos e era ruído ("#vangogh 17,8x, 4 vídeos"). O que
entrou no lugar foi a **monetização**: ela passou de 10 mil seguidores, e o
Programa de Recompensas exige 100 mil views em 30 dias em vídeos de mais de 1
minuto — e só 16% do que ela postava passava de 1 minuto, enquanto o vídeo
longo ganhava de 5 a 7 vezes mais views novas por vídeo do que o curto
(conforme a janela medida).

O que sobrou é calculado uma vez por dia e gravado (ver `pronto.py`); a tela lê
o arquivo. Abrir a tela não calcula nada.

DUAS REGRAS QUE VALEM PARA TUDO NESTE ARQUIVO:

1. **Mediana, não média.** No TikTok um vídeo viral distorce qualquer média: um
   de 200 mil entre nove de 800 faz a "média" dizer 20 mil, número que não
   descreve nenhum vídeo dela. A mediana descreve o dia normal.
2. **Piso de amostra.** Toda comparação diz de quantos vídeos ela saiu. Um vídeo
   com 12 visualizações e 1 compartilhamento tem "8% de taxa" e não significa
   nada. Sem o piso, o ranking enche de ruído e aponta pro lugar errado.
"""

from datetime import datetime, timedelta
from functools import lru_cache

import conteudo
from comum import MINIMO_DE_VIDEOS
from comum import identidade as _identidade
from comum import mediana as _mediana
from comum import n as _n
from comum import quando as _quando


def ultimos_videos(fotos):
    """A leitura mais recente: a lista de vídeos como está hoje."""
    if not fotos:
        return []
    return fotos[-1].get("videos") or []


def serie_por_video(fotos):
    """{id: [(dia, views), ...]} em ordem, uma entrada por fotografia.

    É A CONTA MAIS CARA DO ARQUIVO (2.430 vídeos × 15 dias) e por isso é feita
    UMA vez em `tudo()` e passada adiante. Antes cada painel de trajetória
    montava a sua, e só isso custava 12 dos 44 segundos da tela.
    """
    serie = {}
    for f in fotos:
        dia = f.get("dia")
        for v in f.get("videos") or []:
            if not v.get("id"):
                continue
            serie.setdefault(v["id"], []).append((dia, _n(v.get("view_count"))))
    for k in serie:
        serie[k].sort(key=lambda x: x[0])
    return serie


@lru_cache(maxsize=4096)
def _dias_entre(a, b):
    """Dias entre dois rótulos AAAA-MM-DD. 1 quando não der para saber.

    COM CACHE, e isso é metade do tempo do cálculo inteiro: são 2.430 vídeos ×
    14 intervalos × 3 painéis, quase 200 mil chamadas, para 15 pares de dias
    distintos. Medido: acelerando caía de 5,0 s para menos de 1 s só com isto.
    """
    try:
        return max(1, (datetime.strptime(b, "%Y-%m-%d")
                       - datetime.strptime(a, "%Y-%m-%d")).days)
    except (ValueError, TypeError):
        return 1


def _ganhos_diarios(pontos):
    """As diferenças entre leituras consecutivas: (dia, ganho, ganho por dia).

    Negativo aparece quando o TikTok recalcula ou o vídeo sai do ar por um dia.
    Deixar passar viraria "ganho de -3.000 views" na tela, que assusta sem
    motivo; zerar é a leitura honesta - naquele intervalo não houve ganho.

    E O INTERVALO NEM SEMPRE É DE UM DIA. A leitura pode falhar, o Pi pode ficar
    sem luz, e um vídeo pode simplesmente não vir numa leitura que encolheu (foi
    o que aconteceu em 06/09: 1.394 vídeos não vieram). Nesses casos as duas
    leituras vizinhas estão a três, cinco dias de distância, e chamar a
    diferença toda de "ganhou ontem" infla o número na cara dela — justamente
    no painel que existe para ela decidir onde gastar a próxima hora. O ganho
    bruto continua saindo daqui, agora com o ritmo por dia ao lado.
    """
    fora = []
    for i in range(1, len(pontos)):
        dias = _dias_entre(pontos[i - 1][0], pontos[i][0])
        ganho = max(0.0, pontos[i][1] - pontos[i - 1][1])
        fora.append((pontos[i][0], ganho, ganho / dias))
    return fora


# =========================================================================
#  PRECISAM DE HISTÓRICO
# =========================================================================

def acelerando(fotos, quantos=10, por_id=None, serie=None):
    """O que está pegando fogo AGORA: views ganhas na última leitura e em 7.

    É a pergunta mais urgente de quem posta todo dia, e o app não responde: lá
    tudo é acumulado desde a publicação. Um vídeo com 50 mil views pode estar
    parado há duas semanas, e um de 3 mil pode ter ganhado 2 mil ontem - na tela
    do TikTok os dois parecem o que não são.
    """
    if len(fotos) < 2:
        return {"pronto": False, "faltam": 2 - len(fotos), "itens": []}

    serie = serie if serie is not None else serie_por_video(fotos)
    atuais = {v.get("id"): v for v in ultimos_videos(fotos)}
    # ORDENA PELO RITMO, não pelo bruto: entre um vídeo que ganhou 900 views em
    # três dias e um que ganhou 500 em um, quem está pegando fogo agora é o
    # segundo — e "agora" é a pergunta inteira deste painel.
    # E ORDENA ANTES DE MONTAR A IDENTIDADE: título limpo, link e capa para os
    # 2.430 vídeos, quando a tela mostra 10, era metade do tempo deste painel.
    brutos = []
    for vid, pontos in serie.items():
        ganhos = _ganhos_diarios(pontos)
        if not ganhos:
            continue
        brutos.append((ganhos[-1][2], vid, pontos, ganhos))
    brutos.sort(key=lambda x: -x[0])
    itens = []
    for ritmo, vid, pontos, ganhos in brutos[:quantos]:
        v = atuais.get(vid) or {}
        reserva = (por_id or {}).get(vid)
        itens.append(dict(_identidade(v, reserva), **{
            "id": vid,
            "views": _n(v.get("view_count")) or _n((reserva or {}).get("view_count")),
            "ganho_ultimo": ganhos[-1][1],
            "ganho_por_dia": round(ritmo, 1),
            "dias_do_intervalo": _dias_entre(pontos[-2][0], pontos[-1][0]),
            "ganho_7d": sum(g for _, g, _r in ganhos[-7:]),
        }))
    return {"pronto": True, "itens": itens}


def ressurreicoes(fotos, idade_minima=14, fator=3.0, piso=50, por_id=None,
                  serie=None):
    """Vídeo velho que voltou a crescer.

    POR QUE ISTO IMPORTA MAIS DO QUE PARECE: o TikTok revive vídeo antigo o tempo
    todo, e **não avisa**. Sem alguém olhando, ela descobre semanas depois - ou
    nunca. Sabendo no dia, dá pra reagir enquanto o vídeo ainda está subindo:
    fazer uma continuação, responder comentário, empurrar o link.

    A régua é o ritmo do PRÓPRIO vídeo, não um número fixo: 500 views num dia é
    ressurreição para um vídeo parado e rotina para um que acabou de sair.
    """
    if len(fotos) < 4:
        return {"pronto": False, "faltam": 4 - len(fotos), "itens": []}

    serie = serie if serie is not None else serie_por_video(fotos)
    atuais = {v.get("id"): v for v in ultimos_videos(fotos)}
    agora = datetime.now()
    itens = []
    for vid, pontos in serie.items():
        ganhos = _ganhos_diarios(pontos)
        if len(ganhos) < 3:
            continue
        v = atuais.get(vid) or (por_id or {}).get(vid) or {}
        nasceu = _quando(v.get("create_time"))
        if not nasceu or (agora - nasceu).days < idade_minima:
            continue
        ultimo = ganhos[-1][2]        # ritmo por dia, não o bruto do intervalo
        antes = _mediana([r for _, _g, r in ganhos[:-1]]) or 0.0
        if ultimo < piso:
            continue
        # Vídeo que estava parado de vez (mediana 0) e ganhou acima do piso já é
        # ressurreição: não dá pra multiplicar por zero e exigir um fator.
        if antes == 0 or ultimo >= antes * fator:
            itens.append(dict(_identidade(v, (por_id or {}).get(vid)), **{
                "id": vid,
                "views": _n(v.get("view_count")),
                "ganho_ultimo": ultimo,
                "ritmo_anterior": antes,
                "idade_dias": (agora - nasceu).days,
            }))
    itens.sort(key=lambda x: -x["ganho_ultimo"])
    return {"pronto": True, "itens": itens}


# =========================================================================
#  MONETIZAÇÃO
# =========================================================================

# As regras do Programa de Recompensas do Criador, como estão na Creator
# Academy em 18/09/2026 (Brasil elegível): 10 mil seguidores, 100 mil views nos
# últimos 30 dias, conteúdo com mais de 1 minuto, 18+, conta pessoal. Ficam num
# dicionário e não espalhadas no código porque o TikTok muda isso sem avisar, e
# a tela mostra os números ao lado do medido — número escondido no código
# mentiria em silêncio quando a regra mudasse.
#
# `folga` é a margem abaixo da qual a pauta avisa: estar em 100.001 é estar
# dentro hoje e fora amanhã.
REGRAS = {"seguidores": 10000, "views_30d": 100000, "duracao_s": 60,
          "janela_dias": 30, "folga": 1.5}

# Três faixas e não seis: a régua da monetização é 1 minuto, e a pergunta que
# a faixa responde é "vale gravar mais longo?". Dividir mais fino do que a
# pergunta pede só espalha a amostra.
FAIXAS = [(0, 30, "até 30 s"), (30, 60, "31 a 60 s"), (60, 10 ** 6, "mais de 1 min")]
FAIXA_LONGA = FAIXAS[-1][2]


def _faixa(duracao):
    d = _n(duracao)
    if not d:
        return None
    for de, ate, nome in FAIXAS:
        if de < d <= ate:
            return nome
    return None


def monetizacao(fotos, videos, serie=None, regras=REGRAS):
    """Ela está dentro das regras de monetização, e por quanto?

    O app mostra o acumulado de cada vídeo e o total de seguidores. A regra
    mede outra coisa: quantas views a conta GANHOU nos últimos 30 dias — e isso
    só sai da série. É a mesma conta do "Acelerando", somada para a conta
    inteira dentro da janela.

    A CONTA DO GANHO, por vídeo: soma das diferenças entre leituras consecutivas
    dentro da janela (`_ganhos_diarios`, que já zera negativo e já sabe que uma
    leitura pulada estica o intervalo). Vídeo que NASCEU dentro da janela conta
    também o número que já tinha na primeira leitura — aquelas views são desta
    janela, só não foram vistas nascer. Vídeo que não veio numa leitura truncada
    (05 e 06/09 trouxeram 1.478 e 958 dos 2.430) não perde nada: o intervalo
    04→07 cobre os dias que faltaram.

    ENQUANTO NÃO HÁ 30 DIAS DE LEITURA, o número é projetado (ganho × 30 ÷ dias
    medidos) e a tela diz isso. Com 14 dias medidos a projeção é uma estimativa
    honesta; com 2 dias ela mede um fim de semana e a tela tem que avisar.

    SEGUIDORES SAEM `None`: o add-on ainda não pede o escopo `user.info.stats`
    (fase 1). Mentir com o último número que ela viu no app seria pior do que
    dizer que não foi lido.
    """
    janela = regras["janela_dias"]
    fora = {"regras": regras, "janela_dias": janela, "pronto": False,
            "seguidores": None, "seguidores_ok": None}
    if len(fotos) < 2:
        fora["faltam"] = 2 - len(fotos)
        return fora

    serie = serie if serie is not None else serie_por_video(fotos)
    ate = fotos[-1].get("dia") or ""
    try:
        inicio_dt = datetime.strptime(ate, "%Y-%m-%d") - timedelta(days=janela)
    except ValueError:
        fora["faltam"] = 1
        return fora
    inicio = inicio_dt.strftime("%Y-%m-%d")
    dias_com_foto = [f.get("dia") for f in fotos if (f.get("dia") or "") >= inicio]
    if len(dias_com_foto) < 2:
        fora["faltam"] = 2 - len(dias_com_foto)
        return fora
    desde = dias_com_foto[0]
    dias_medidos = _dias_entre(desde, ate)

    por_id = {v.get("id"): v for v in videos if v.get("id")}
    ganho_por_video = {}
    for vid, pontos in serie.items():
        dentro = [p for p in pontos if (p[0] or "") >= inicio]
        if not dentro:
            continue
        g = sum(gn for _d, gn, _r in _ganhos_diarios(dentro))
        v = por_id.get(vid) or {}
        nasceu = _quando(v.get("create_time"))
        if nasceu and nasceu >= inicio_dt:
            g += dentro[0][1]
        ganho_por_video[vid] = g

    ganho = sum(ganho_por_video.values())
    projetado = dias_medidos < janela
    views_30d = (ganho * janela / dias_medidos) if projetado else ganho

    por_faixa = {}
    for vid, g in ganho_por_video.items():
        nome = _faixa((por_id.get(vid) or {}).get("duration"))
        if nome is not None:
            por_faixa.setdefault(nome, []).append(g)
    faixas = []
    for _de, _ate, nome in FAIXAS:
        gs = por_faixa.get(nome) or []
        if len(gs) < MINIMO_DE_VIDEOS:
            continue
        faixas.append({"rotulo": nome, "videos": len(gs),
                       "ganho": round(sum(gs)),
                       "ganho_por_video": round(sum(gs) / len(gs)),
                       "mediana_ganho": _mediana(gs)})
    longos = [f for f in faixas if f["rotulo"] == FAIXA_LONGA]
    curtos = [f for f in faixas if f["rotulo"] != FAIXA_LONGA]
    longo_vs_curto = None
    if longos and curtos:
        base = sum(f["ganho"] for f in curtos) / float(sum(f["videos"] for f in curtos))
        if base:
            longo_vs_curto = round(longos[0]["ganho_por_video"] / base, 1)

    publicados = [v for v in videos
                  if (_quando(v.get("create_time")) or datetime.min) >= inicio_dt]
    n_longos = sum(1 for v in publicados
                   if _n(v.get("duration")) > regras["duracao_s"])
    pct = round(n_longos * 100.0 / len(publicados), 1) if publicados else None

    fora.update({
        "pronto": True, "desde": desde, "ate": ate, "dias_medidos": dias_medidos,
        "videos_medidos": len(ganho_por_video),
        "views_ganhas": round(ganho), "views_30d": round(views_30d),
        "projetado": projetado,
        "views_ok": views_30d >= regras["views_30d"],
        "views_vezes": round(views_30d / regras["views_30d"], 1),
        "publicados": len(publicados), "longos": n_longos, "pct_longos": pct,
        "faixas": faixas, "longo_vs_curto": longo_vs_curto,
    })
    return fora


# =========================================================================
#  TUDO, E DE ONDE A TELA LÊ
# =========================================================================

def tudo(fotos, videos=None):
    """Todos os painéis numa chamada só.

    `videos` é o CATÁLOGO — todo vídeo que já foi visto, com o número mais
    recente de cada um. Quando não vem, cai na última fotografia, que é como
    era antes.

    A DIVISÃO QUE IMPORTA, e o motivo de o parâmetro existir:

      - **Retrato** (refazer, parcerias, e a contagem de publicados da
        monetização): sai do catálogo. São perguntas sobre COMO É A CONTA
        DELA, e responder isso com a leitura de hoje — que em 06/09 trouxe 958
        dos 2.352 vídeos — descreve os últimos três meses fingindo ser a conta
        toda. Foi assim que o vídeo de 2,1 milhão sumiu da tela.
      - **Trajetória** (acelerando, ressuscitou, largada, e o ganho da
        monetização): sai das fotografias, cruas. São perguntas sobre O QUE
        MUDOU, e para isso só vale leitura de verdade — misturar o número de
        anteontem inventaria ganho que não houve.
    """
    videos = videos or ultimos_videos(fotos)
    # QUEM É CADA VÍDEO, num mapa. Os painéis de trajetória saem das
    # fotografias, e fotografia não tem capa; o catálogo tem. Sem isto, o
    # painel "Acelerando" - o mais urgente da tela - seria o único mostrando
    # vídeo sem imagem e sem link.
    por_id = {v.get("id"): v for v in videos if v.get("id")}
    serie = serie_por_video(fotos)

    lg = conteudo.largada(fotos, por_id=por_id)
    rf = conteudo.refazer(videos)
    mn = monetizacao(fotos, videos, serie=serie)
    return {
        "dias_de_historico": len(fotos),
        "videos": len(videos),
        # A ORDEM AQUI NÃO É A DA TELA (o dashboard.html decide), mas a pauta
        # vem primeiro por ser o único painel que sai dos outros.
        "pauta": conteudo.pauta(lg, rf, mn),
        "monetizacao": mn,
        "largada": lg,
        "acelerando": acelerando(fotos, por_id=por_id, serie=serie),
        "ressurreicoes": ressurreicoes(fotos, por_id=por_id, serie=serie),
        "refazer": rf,
        "parcerias": conteudo.parcerias(videos),
    }


def escolher(tk, conta=None):
    """Qual perfil vai para a tela: (open_id ou None, erro ou None).

    A tela manda o open_id escolhido; sem ele, o primeiro conectado. Perfil
    pedido que não existe mais (ela desconectou noutra aba) cai no primeiro em
    vez de dar erro — tela vazia com mensagem técnica é pior que tela certa do
    perfil vizinho, que ela reconhece na hora.
    """
    try:
        lista = tk.contas()
    except Exception as e:
        return None, str(e)
    ids = [c["open_id"] for c in lista]
    return (conta if conta in ids else (ids[0] if ids else None)), None


def calcular(tk, escolhida):
    """Os painéis de UM perfil, lidos do disco. É a parte cara.

    Devolve {"tem_dados": False} quando o perfil não tem fotografia nenhuma.
    Levanta se o disco falhar — quem chama decide o que fazer com isso.
    """
    fotos = tk.fotos(escolhida)
    if not fotos:
        return {"tem_dados": False}

    # O CATÁLOGO, e o quanto a última leitura cobriu dele. Se falhar, a tela
    # continua de pé com a última fotografia — que é o comportamento antigo,
    # pior mas nunca vazio.
    catalogados, cobertura = None, None
    try:
        import catalogo
        pasta = tk.pasta_da_conta(escolhida)
        catalogados = catalogo.videos(pasta)
        cobertura = catalogo.cobertura(pasta, ultimos_videos(fotos))
    except Exception:
        catalogados, cobertura = None, None

    d = tudo(fotos, catalogados)
    d["cobertura"] = cobertura
    d["tem_dados"] = True
    return d


def estado_de(estado):
    """O estado é o enfeite ao lado do número; o número é o que ela veio ver.
    Um agendador indisponível não pode esvaziar a tela inteira."""
    try:
        return estado() if estado else {}
    except Exception:
        return {}


def painel_de_desempenho(tk, conta=None, estado=None):
    """Os dashboards da API do TikTok. Uma resposta só, calculada agora.

    Sai das FOTOGRAFIAS diárias, não de uma chamada à API: a série de tempo é o
    que dá valor a quase tudo aqui, e ela só existe porque alguém guardou as
    leituras. Abrir a tela não dispara chamada ao TikTok.

    MORA AQUI, E NÃO NO painel.py, porque o servidor do Raspberry precisa da
    mesma resposta e o painel.py não vai para lá (quase 3.000 linhas presas a
    ffmpeg). O servidor do Raspberry, por sua vez, NÃO chama isto ao abrir a
    tela: ele lê o resultado gravado por `pronto.py`, que chama `calcular` uma
    vez por dia. Esta função continua existindo para o painel.py do computador.

    `tk` é o módulo tiktok, e `estado` é uma função sem argumentos: o painel
    informa se a tarefa agendada do Windows existe, e o add-on informa outra
    coisa. Este arquivo não pode passar a saber o que é agendador do Windows.
    """
    escolhida, erro = escolher(tk, conta)
    if erro:
        return {"ok": False, "erro": erro}
    if escolhida is None:
        return {"ok": True, "tem_dados": False, "conta": None,
                "tiktok": estado_de(estado)}
    try:
        d = calcular(tk, escolhida)
    except Exception as e:
        return {"ok": False, "erro": str(e)}
    d["ok"] = True
    d["conta"] = escolhida
    d["tiktok"] = estado_de(estado)
    return d

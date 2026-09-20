# -*- coding: utf-8 -*-
"""O que gravar amanhã — os painéis que respondem "o que fazer", não "como foi".

POR QUE ISTO EXISTE (07/09/2026). Pedido dele: *"pense como um influenciador,
buscando melhorias em como achar vídeos novos e assuntos novos para postar"*.

A REGRA QUE ESTE ARQUIVO INTEIRO OBEDECE: **um painel só entra se ela puder
fazer alguma coisa com ele amanhã de manhã.** "Vale refazer" cabe;
"distribuição de views por decil" não cabe.

O CORTE DE 18/09/2026 (1.4.0). Saíram daqui hashtags, frases de duas palavras,
ganchos de título, "assunto que rendia e você parou", comentado por view e
cadência. Motivo, medido nos dados dela: as hashtags que ela usa são de campanha
(`#tiktokshopbr88`, `#tiktokshopbr66`... em 1.646 dos 2.430 vídeos), não de
assunto; e o que sobrava no topo dos rankings saía de 4 vídeos ("#vangogh
17,8x", "praia dunas cabo 9,66x") — pista fraca demais para virar pauta, e a
pauta é o único produto desta tela. Ficou o que responde com amostra de
verdade: a largada (reaja agora), o refazer (o vídeo bom que não foi entregue)
e as parcerias (que marca rende, porque ela é afiliada e isso é dinheiro).

AS DUAS REGRAS DA CASA VALEM AQUI (ver metricas.py): mediana e nunca média, e
toda comparação diz de quantos vídeos saiu.
"""

import re
from datetime import datetime

from comum import (MINIMO_DE_VIDEOS, MINIMO_DE_VIEWS, identidade, mediana, n,
                   quando, texto_do_video)

# Uma marca/parceria precisa de menos vídeos que um assunto para virar linha na
# tela: ela tem poucas parcerias e cada uma vale muito, então exigir a mesma
# amostra esconderia justamente a informação mais cara.
MINIMO_DE_PARCERIA = 3


# ------------------------------------------------------------------ a régua

def _ranking(videos, extrair, minimo, quantos, rotular=None):
    """Ranqueia qualquer coisa extraível do vídeo pela mediana de views DELA.

    `extrair` devolve o conjunto de termos de um vídeo (conjunto, não lista:
    a palavra repetida três vezes no mesmo texto não pode contar como três
    vídeos). A conta é sempre a mesma — a mediana do grupo contra a mediana
    geral — e é ela que faz uma menção presente em todo vídeo cair sozinha para
    1,0x sem lista negra.
    """
    geral = mediana([n(v.get("view_count")) for v in videos])
    if not geral:
        return {"geral": None, "amostra": 0, "itens": [], "piores": []}

    onde = {}
    quando_ultimo = {}
    for v in videos:
        publicado = quando(v.get("create_time"))
        for termo in set(extrair(v) or []):
            onde.setdefault(termo, []).append(n(v.get("view_count")))
            if publicado and (termo not in quando_ultimo
                              or publicado > quando_ultimo[termo]):
                quando_ultimo[termo] = publicado

    total = len(videos)
    itens = []
    for termo, vistos in onde.items():
        if len(vistos) < minimo:
            continue
        med = mediana(vistos)
        ultimo = quando_ultimo.get(termo)
        itens.append({
            "termo": rotular(termo) if rotular else termo,
            "videos": len(vistos),
            "mediana": med,
            "vezes_a_geral": round(med / geral, 2) if geral else None,
            # Em quantos % dos vídeos o termo aparece. 90% de presença e 1,0x
            # não é parceria, é assinatura.
            "presenca": round(len(vistos) / total * 100, 1) if total else 0,
            "ultimo_uso": ultimo.strftime("%Y-%m-%d") if ultimo else None,
            "dias_sem_usar": (datetime.now() - ultimo).days if ultimo else None,
        })
    itens.sort(key=lambda x: -(x["vezes_a_geral"] or 0))
    return {"geral": geral, "amostra": total, "itens": itens[:quantos],
            "piores": itens[-quantos:][::-1] if len(itens) > quantos else []}


# --------------------------------------------------------------- as marcas

def _mencoes_do_video(v):
    return [m.lower() for m in
            re.findall(r"@([0-9A-Za-zÀ-ÿ_.]+)", texto_do_video(v))]


def parcerias(videos, minimo=MINIMO_DE_PARCERIA, quantos=12):
    """Que marca/parceria rende mais.

    ATENÇÃO AO QUE ISTO MEDE. Quando ela cola o nome de exibição da marca
    ("@Grupo On Line Editora"), só a primeira palavra vira menção — o TikTok
    separaria igual. Então `@grupo` aqui é "a parceria com o Grupo On Line",
    e não uma conta chamada "grupo". Serve para comparar parcerias entre si,
    que é a pergunta dela; não serve como identificador de conta.

    Mede VIEWS, não comissão. É o que a Display API dá. Quando a API de
    afiliado entrar (fase 2), este painel vira "marcas que pagam".
    """
    return _ranking(videos, _mencoes_do_video, minimo, quantos,
                    rotular=lambda m: "@" + m)


# ------------------------------------------------ o que fazer com o que já existe

def refazer(videos, quantos=10, idade_minima=14, fator=2.0):
    """Vídeo que agradou quem viu, mas que o TikTok não entregou.

    A LEITURA QUE JUSTIFICA O PAINEL: view é o que o TikTok deu; compartilhar e
    comentar é o que a PESSOA fez. Um vídeo com poucas views e taxa de
    compartilhamento duas vezes acima da mediana dela não é um vídeo ruim — é
    um vídeo bom que teve azar de entrega. Refazer esse é a aposta mais segura
    que existe na rotina dela: o assunto já passou no teste que importa, e só a
    capa, o gancho ou o horário mudam.

    Vídeo novo fica de fora (`idade_minima`): ele ainda pode estar entregando,
    e mandá-la refazer hoje o que ia crescer amanhã é conselho caro.
    """
    maduros = [v for v in videos
               if n(v.get("view_count")) >= MINIMO_DE_VIEWS]
    if not maduros:
        return {"itens": [], "amostra": 0}

    med_views = mediana([n(v.get("view_count")) for v in maduros]) or 0
    med_share = mediana([n(v.get("share_count")) / n(v.get("view_count")) * 100
                         for v in maduros]) or 0
    med_coment = mediana([n(v.get("comment_count")) / n(v.get("view_count")) * 100
                          for v in maduros]) or 0

    agora = datetime.now()
    itens = []
    for v in maduros:
        vistos = n(v.get("view_count"))
        if vistos >= med_views:
            continue                      # já teve entrega; não é este o caso
        nasceu = quando(v.get("create_time"))
        if not nasceu or (agora - nasceu).days < idade_minima:
            continue
        taxa_s = n(v.get("share_count")) / vistos * 100
        taxa_c = n(v.get("comment_count")) / vistos * 100
        forca_s = (taxa_s / med_share) if med_share else 0
        forca_c = (taxa_c / med_coment) if med_coment else 0
        if max(forca_s, forca_c) < fator:
            continue
        itens.append(dict(identidade(v), **{
            "id": v.get("id"),
            "views": vistos,
            "taxa_compartilhamento": round(taxa_s, 2),
            "taxa_comentario": round(taxa_c, 2),
            "forca": round(max(forca_s, forca_c), 2),
            "idade_dias": (agora - nasceu).days,
            "motivo": ("compartilharam muito" if forca_s >= forca_c
                       else "comentaram muito"),
        }))
    itens.sort(key=lambda x: -x["forca"])
    return {"itens": itens[:quantos], "amostra": len(maduros),
            "mediana_views": med_views,
            "mediana_compartilhamento": round(med_share, 2),
            "mediana_comentario": round(med_coment, 2)}


# -------------------------------------------------------------- a largada

def largada(fotos, janela_horas=48, recentes=8, faixa_horas=12, por_id=None):
    """Quanto o vídeo faz nas primeiras horas — e quais estão acima disso AGORA.

    POR QUE ISTO É O PAINEL MAIS URGENTE DE TODOS. Reagir a um vídeo que está
    subindo só vale enquanto ele sobe: responder comentário, fixar comentário,
    gravar a parte 2, empurrar o link. ISTO diz, dentro da janela, quais vídeos
    merecem a energia. (A meia-vida dela, medida enquanto o painel existiu, era
    de 2 dias para juntar 80% das views: é a janela em que vale insistir.)

    DUAS ARMADILHAS, as duas descobertas medindo os dados reais dela:

    1. **A hora da leitura é a que está gravada, não 21h.** A leitura automática
       é às 21h, mas o botão "Ler agora" roda quando ela aperta — a fotografia
       de 07/09 foi lida às 08h31. Assumir 21h fazia um vídeo publicado às 07h
       daquele dia contar como "1 view em 13 horas" quando eram 1,5 hora. Cada
       fotografia carrega `lido_em`; é dele que a idade sai.

    2. **Comparar 14 horas com 28 horas não compara nada.** Vídeo medido mais
       tarde tem naturalmente mais views, e a "mediana da largada" misturada
       fazia todo vídeo do dia parecer fraco e todo vídeo da véspera parecer
       forte. A mediana é por FAIXA de idade (`faixa_horas`), e cada vídeo se
       compara com a faixa dele.
    """
    if len(fotos) < 2:
        return {"pronto": False, "faltam": 2 - len(fotos), "itens": [],
                "mediana": None, "amostra": 0, "janela_horas": janela_horas}

    primeira_leitura = {}
    for f in fotos:
        instante = None
        if f.get("lido_em"):
            try:
                instante = datetime.fromtimestamp(int(f["lido_em"]))
            except (ValueError, OSError, TypeError):
                instante = None
        if instante is None:
            # Fotografia antiga, de antes de `lido_em` existir: 21h é o melhor
            # palpite, porque é a hora da leitura automática.
            try:
                instante = datetime.strptime(f.get("dia") or "", "%Y-%m-%d").replace(hour=21)
            except ValueError:
                continue
        for v in f.get("videos") or []:
            vid = v.get("id")
            if not vid or vid in primeira_leitura:
                continue
            nasceu = quando(v.get("create_time"))
            if not nasceu:
                continue
            horas = (instante - nasceu).total_seconds() / 3600.0
            if horas <= 0 or horas > janela_horas:
                continue        # nasceu depois da leitura, ou já é vídeo velho
            primeira_leitura[vid] = dict(
                identidade(v, (por_id or {}).get(vid)), **{
                    "id": vid, "views": n(v.get("view_count")),
                    "horas": round(horas, 1),
                    "faixa": int(horas // faixa_horas), "nasceu": nasceu,
                })

    if not primeira_leitura:
        return {"pronto": True, "itens": [], "mediana": None, "amostra": 0,
                "janela_horas": janela_horas}

    por_faixa = {}
    for x in primeira_leitura.values():
        por_faixa.setdefault(x["faixa"], []).append(x["views"])
    medianas = {k: mediana(vs) for k, vs in por_faixa.items()}

    itens = sorted(primeira_leitura.values(), key=lambda x: -x["nasceu"].timestamp())
    for x in itens:
        med = medianas.get(x["faixa"])
        # Faixa com pouca gente ainda não é régua: sem isso, o primeiro vídeo de
        # uma faixa nova viraria "1,0x" só por ser o único, e a tela diria que
        # está normal sem ter com o que comparar.
        confiavel = len(por_faixa.get(x["faixa"]) or []) >= MINIMO_DE_VIDEOS
        x["vezes_a_largada"] = (round(x["views"] / med, 2)
                                if (med and confiavel) else None)
        x["mediana_da_faixa"] = med if confiavel else None
        x["faixa_rotulo"] = "%d-%dh" % (x["faixa"] * faixa_horas,
                                        (x["faixa"] + 1) * faixa_horas)
        x["comparaveis"] = len(por_faixa.get(x["faixa"]) or [])
        x.pop("nasceu")
    return {"pronto": True, "mediana": mediana(list(primeira_leitura and
                                                    [x["views"] for x in
                                                     primeira_leitura.values()])),
            "amostra": len(primeira_leitura), "faixa_horas": faixa_horas,
            "janela_horas": janela_horas, "itens": itens[:recentes]}


# ------------------------------------------------------------ o plano do dia

def plano_do_dia(vendas_, largada_, refazer_, cadencia=None):
    """A lista de gravação de hoje: quantos vídeos, e de que tipo cada um.

    POR QUE ISTO EXISTE (fase C.3). A pauta diz o que fazer; o plano diz
    quanto de cada coisa cabe no dia. A Owra chama de "campeões × apostas".
    O tamanho é a cadência DELA (mediana de vídeos por dia no mês), não um
    número de manual: uma lista de 15 num dia de 8 é lista que não se cumpre.

    A DIVISÃO: metade em campeões (produtos que vendem — só existem com
    relatório de vendas), um quarto em apostas (vídeos que largaram bem:
    parte 2 enquanto sobe), um ou dois refazer, e o resto em novo (produto
    que ainda não foi testado — sem isso a conta para de descobrir). Sem
    vendas na pasta, os campeões viram "novo" e a lista diz por quê.
    """
    n = max(3, min(12, int(cadencia or 6)))
    itens = []
    vd = vendas_ or {}
    lg = largada_ or {}
    rf = refazer_ or {}

    # CAMPEÕES: os produtos que mais pagaram (acelerando primeiro).
    campeoes = []
    vistos = set()
    for x in (vd.get("produtos_acelerando") or []):
        if x["produto"] not in vistos:
            vistos.add(x["produto"])
            campeoes.append(("acelerando", x["produto"],
                             "%d pedido(s) nesta semana, %sx a anterior" % (x["pedidos_semana"], x["vezes"])))
    for x in (vd.get("por_produto") or []):
        if x["produto"] not in vistos and (x.get("comissao") or 0) > 0:
            vistos.add(x["produto"])
            campeoes.append(("campeão", x["produto"],
                             "R$ %s em %d pedido(s) nos últimos 30 dias"
                             % (("%.2f" % x["comissao"]).replace(".", ","), x["pedidos"])))
    vagas_campeoes = (n + 1) // 2
    for tipo, produto, motivo in campeoes[:vagas_campeoes]:
        itens.append({"tipo": tipo, "texto": "Outro corte de %s" % produto, "motivo": motivo})

    # APOSTAS: parte 2 do que largou acima do normal.
    subindo = sorted([i for i in (lg.get("itens") or []) if (i.get("vezes_a_largada") or 0) >= 1.5],
                     key=lambda i: -i["vezes_a_largada"])
    vagas_apostas = max(1, n // 4)
    for i in subindo[:vagas_apostas]:
        itens.append({"tipo": "aposta", "id": i.get("id"), "link": i.get("link"),
                      "texto": "Parte 2 de \"%s\"" % i.get("titulo"),
                      "motivo": "largou %sx acima do normal (%s views em %sh)"
                                % (i["vezes_a_largada"], "%.0f" % i["views"], i["horas"])})

    # REFAZER: um ou dois, sem repetir título.
    vistos_t, refazer = set(), []
    for i in rf.get("itens") or []:
        t = (i.get("titulo") or "").strip().lower()
        if t and t not in vistos_t:
            vistos_t.add(t)
            refazer.append(i)
    for i in refazer[:max(1, n // 6)]:
        itens.append({"tipo": "refazer", "id": i.get("id"), "link": i.get("link"),
                      "texto": "Refazer \"%s\" com outra capa e outro gancho" % i.get("titulo"),
                      "motivo": "%s (%sx a sua mediana)" % (i.get("motivo"), i.get("forca"))})

    # NOVO: o que sobrar. É onde a conta descobre o próximo campeão.
    novos = max(0, n - len(itens))
    for _ in range(novos):
        itens.append({"tipo": "novo", "texto": "Produto ainda não testado",
                      "motivo": "um por dia mantém a descoberta viva"})

    return {"quantos": n, "cadencia": cadencia, "itens": itens[:n],
            "sem_vendas": not bool(vd.get("tem_dados")),
            "campeoes": sum(1 for i in itens if i["tipo"] in ("campeão", "acelerando")),
            "apostas": sum(1 for i in itens if i["tipo"] == "aposta"),
            "refazer": sum(1 for i in itens if i["tipo"] == "refazer"),
            "novos": sum(1 for i in itens if i["tipo"] == "novo")}


# ------------------------------------------------------------------- a pauta

def pauta(largada_, refazer_, monet, vendas_=None, quantos=8):
    """A lista do dia seguinte, em frases que ela pode executar.

    POR QUE EM FRASE, e não mais um gráfico: nenhum painel desta tela diz o que
    FAZER — cada um diz um pedaço e deixa a conclusão por conta de quem lê. Ela
    grava 15 vídeos por dia; a tradução tem que estar pronta na tela, ou vira
    mais um número bonito que não muda nada.

    Cada linha carrega de onde saiu. Conselho sem origem, ela não tem como
    conferir — e conselho que não se confere, com o tempo, não se segue.

    RECEBE OS PAINÉIS PRONTOS em vez de recalculá-los: a versão anterior
    chamava largada, refazer, esquecidos, hashtags, cadência e ganchos por
    dentro, e isso eram 4,4 dos 44 segundos da tela — tudo já calculado uma
    linha acima em `metricas.tudo()`.

    A LINHA DE DINHEIRO VEM PRIMEIRO. Ela passou de 10 mil seguidores; o que
    decide se a conta monetiza é gravar acima de 1 minuto e manter 100 mil
    views em 30 dias. Isso vale mais que qualquer vídeo específico.
    """
    linhas = []

    m = monet or {}
    # SEGUIDORES ABAIXO DA REGRA vem antes de tudo: é a porta do programa. Só
    # aparece quando o número foi lido - sem leitura, o cartão da monetização
    # já diz o que falta, e repetir aqui seria conselho sem dado.
    seg = m.get("seguidores")
    piso = (m.get("regras") or {}).get("seguidores") or 10000
    if seg is not None and seg < piso:
        faltam = piso - seg
        ritmo = m.get("seguidores_por_dia")
        texto = "A conta tem %s seguidores; a regra pede %s — faltam %s." % (
            "{:,}".format(int(seg)).replace(",", "."),
            "{:,}".format(int(piso)).replace(",", "."),
            "{:,}".format(int(faltam)).replace(",", "."))
        if ritmo and ritmo > 0:
            texto += " No ritmo atual (%s por dia) são uns %d dias." % (
                ("%.0f" % ritmo), int(round(faltam / ritmo)))
        linhas.append({"acao": "FALTAM SEGUIDORES", "texto": texto,
                       "de_onde": "perfil lido em %s" % m.get("seguidores_lido_em")})

    if m.get("pronto"):
        regras = m.get("regras") or {}
        pct = m.get("pct_longos")
        # GRAVE MAIS LONGO vale pela AUDIÊNCIA, não pelo programa: vídeo de
        # loja não ganha recompensa de jeito nenhum, mas o longo ganha 5 a 7x
        # mais views novas — e views em vídeo de loja viram clique e comissão.
        # `> 1`, e não só "existe": com 0,6x a linha antiga mandava gravar
        # mais longo citando o número que provava o contrário (revisão 19/09).
        if pct is not None and pct < 50 and (m.get("longo_vs_curto") or 0) > 1:
            linhas.append({
                "acao": "GRAVE MAIS LONGO",
                "texto": "Só %s%% dos %d vídeos dos últimos %d dias passam de 1 minuto, e "
                         "neste período o vídeo longo ganhou %sx mais views novas por vídeo "
                         "do que o curto. Em vídeo de loja, view é clique no produto."
                         % (("%.0f" % pct), m.get("publicados") or 0,
                            m.get("janela_dias") or 30, m["longo_vs_curto"]),
                "de_onde": "monetização: %d vídeos medidos em %d dia(s)"
                           % (m.get("videos_medidos") or 0, m.get("dias_medidos") or 0),
            })
        # RECOMPENSAS: a conta pode bater seguidores e views e não ter UM vídeo
        # que o programa pague. Dizer isso é mais útil do que fingir que a
        # regra de 1 minuto se aplica ao que ela grava.
        if m.get("publicados") and m.get("elegiveis_recompensa") == 0:
            linhas.append({
                "acao": "RECOMPENSAS: NADA ELEGÍVEL",
                "texto": "Nenhum dos %d vídeos dos últimos %d dias é pago pelo Programa de "
                         "Recompensas: %d têm link de loja (excluídos pela regra) e os %d sem "
                         "link não passam de 1 minuto. A receita desta conta é comissão — a "
                         "régua está no painel de Vendas. Recompensa só entraria com uma "
                         "linha à parte de vídeos sem produto, longos e originais."
                         % (m.get("publicados") or 0, m.get("janela_dias") or 30,
                            m.get("publicados_loja") or 0, m.get("publicados_sem_loja") or 0),
                "de_onde": "vídeo de loja reconhecido pela #tiktokshop na descrição (proxy)",
            })
        vezes = m.get("views_vezes")
        folga = regras.get("folga") or 1.5
        if vezes is not None and vezes < folga:
            linhas.append({
                "acao": "ATENÇÃO ÀS VIEWS" if m.get("views_ok") else "FORA DA REGRA",
                "texto": "A conta está em %s views em 30 dias%s — a regra pede %s. "
                         "%s" % ("{:,}".format(m.get("views_30d") or 0).replace(",", "."),
                                 " (projetado)" if m.get("projetado") else "",
                                 "{:,}".format(regras.get("views_30d") or 0).replace(",", "."),
                                 "Está dentro, mas sem folga." if m.get("views_ok")
                                 else "Está fora."),
                "de_onde": "monetização: ganho de views desde %s" % m.get("desde"),
            })

    # DINHEIRO ANTES DE AUDIÊNCIA (fase 2). Quando há vendas, o vídeo que mais
    # rendeu comissão nos últimos 30 dias e ainda vende é o primeiro conselho:
    # empurrar o que já converte é mais barato que descobrir o que converte.
    vd = vendas_ or {}
    if vd.get("tem_dados"):
        vive = [x for x in (vd.get("ainda_vende") or []) if (x.get("comissao") or 0) > 0]
        top = vive[0] if vive else next(
            (x for x in (vd.get("por_video") or []) if (x.get("comissao") or 0) > 0), None)
        if top:
            linhas.append({
                "acao": "EMPURRE O QUE VENDE",
                "id": top.get("id"),
                "link": top.get("link"), "capa": top.get("capa"),
                "texto": '"%s" rendeu R$ %s de comissão em %d pedido(s) nos últimos 30 dias%s. '
                         "Fixe o comentário com o link, responda quem pergunta preço, e grave "
                         "outro corte do mesmo produto."
                         % (top.get("titulo"), ("%.2f" % top["comissao"]).replace(".", ","),
                            top.get("pedidos") or 0,
                            (" (último pedido em %s)" % top["ultimo_pedido"]) if top.get("ultimo_pedido") else ""),
                "de_onde": "vendas: %d vídeo(s) com pedido no período" % (vd.get("videos_com_venda") or 0),
            })
        # PRODUTO ACELERANDO e COMISSÃO MUDOU (fase C.2): decisão de amanhã
        # de manhã nos dois casos — gravar mais do que está subindo; parar
        # de empurrar o que passou a pagar menos.
        for x in (vd.get("produtos_acelerando") or [])[:2]:
            linhas.append({
                "acao": "PRODUTO ACELERANDO",
                "texto": "%s: %d pedido(s) nesta semana contra %d na anterior (%sx), R$ %s de "
                         "comissão. Grave outro corte enquanto está subindo."
                         % (x["produto"], x["pedidos_semana"], x["pedidos_anterior"],
                            x["vezes"], ("%.2f" % x["comissao_semana"]).replace(".", ",")),
                "de_onde": "vendas: semana × semana anterior",
            })
        for x in (vd.get("comissao_mudou") or [])[:1]:
            linhas.append({
                "acao": "COMISSÃO MUDOU",
                "texto": "%s paga R$ %s por pedido agora, contra R$ %s na semana anterior "
                         "(%s%s%%). %s"
                         % (x["produto"], ("%.2f" % x["por_pedido_agora"]).replace(".", ","),
                            ("%.2f" % x["por_pedido_antes"]).replace(".", ","),
                            "+" if x["variacao_pct"] >= 0 else "", x["variacao_pct"],
                            "Vale mais cada vídeo dele." if x["variacao_pct"] >= 0
                            else "Confira a taxa na Central antes de gravar mais."),
                "de_onde": "vendas: comissão por pedido, semana × anterior",
            })
        sem = vd.get("sem_video") or {}
        if (sem.get("pedidos") or 0) > 0 and not (vd.get("por_video") or []):
            linhas.append({
                "acao": "VENDAS SEM VÍDEO",
                "texto": "Há %d pedido(s) no período que o painel não consegue ligar a nenhum "
                         "vídeo: a fonte não traz id nem link do vídeo. Exporte da Central o "
                         "relatório por vídeo, ou veja o log da API." % sem["pedidos"],
                "de_onde": "vendas: fontes sem identificação de vídeo",
            })

    lg = largada_ or {}
    if lg.get("pronto") and lg.get("mediana"):
        subindo = sorted([i for i in lg["itens"]
                          if (i["vezes_a_largada"] or 0) >= 1.5],
                         key=lambda i: -i["vezes_a_largada"])
        for i in subindo[:2]:
            linhas.append({
                "acao": "EMPURRE HOJE",
                "id": i.get("id"),
                "link": i.get("link"), "capa": i.get("capa"),
                "texto": '"%s" largou %sx acima do normal (%s views em %sh). '
                         "Responda os comentários e grave a parte 2 enquanto sobe."
                         % (i["titulo"], i["vezes_a_largada"],
                            "%.0f" % i["views"], i["horas"]),
                "de_onde": "mediana de %.0f views entre os %d vídeos com "
                           "%s de vida" % (i["mediana_da_faixa"],
                                           i["comparaveis"], i["faixa_rotulo"]),
            })

    # O MESMO VÍDEO NÃO OCUPA DUAS VAGAS. Ela publica o mesmo produto em cortes
    # diferentes com o mesmo título ("@Piracanjuba #meucarnavalproforce", duas
    # vezes, 137 e 135 views), e os dois saíam na pauta como se fossem duas
    # ideias. A lista tem duas vagas para REFAÇA; que sejam dois assuntos.
    rf = refazer_ or {}
    vistos, escolhidos = set(), []
    for i in rf.get("itens") or []:
        chave = (i.get("titulo") or "").strip().lower()
        if chave in vistos:
            continue
        vistos.add(chave)
        escolhidos.append(i)
        if len(escolhidos) == 2:
            break
    for i in escolhidos:
        linhas.append({
            "acao": "REFAÇA",
            "id": i.get("id"),
            "link": i.get("link"), "capa": i.get("capa"),
            "texto": '"%s" só fez %s views, mas %s (%.2f%%, %sx a sua mediana). '
                     "O assunto passou no teste; troque capa e gancho e poste de novo."
                     % (i["titulo"], "%.0f" % i["views"], i["motivo"],
                        i["taxa_compartilhamento"] if i["motivo"].startswith("compart")
                        else i["taxa_comentario"], i["forca"]),
            "de_onde": "mediana da conta: %.0f views" % rf["mediana_views"],
        })

    return {"itens": linhas[:quantos]}

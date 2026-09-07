# -*- coding: utf-8 -*-
"""O que gravar amanhã — os painéis que respondem "sobre o quê", não "como foi".

POR QUE ISTO EXISTE (07/09/2026). Pedido dele: *"pense como um influenciador,
buscando melhorias em como achar vídeos novos e assuntos novos para postar"*.

O que já existia responde **como postar** (duração, horário, ritmo) e **o que
aconteceu** (acelerando, ressuscitou, meia-vida). Nada respondia **o que
gravar**. `metricas.temas()` chegava perto, mas jogava fora as duas pistas de
assunto mais explícitas que existem nos dados:

  - **as hashtags**, que são o assunto ROTULADO por ela mesma. O código antigo
    apagava `#...` antes de contar palavras — de propósito, para `#fyp` não
    poluir o ranking. Só que jogar fora `#quebracabeça` junto era jogar fora o
    catálogo de assuntos dela inteiro. E a régua já resolve o `#fyp` sozinha:
    hashtag que está em quase todo vídeo tem mediana igual à mediana geral, e
    aparece como 1,0x — sozinha no meio do ranking, sem precisar de lista negra.
  - **as menções**, que na conta dela são as MARCAS. Ela é afiliada; saber qual
    parceria rende é decisão de negócio, não de curiosidade.

AS DUAS REGRAS DA CASA VALEM AQUI (ver metricas.py): mediana e nunca média, e
toda comparação diz de quantos vídeos saiu.

E A REGRA NOVA, que este arquivo inteiro obedece: **um painel só entra se ela
puder fazer alguma coisa com ele amanhã de manhã.** "Assunto que rendia e você
parou de postar" cabe; "distribuição de views por decil" não cabe.
"""

import re
from datetime import datetime, timedelta

from comum import (MINIMO_DE_VIDEOS, MINIMO_DE_VIEWS, identidade, mediana, n,
                   palavras, quando, texto_do_video)

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
    geral — e é ela que faz `#fyp` cair sozinho para 1,0x sem lista negra.
    """
    geral = mediana([n(v.get("view_count")) for v in videos])
    if not geral:
        return {"geral": None, "amostra": 0, "itens": [], "piores": []}

    onde = {}
    quais = {}
    quando_ultimo = {}
    for v in videos:
        publicado = quando(v.get("create_time"))
        for termo in set(extrair(v) or []):
            onde.setdefault(termo, []).append(n(v.get("view_count")))
            # QUAIS vídeos, e não só quantos. É o que permite descobrir que
            # "#suportecarro" e "veicular suporte" são os MESMOS seis vídeos —
            # dois nomes para uma pauta só. Ver `_sem_repetir`.
            quais.setdefault(termo, set()).add(v.get("id"))
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
            # Em quantos % dos vídeos o termo aparece. É o que denuncia a
            # hashtag-de-encher: 90% de presença e 1,0x não é assunto, é hábito.
            "presenca": round(len(vistos) / total * 100, 1) if total else 0,
            "ultimo_uso": ultimo.strftime("%Y-%m-%d") if ultimo else None,
            "dias_sem_usar": (datetime.now() - ultimo).days if ultimo else None,
            "ids": quais.get(termo) or set(),
        })
    itens.sort(key=lambda x: -(x["vezes_a_geral"] or 0))
    return {"geral": geral, "amostra": total, "itens": itens[:quantos],
            "piores": itens[-quantos:][::-1] if len(itens) > quantos else [],
            "todos": itens}


# --------------------------------------------------------------- os assuntos

def _tags_do_video(v):
    """As hashtags, em minúscula.

    O hífen NÃO entra no conjunto de caracteres de propósito: o TikTok corta a
    hashtag no primeiro caractere que não é letra ou número, então `#quebra-cabeça`
    vira a tag `quebra` lá dentro. Aceitar o hífen aqui inventaria uma hashtag
    que não existe na plataforma e que ninguém pode pesquisar.
    """
    return [t.lower() for t in
            re.findall(r"#([0-9A-Za-zÀ-ÿ_]+)", texto_do_video(v))]


def _sem_repetir(itens, sobreposicao=0.7):
    """Tira os termos que descrevem o MESMO punhado de vídeos.

    Achado testando com os dados dela: a pauta saía com "#suportecarro" (8,88x,
    6 vídeos), "veicular suporte" (8,88x, 6 vídeos) e "acabarem alves" (8,88x,
    6 vídeos) — três linhas, uma pauta só. O número idêntico entregou o jogo:
    são as mesmas seis publicações vistas por três recortes do texto.

    Três linhas iguais numa lista de oito ocupam o lugar de três ideias
    diferentes, que é o único produto desta tela. O primeiro termo fica (a lista
    já vem ordenada pelo que rendeu mais) e os que repetem os mesmos vídeos
    saem.
    """
    fora = []
    for i in itens:
        meus = i.get("ids") or set()
        if any(meus and len(meus & (j.get("ids") or set())) /
               float(len(meus)) >= sobreposicao for j in fora):
            continue
        fora.append(i)
    return fora


def hashtags(videos, minimo=4, quantos=15):
    """Que hashtag rende mais — o assunto rotulado por ela mesma.

    A tela precisa dizer o que a coluna "presença" significa: hashtag que ela
    põe em tudo (`#tiktokshopbr77`, `#creatorsearchinsights`) não separa vídeo
    bom de ruim, e vai aparecer perto de 1,0x. As que sobem acima disso são as
    que marcam ASSUNTO — e assunto é o que dá para repetir amanhã.
    """
    return _ranking(videos, _tags_do_video, minimo, quantos,
                    rotular=lambda t: "#" + t)


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
    """
    return _ranking(videos, _mencoes_do_video, minimo, quantos,
                    rotular=lambda m: "@" + m)


def _frases_do_video(v):
    """Pares de palavras vizinhas — "quebra cabeça", "kit pincéis".

    Palavra solta espalha o assunto: "kit" aparece em kit de pincéis, kit de
    maquiagem e kit de cozinha, e a mediana de "kit" não descreve nenhum dos
    três. O par de palavras é a menor unidade que ainda é um ASSUNTO.

    As palavras de ligação já saíram em `palavras()`, então "kit de pincéis"
    chega aqui como "kit pinceis" — o par vizinho depois da limpeza, que é o
    que junta as variações que ela escreve de jeitos diferentes.
    """
    ps = palavras(texto_do_video(v))
    return [ps[i] + " " + ps[i + 1] for i in range(len(ps) - 1)]


def frases(videos, minimo=4, quantos=15):
    """Assunto em duas palavras. Mais específico que `metricas.temas()`."""
    return _ranking(videos, _frases_do_video, minimo, quantos)


def _gancho_do_video(v, palavras_do_gancho=3):
    """As primeiras palavras do TÍTULO — o que a pessoa lê antes de decidir.

    Só o título, nunca a descrição: a descrição é onde moram as hashtags e o
    texto de afiliado, e ninguém lê aquilo antes de decidir se fica no vídeo.
    """
    ps = palavras(v.get("title") or "")[:palavras_do_gancho]
    return [" ".join(ps)] if len(ps) == palavras_do_gancho else []


def ganchos(videos, minimo=3, quantos=12):
    """Que abertura de título rendeu mais.

    Ela publica 15-16 vídeos por dia e repete fórmulas de abertura sem medir
    qual delas funciona. Isto mede — e trocar a abertura é a mudança mais
    barata que existe: não exige regravar nada.
    """
    return _ranking(videos, _gancho_do_video, minimo, quantos)


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


def esquecidos(videos, dias=21, minimo=5, quantos=12, forca=1.3):
    """Assunto que rendia acima da média dela e que ela parou de postar.

    POR QUE ISTO É O PAINEL MAIS PARECIDO COM "TEMA NOVO". Ninguém tem ideia
    nova todo dia, e a conta dela já tem 2.300 vídeos de tentativas. O assunto
    que rendeu 2x e sumiu há um mês é uma pauta pronta que ela já sabe gravar,
    com público já testado — custa uma tarde, não uma aposta.

    Vale para hashtag e para frase, com o rótulo do tipo junto: são as duas
    unidades que descrevem assunto sem virar palavra solta.
    """
    fora = []
    for tipo, funcao in (("hashtag", hashtags), ("assunto", frases)):
        r = funcao(videos, minimo=minimo, quantos=10 ** 6)
        for i in r.get("todos") or []:
            if (i["vezes_a_geral"] or 0) < forca:
                continue
            if i["dias_sem_usar"] is None or i["dias_sem_usar"] < dias:
                continue
            # Hashtag que ela põe em quase tudo não é assunto esquecido: se
            # aparece em 60% dos vídeos e "sumiu", o que mudou foi o hábito de
            # marcar, não o assunto gravado.
            if i["presenca"] > 40:
                continue
            fora.append(dict(i, tipo=tipo))
    # O que rendeu mais primeiro; o tempo parado só desempata. Ela tem uma noite
    # por semana para isso, e a ordem da lista é a ordem em que ela vai gravar.
    #
    # NO EMPATE, A HASHTAG GANHA DA FRASE, e isso decide mais do que parece:
    # os mesmos 6 vídeos apareciam como "#suportecarro" e como "acabarem alves"
    # (pedaço da assinatura que ela escreve no fim do texto), empatados em
    # 8,88x. `_sem_repetir` mantém o primeiro — e o primeiro tem que ser o que
    # ela consegue usar. "#suportecarro" é assunto, dá para pesquisar e dá para
    # repetir; "acabarem alves" não é pauta de nada.
    fora.sort(key=lambda x: (-(x["vezes_a_geral"] or 0),
                             x["tipo"] != "hashtag",
                             -(x["dias_sem_usar"] or 0)))
    return {"itens": [_enxuto(i) for i in _sem_repetir(fora)[:quantos]],
            "dias": dias}


def taxa_de_comentario(videos, quantos=10):
    """Comentário por view — onde o público está PEDINDO conteúdo.

    Compartilhamento mede alcance; comentário mede vontade de conversar. Na
    prática, o vídeo muito comentado é o que gerou dúvida — e dúvida é pauta
    pronta: o próximo vídeo é a resposta, e já nasce com público interessado.
    """
    itens = []
    for v in videos:
        vistos = n(v.get("view_count"))
        if vistos < MINIMO_DE_VIEWS:
            continue
        itens.append(dict(identidade(v), id=v.get("id"), views=vistos,
                          comentarios=n(v.get("comment_count")),
                          taxa=round(n(v.get("comment_count")) / vistos * 100, 2)))
    itens.sort(key=lambda x: -x["taxa"])
    return {"itens": itens[:quantos], "amostra": len(itens),
            "mediana": mediana([i["taxa"] for i in itens])}


# -------------------------------------------------------------- a rotina dela

def cadencia(videos, maturacao_dias=3, quantos=21):
    """Postar mais no mesmo dia está diluindo o resultado de cada vídeo?

    A PERGUNTA MAIS CARA DA ROTINA DELA. São 15-16 vídeos por dia; se a partir
    do décimo o retorno cai, ela está gastando horas para empurrar o próprio
    vídeo para baixo. `metricas.ritmo()` já cruza cadência com resultado por
    SEMANA — mas a decisão dela é diária ("gravo mais um hoje ou não?"), e a
    semana esconde o dia dentro da média.

    OS ÚLTIMOS DIAS FICAM DE FORA (`maturacao_dias`). Vídeo de ontem ainda está
    sendo entregue: incluí-lo faria todo dia recente parecer fraco e a conta
    diria "poste menos" só porque a leitura é recente.
    """
    corte = datetime.now() - timedelta(days=maturacao_dias)
    por_dia = {}
    for v in videos:
        q = quando(v.get("create_time"))
        if not q or q > corte:
            continue
        por_dia.setdefault(q.strftime("%Y-%m-%d"), []).append(n(v.get("view_count")))

    dias = [{"dia": d, "videos": len(vs), "mediana": mediana(vs)}
            for d, vs in sorted(por_dia.items())]
    if len(dias) < 6:
        return {"pronto": False, "dias": dias, "faltam": 6 - len(dias)}

    # O corte é a mediana DELA de vídeos por dia, não um número inventado: a
    # pergunta é "mais do que o meu normal atrapalha?", e o normal é o dela.
    corte_de_volume = mediana([d["videos"] for d in dias]) or 0
    leves = [d["mediana"] for d in dias if d["videos"] <= corte_de_volume]
    pesados = [d["mediana"] for d in dias if d["videos"] > corte_de_volume]
    resposta = {"pronto": True, "dias": dias[-quantos:],
                "corte": corte_de_volume,
                "leves": {"dias": len(leves), "mediana": mediana(leves)},
                "pesados": {"dias": len(pesados), "mediana": mediana(pesados)}}
    a, b = resposta["leves"]["mediana"], resposta["pesados"]["mediana"]
    # Só conclui com os dois lados na mão e com dias suficientes de cada lado.
    # Meia comparação vira conselho inventado, e conselho de rotina é o mais
    # caro de seguir errado.
    if a and b and len(leves) >= MINIMO_DE_VIDEOS and len(pesados) >= MINIMO_DE_VIDEOS:
        resposta["diferenca"] = round((b - a) / a * 100, 1)
    return resposta


def largada(fotos, janela_horas=48, recentes=8, faixa_horas=12, por_id=None):
    """Quanto o vídeo faz nas primeiras horas — e quais estão acima disso AGORA.

    POR QUE ISTO É O PAINEL MAIS URGENTE DE TODOS. Reagir a um vídeo que está
    subindo só vale enquanto ele sobe: responder comentário, fixar comentário,
    gravar a parte 2, empurrar o link. A meia-vida dela mede quanto tempo a
    janela dura; ISTO diz, dentro da janela, quais vídeos merecem a energia.

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


# ------------------------------------------------------------------- a pauta

def pauta(videos, fotos, quantos=8, por_id=None):
    """A lista do dia seguinte, em frases que ela pode executar.

    POR QUE EM FRASE, e não mais um gráfico: nenhum painel desta tela diz o que
    FAZER — cada um diz um pedaço e deixa a conclusão por conta de quem lê. Ela
    grava 15 vídeos por dia; a tradução tem que estar pronta na tela, ou vira
    mais um número bonito que não muda nada.

    Cada linha carrega de onde saiu. Conselho sem origem, ela não tem como
    conferir — e conselho que não se confere, com o tempo, não se segue.
    """
    linhas = []

    lg = largada(fotos, por_id=por_id)
    if lg.get("pronto") and lg.get("mediana"):
        subindo = sorted([i for i in lg["itens"]
                          if (i["vezes_a_largada"] or 0) >= 1.5],
                         key=lambda i: -i["vezes_a_largada"])
        for i in subindo[:2]:
            linhas.append({
                "acao": "EMPURRE HOJE",
                "link": i.get("link"), "capa": i.get("capa"),
                "texto": '"%s" largou %sx acima do normal (%s views em %sh). '
                         "Responda os comentários e grave a parte 2 enquanto sobe."
                         % (i["titulo"], i["vezes_a_largada"],
                            "%.0f" % i["views"], i["horas"]),
                "de_onde": "mediana de %.0f views entre os %d vídeos com "
                           "%s de vida" % (i["mediana_da_faixa"],
                                           i["comparaveis"], i["faixa_rotulo"]),
            })

    rf = refazer(videos)
    for i in rf["itens"][:2]:
        linhas.append({
            "acao": "REFAÇA",
            "link": i.get("link"), "capa": i.get("capa"),
            "texto": '"%s" só fez %s views, mas %s (%.2f%%, %sx a sua mediana). '
                     "O assunto passou no teste; troque capa e gancho e poste de novo."
                     % (i["titulo"], "%.0f" % i["views"], i["motivo"],
                        i["taxa_compartilhamento"] if i["motivo"].startswith("compart")
                        else i["taxa_comentario"], i["forca"]),
            "de_onde": "mediana da conta: %.0f views" % rf["mediana_views"],
        })

    esq = esquecidos(videos)
    for i in esq["itens"][:3]:
        linhas.append({
            "acao": "VOLTE AO ASSUNTO",
            "texto": '%s rendeu %sx a sua mediana em %d vídeos e você não posta '
                     "há %d dias." % (i["termo"], i["vezes_a_geral"], i["videos"],
                                      i["dias_sem_usar"]),
            "de_onde": "último uso em %s" % i["ultimo_uso"],
        })

    ht = hashtags(videos)
    # AINDA VIVO: sem o corte de dias, a mesma hashtag saía como "REPITA,
    # ainda é assunto vivo" e como "VOLTE AO ASSUNTO, parada há 67 dias" na
    # mesma lista — duas frases opostas sobre a mesma coisa, e a lista inteira
    # perde a confiança de quem lê.
    # `_sem_repetir` aqui também: `#puzzle` e `#noiteestrelada` são as duas
    # hashtags dos MESMOS vídeos de quebra-cabeça, e ocupariam as duas vagas
    # de "repita" com uma ideia só.
    quentes = _sem_repetir(
        [i for i in ht["itens"] if (i["vezes_a_geral"] or 0) >= 1.3
         and i["presenca"] <= 40
         and (i["dias_sem_usar"] is not None and i["dias_sem_usar"] <= 14)])[:2]
    for i in quentes:
        linhas.append({
            "acao": "REPITA",
            "texto": "%s está %sx acima da sua mediana (%d vídeos) e ainda é "
                     "assunto vivo — vale mais um esta semana."
                     % (i["termo"], i["vezes_a_geral"], i["videos"]),
            "de_onde": "hashtags, mediana geral %.0f views" % (ht["geral"] or 0),
        })

    cd = cadencia(videos)
    if cd.get("pronto") and cd.get("diferenca") is not None:
        if cd["diferenca"] <= -15:
            linhas.append({
                "acao": "POSTE MENOS",
                "texto": "Nos dias em que você passa de %d vídeos, a mediana de "
                         "cada um cai %.0f%%. Menos vídeos melhor acabados rendem "
                         "mais que a fila inteira."
                         % (cd["corte"], abs(cd["diferenca"])),
                "de_onde": "%d dias leves contra %d dias pesados"
                           % (cd["leves"]["dias"], cd["pesados"]["dias"]),
            })
        elif cd["diferenca"] >= 15:
            linhas.append({
                "acao": "PODE POSTAR MAIS",
                "texto": "Nos dias em que você passa de %d vídeos, a mediana de "
                         "cada um ainda sobe %.0f%% — o volume não está "
                         "atrapalhando." % (cd["corte"], cd["diferenca"]),
                "de_onde": "%d dias leves contra %d dias pesados"
                           % (cd["leves"]["dias"], cd["pesados"]["dias"]),
            })

    gc = ganchos(videos)
    if gc["itens"] and (gc["itens"][0]["vezes_a_geral"] or 0) >= 1.3:
        i = gc["itens"][0]
        linhas.append({
            "acao": "COMECE ASSIM",
            "texto": 'Títulos que começam com "%s" fazem %sx a sua mediana '
                     "(%d vídeos). Trocar a abertura não custa regravar nada."
                     % (i["termo"], i["vezes_a_geral"], i["videos"]),
            "de_onde": "ganchos de título",
        })

    return {"itens": linhas[:quantos]}


def _enxuto(d):
    """Deixa de fora o que é ferramenta interna, não resposta para a tela.

    `todos` existe porque `esquecidos` precisa varrer o ranking inteiro, e
    `ids` porque `_sem_repetir` precisa saber de quais vídeos cada termo veio.
    Nenhum dos dois é desenhado; mandar os dois numa conta de 2.300 vídeos
    pesaria mais que todo o resto da resposta junto. E `ids` é um `set`, que
    nem sequer atravessa o `json.dumps` — sem esta limpeza, a tela quebra
    inteira em vez de só ficar pesada.
    """
    return {k: v for k, v in d.items() if k not in ("todos", "ids")}


def _ranking_enxuto(r):
    """Um ranking inteiro pronto para virar JSON: sem `todos`, sem `ids`."""
    limpo = _enxuto(r)
    for chave in ("itens", "piores"):
        limpo[chave] = [_enxuto(i) for i in (limpo.get(chave) or [])]
    return limpo


def tudo(videos, fotos, por_id=None):
    """Todos os painéis de conteúdo numa chamada só."""
    return {
        "pauta": pauta(videos, fotos, por_id=por_id),
        "largada": largada(fotos, por_id=por_id),
        "hashtags": _ranking_enxuto(hashtags(videos)),
        "parcerias": _ranking_enxuto(parcerias(videos)),
        "frases": _ranking_enxuto(frases(videos)),
        "ganchos": _ranking_enxuto(ganchos(videos)),
        "refazer": refazer(videos),
        "esquecidos": esquecidos(videos),
        "comentario": taxa_de_comentario(videos),
        "cadencia": cadencia(videos),
    }

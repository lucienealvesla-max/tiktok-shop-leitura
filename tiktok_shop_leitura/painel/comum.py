# -*- coding: utf-8 -*-
"""As contas miúdas que metricas.py e conteudo.py usam as duas.

Existe para não haver duas cópias de "o que é uma palavra útil" nem de "como
se tira a mediana". Duas cópias divergem, e divergir aqui faria dois painéis
da mesma tela discordarem sobre os mesmos vídeos — que é o tipo de erro que
ninguém percebe porque cada metade parece certa sozinha.
"""

import re
import statistics
import unicodedata
from datetime import datetime

# Abaixo disto, a taxa é ruído: numerador pequeno demais para dividir.
MINIMO_DE_VIEWS = 100
# Quantos vídeos um grupo precisa ter para virar conclusão na tela.
MINIMO_DE_VIDEOS = 3


def n(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return 0.0


def mediana(valores):
    v = [x for x in valores if x is not None]
    return statistics.median(v) if v else None


def quando(create_time):
    try:
        return datetime.fromtimestamp(int(create_time))
    except (TypeError, ValueError, OSError):
        return None


def texto_do_video(v):
    return (v.get("title") or "") + " " + (v.get("video_description") or "")


def titulo(v, tamanho=60):
    """O título com o que ajuda a RECONHECER o vídeo nos primeiros 60 caracteres.

    As hashtags e as menções saem da frente. O texto dela costuma ser
    "🧩Quebra-cabeça A Noite Estrelada de Van Gogh. #Quebra-cabeça #puzzle
    #hobby #tik", e cortar em 60 no bruto gastava metade do espaço com marcação
    — sobrava um título que não distingue nada de outro título.

    Se sobrar pouca coisa (vídeo cujo texto é só hashtag), volta o bruto: um
    título ruim é melhor que um título vazio.
    """
    bruto = (v.get("title") or v.get("video_description") or "")
    limpo = re.sub(r"[#@]\S+", " ", bruto)
    limpo = re.sub(r"\s+", " ", limpo).strip(" -–—·|.")
    return (limpo if len(limpo) >= 12 else bruto.strip())[:tamanho]


def identidade(v, reserva=None):
    """Como a tela mostra QUAL vídeo é este. Vai junto de todo item de painel.

    POR QUE ISTO EXISTE (07/09/2026). Pergunta dele: "alguma forma melhor de
    saber qual vídeo é qual". O título sozinho não serve e os números provam:
    **92 vídeos dela começam com os mesmos 40 caracteres** ("🖌️✨🖌️ Kit de
    pincéis que não acumulam pr"), 77 com outros, 35 com outros. Ela publica
    15 por dia, muitas vezes o mesmo produto com cortes diferentes — pelo
    título, a tela mandava refazer "um dos 92".

    Três coisas resolvem, e nenhuma custa uma chamada nova: o **link** (que a
    API já mandava e o código jogava fora antes de guardar), a **capa** e a
    **data com a hora**. Duas publicações do mesmo produto no mesmo dia se
    separam pela hora; o resto se separa pela imagem.
    """
    # A RESERVA É O REGISTRO DO CATÁLOGO. Os painéis de trajetória leem as
    # fotografias, e fotografia não guarda capa (nem guardava link, antes de
    # 07/09/2026). Sem a reserva, justamente os painéis mais urgentes - o que
    # está subindo agora - seriam os únicos sem imagem e sem link.
    if reserva:
        v = dict({k: x for k, x in reserva.items() if x is not None},
                 **{k: x for k, x in (v or {}).items() if x is not None})
    publicado = quando(v.get("create_time"))
    return {
        "titulo": titulo(v),
        # O link é o desempate definitivo: um clique e ela está vendo o vídeo.
        "link": v.get("share_url") or None,
        # A capa VENCE, e vence sozinha - reconhecer imagem é instantâneo e ler
        # título é soletrar. Mas o endereço da capa é assinado e expira, então a
        # tela tem que continuar inteira sem ela (ver o `onerror` no dashboard).
        "capa": v.get("cover_image_url") or None,
        "publicado": publicado.strftime("%d/%m/%y %Hh") if publicado else None,
    }


# Palavras que aparecem em tudo e não distinguem nada. Sem tirar, o "ranking de
# assuntos" vira ranking de artigo e preposição.
PARADAS = set("""
a o as os um uma uns umas de do da dos das em no na nos nas por para com sem
que e ou mas se ja nao sim eu voce vc ela ele nos eles elas meu minha seu sua
isso isto esse essa este esta aquele aquela ai la aqui muito mais menos tudo
todo toda todos todas ser sou e esta estao tem tenho ter vai vou foi era como
quando onde qual quais quem porque pq ate entao so agora hoje ontem amanha
dia dias vez vezes coisa coisas gente pra pro nas dos das num numa
""".split())


def sem_acento(texto):
    return "".join(c for c in unicodedata.normalize("NFD", texto or "")
                   if unicodedata.category(c) != "Mn")


def palavras(texto):
    """As palavras úteis de um título/descrição, sem acento e sem hashtag.

    Hashtag sai fora de propósito: aqui o que interessa é a palavra FALADA no
    título. As hashtags têm ranking próprio em conteudo.py — elas são o rótulo
    de assunto que ela mesma escolheu, e misturar as duas coisas esconderia as
    duas.
    """
    limpo = re.sub(r"[#@]\S+", " ", texto or "")
    limpo = sem_acento(limpo).lower()
    return [p for p in re.findall(r"[a-z]{3,}", limpo) if p not in PARADAS]

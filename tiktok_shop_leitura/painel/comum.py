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
    return (v.get("title") or v.get("video_description") or "")[:tamanho]


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

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Dorme até a hora da leitura, lê, e volta a dormir.

POR QUE ISTO EXISTE. A série por vídeo — quanto ganhou ontem, se acelerou, se
um antigo ressuscitou — só existe porque alguém guardou leituras sucessivas. O
TikTok não guarda isso em lugar nenhum. Um dia sem leitura é um buraco que não
se recupera depois; por isso a leitura mudou para uma máquina que fica ligada.

A HORA PADRÃO É 1H DA MANHÃ, e não mais 21h (07/09/2026). O 21h era palpite —
"o número da noite descreve melhor o que o vídeo fez" — e os dados dela
desmentiram: nos últimos 60 dias ela publicou até **23h56**, e o último vídeo
do dia sai depois das 22h em 11 dos 14 últimos dias. A leitura das 21h fechava
o dia com uma a três publicações ainda por vir, que só entravam na fotografia
do dia seguinte já com um dia de vida — justo os vídeos novos, que são os que
o painel da largada existe para pegar. À 1h da manhã o dia anterior está
inteiro, ela não está postando, e a máquina está ociosa.

E ELE SE RECUPERA DE UM REINÍCIO. Antes, um container que subisse depois da
hora marcada simplesmente esperava o dia seguinte, calado. Como o add-on
reinicia por atualização, por watchdog e por falta de memória, dava para
passar dias sem leitura nenhuma com a tela dizendo "lendo sozinho todo dia" —
e cada dia sem leitura é um buraco que não se recupera. Agora, ao subir depois
da hora, ele confere na hora se a leitura de hoje já aconteceu.
"""

import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

PASTA = Path(__file__).resolve().parent
sys.path.insert(0, str(PASTA))


def _hora_escolhida(padrao=1):
    """A hora da leitura, da opcao do add-on. Nunca levanta, nunca vira 0 sozinha.

    String vazia e o que uma opcao ausente entrega, e `int("")` derrubaria o
    relogio no arranque - o container morreria em laco e a leitura nunca mais
    aconteceria. Valor fora de 0-23 tambem cai no padrao: e melhor ler na hora
    errada do que nao ler nunca.
    """
    try:
        h = int(str(os.environ.get("TIKTOK_SHOP_HORA", "")).strip())
    except (TypeError, ValueError):
        return padrao
    return h if 0 <= h <= 23 else padrao


HORA = _hora_escolhida()

# O Pi 4 nao tem RTC (relogio de tempo real): ao subir o container, o horario
# pode estar errado ate o NTP acertar. E time.sleep() e MONOTONICO no Linux -
# uma correcao de relogio no meio de um sono longo nao muda quando ele acorda.
# Dormir em pedacos e reavaliar datetime.now() a cada volta cobre os dois
# casos (relogio atrasado ou adiantado) sem esperar o sono inteiro escoar.
# Seguro: puxar_diario ja tem trava por dia e por perfil, entao acordar cedo
# demais nao gasta chamada nenhuma - so faz o laco checar de novo.
PEDACO_MAXIMO = 15 * 60


def pedaco_de_sono(segundos_restantes, maximo=PEDACO_MAXIMO):
    """Quanto dormir desta vez: nunca mais que o maximo, nunca negativo."""
    return max(0.0, min(segundos_restantes, maximo))


def proxima_leitura(agora, hora=HORA):
    """O próximo instante de leitura, estritamente DEPOIS de `agora`.

    Em cima da hora conta como já passada: às 21:00:00 a leitura de hoje acabou
    de rodar, e marcar para agora faria o laço girar em falso.
    """
    alvo = agora.replace(hour=hora, minute=0, second=0, microsecond=0)
    if alvo <= agora:
        alvo += timedelta(days=1)
    return alvo


def segundos_ate(agora, hora=HORA):
    return (proxima_leitura(agora, hora) - agora).total_seconds()


def main():
    import puxar_diario
    print("relogio da leitura no ar - lendo todo dia as %dh" % HORA)

    # A RECUPERACAO DO REINICIO. `puxar_diario` confere por perfil se a leitura
    # de hoje ja existe e esta completa, entao subir dez vezes num dia nao gasta
    # dez leituras - ele para sozinho depois de tres tentativas incompletas.
    if datetime.now().hour >= HORA:
        print("subi depois das %dh - conferindo a leitura de hoje" % HORA)
        try:
            puxar_diario.main()
        except Exception as e:
            print("a leitura de recuperacao falhou: %s" % e)

    while True:
        agora = datetime.now()
        alvo = proxima_leitura(agora)
        # O absoluto ao lado do relativo: a spec pede "21h LOCAIS", mas nada
        # no log revela o fuso do container. So o relativo ("em 623 min")
        # esconde tanto o fuso errado quanto o relogio sem hora certa; o
        # absoluto deixa isso obvio de olhar, em vez de invisivel.
        print("proxima leitura em %.0f min (as %s)" %
              ((alvo - agora).total_seconds() / 60,
               alvo.strftime("%Y-%m-%d %Hh%M")))
        restante = (alvo - agora).total_seconds()
        while restante > 0:
            time.sleep(pedaco_de_sono(restante))
            restante = (alvo - datetime.now()).total_seconds()
        try:
            puxar_diario.main()
        except Exception as e:
            # UM DIA PERDIDO NÃO PODE DERRUBAR O RELÓGIO. Se o laço morrer,
            # perdem-se todos os dias seguintes em vez de um só.
            print("a leitura de hoje falhou: %s" % e)


if __name__ == "__main__":
    main()

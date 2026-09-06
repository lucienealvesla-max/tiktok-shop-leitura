#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Dorme até as 21h, lê, e volta a dormir.

POR QUE ISTO EXISTE. A série por vídeo — quanto ganhou ontem, se acelerou, se
um antigo ressuscitou — só existe porque alguém guardou leituras sucessivas. O
TikTok não guarda isso em lugar nenhum. Um dia sem leitura é um buraco que não
se recupera depois; por isso a leitura mudou para uma máquina que fica ligada.

Por que 21h: de manhã ela está começando o dia, e o número da noite descreve
melhor o que o vídeo fez.
"""

import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

PASTA = Path(__file__).resolve().parent
sys.path.insert(0, str(PASTA))

HORA = 21

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

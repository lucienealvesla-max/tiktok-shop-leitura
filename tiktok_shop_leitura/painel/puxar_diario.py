# -*- coding: utf-8 -*-
"""Puxa a leitura do dia na API do TikTok e guarda a fotografia.

Rodado pela tarefa agendada do Windows, uma vez por dia. Também dá para rodar
na mão:  python painel/puxar_diario.py

POR QUE UMA VEZ POR DIA, TODO DIA. O TikTok mostra o número acumulado de agora;
ele nunca mostra a trajetória. A série por vídeo — quanto ganhou ontem, se
acelerou, se um vídeo antigo ressuscitou — só existe porque alguém guardou
leituras sucessivas. Um dia sem leitura é um buraco que não se recupera depois.

SAI QUIETO quando não há o que fazer (sem configuração, sem token, sem rede).
Tarefa agendada que falha barulhento no boot vira janela de erro na cara dela
sem motivo — e o remédio nesses casos é ela conectar, não ver um alerta.
"""

import sys
from datetime import datetime
from pathlib import Path

PASTA = Path(__file__).resolve().parent
sys.path.insert(0, str(PASTA))


def main():
    try:
        import tiktok
    except Exception as e:
        print("nao consegui carregar o tiktok.py: %s" % e)
        return 0

    if not tiktok.configurado():
        print("conexao com o TikTok nao configurada - nada a fazer")
        return 0

    contas = tiktok.contas()
    if not contas:
        print("nenhum perfil conectado - nada a fazer")
        return 0

    # Onde o CSV vai parar. Resolvido UMA vez, fora do laco.
    pasta = None
    try:
        import painel
        pasta = painel.pasta_de_dados()
    except Exception:
        pass

    hoje = datetime.now().strftime("%Y-%m-%d")
    for conta in contas:
        # UM PERFIL DE CADA VEZ, e o de hoje conferido POR PERFIL. Conferir uma
        # vez so faria o segundo perfil ser pulado sempre que o primeiro ja
        # tivesse lido - e ele nunca teria historico nenhum.
        pasta_da_conta = tiktok.pasta_da_conta(conta["open_id"])
        if (pasta_da_conta / "fotos" / (hoje + ".json")).is_file():
            print("%s: ja existe a leitura de %s" % (conta["nome"], hoje))
            continue

        try:
            ok, dados = tiktok.puxar_videos(conta["open_id"])
        except Exception as e:
            print("%s: nao consegui ler: %s" % (conta["nome"], e))
            continue          # um perfil que falha nao pode levar os outros
        videos = dados.get("videos") or []
        if not videos:
            print("%s: nao vieram videos: %s"
                  % (conta["nome"], dados.get("erro", "sem motivo")))
            continue

        guardou, recado = tiktok.guardar_foto(conta["open_id"], videos)
        print("%s: %s" % (conta["nome"],
                          recado if guardou else "nao consegui guardar: " + recado))

        # A cópia em CSV na pasta de dados continua sendo feita: é o que mantém
        # o caminho da planilha vivo se a API fechar um dia.
        try:
            if pasta is not None:
                tiktok.gravar_na_pasta_de_dados(
                    tiktok.fotografia_de_hoje(conta["open_id"]) or videos,
                    pasta, conta["nome"])
        except Exception:
            pass      # a fotografia é o que importa; o CSV é conveniência
    return 0


if __name__ == "__main__":
    sys.exit(main())

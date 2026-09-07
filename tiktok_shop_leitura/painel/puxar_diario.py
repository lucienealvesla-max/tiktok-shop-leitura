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


# Quantas vezes por dia a API pode ser consultada por conta. Tres, e nao uma:
# a leitura vem pela metade com frequencia (em 06/09/2026 vieram 958 de 2.352
# videos), e a segunda tentativa costuma trazer o que faltou porque a uniao por
# id soma as duas. Tres, e nao "ate completar": conta pode ter video apagado,
# e ai a leitura NUNCA cobre o catalogo inteiro - a condicao de parada seria
# falsa para sempre, e o laco viraria um martelo em cima da API.
MAXIMO_DE_LEITURAS_POR_DIA = 3
# Abaixo disto a leitura conta como incompleta e vale insistir.
COBERTURA_BOA = 0.95


def _falta_ler(pasta_da_conta, hoje, nome):
    """Esta conta ainda precisa ser lida hoje? Diz no log por que sim ou nao."""
    foto = pasta_da_conta / "fotos" / (hoje + ".json")
    if not foto.is_file():
        return True

    import json as _json
    try:
        d = _json.loads(foto.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return True                     # arquivo ilegivel conta como sem leitura

    leituras = int(d.get("leituras") or 1)
    lidos = len(d.get("videos") or [])
    try:
        import catalogo
        conhecidos = len(catalogo.ler(pasta_da_conta) or {})
    except Exception:
        conhecidos = 0

    if conhecidos and lidos < conhecidos * COBERTURA_BOA:
        if leituras >= MAXIMO_DE_LEITURAS_POR_DIA:
            print("%s: a leitura de %s trouxe %d de %d videos conhecidos e ja "
                  "foram %d tentativas hoje - fica assim, e o catalogo cobre o "
                  "resto" % (nome, hoje, lidos, conhecidos, leituras))
            return False
        print("%s: a leitura de %s trouxe so %d de %d videos conhecidos "
              "(tentativa %d) - vou tentar completar"
              % (nome, hoje, lidos, conhecidos, leituras + 1))
        return True

    print("%s: ja existe a leitura de %s (%d videos)" % (nome, hoje, lidos))
    return False


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
        if not _falta_ler(pasta_da_conta, hoje, conta["nome"]):
            continue

        try:
            ok, dados = tiktok.puxar_videos(conta["open_id"])
        except Exception as e:
            print("%s: nao consegui ler: %s" % (conta["nome"], e))
            continue          # um perfil que falha nao pode levar os outros
        videos = dados.get("videos") or []
        if not videos:
            print("%s: nao vieram videos: %s"
                  % (conta["nome"], tiktok.motivo_de_lista_vazia(dados)))
            continue
        # POR QUE A LEITURA PAROU, no log, sempre. A investigacao de 07/09/2026
        # comecou por arquivo no disco porque isto aqui nao existia: a leitura
        # encolhia e o log dizia so quantos videos vieram, nunca que a API
        # tinha recusado a pagina seguinte.
        if dados.get("parcial"):
            print("%s: LEITURA PARCIAL - %s" % (conta["nome"],
                                                dados.get("motivo") or "sem motivo"))

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

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""O servidor de leitura — a parte do painel que roda no Raspberry.

POR QUE ELE EXISTE, e não o painel.py. O painel.py tem quase 3.000 linhas de ffmpeg,
preparo de clipe, montagem e rotas POST que gravam arquivo. Nada disso tem
função no Raspberry, e este servidor fica atrás de um túnel para a internet:
quanto menos porta, melhor. Aqui existem TRÊS rotas e nada além.

O QUE ELE NÃO FAZ: não fala com o Google Drive, não chama ffmpeg, não escreve
vídeo. A metade "produção" do dashboard (qual gancho rende mais) precisa dos
nomes dos montados e ficou para a fase 2.
"""

import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

PASTA = Path(__file__).resolve().parent
sys.path.insert(0, str(PASTA))

import metricas
import tiktok

def _versao():
    """De onde vem a versao carimbada no rodape da tela.

    O caminho preferido e o build-arg do Dockerfile (ENV TIKTOK_SHOP_VERSAO).
    Mas o Supervisor do Home Assistant nao tem campo de UI pra --build-arg
    arbitrario, e os arquivos chegam por copia manual (Samba/SSH) - entao na
    pratica essa variavel fica presa em "desconhecida" pra sempre. O arquivo
    VERSAO ao lado do codigo e o fallback real: o README manda escrever o
    commit ali na hora de copiar. Ler esse arquivo NUNCA pode derrubar o
    servidor - sem ele, ou com ele ilegivel, a versao so fica "desconhecida",
    que e o mesmo estado de hoje.
    """
    env = os.environ.get("TIKTOK_SHOP_VERSAO")
    if env and env != "desconhecida":
        return env
    try:
        texto = (PASTA / "VERSAO").read_text(encoding="utf-8").strip()
        return texto or "desconhecida"
    except Exception:
        return "desconhecida"


VERSAO = _versao()


def caminho_pedido(caminho, prefixo):
    """Desconta o prefixo que o Ingress do Home Assistant põe na frente.

    O HA serve o add-on sob /api/hassio_ingress/<token>/ e manda o prefixo no
    cabeçalho X-Ingress-Path. O dashboard.html usa URLs RELATIVAS, então os
    pedidos chegam com esse prefixo colado. Prefixo que não bate é ignorado:
    cabeçalho de outro pedido não pode reescrever este.

    O cabeçalho vem do PEDIDO, então é hostil por definição: alguém pode mandar
    X-Ingress-Path igual ao próprio caminho. Sem cuidado, `resto` fica vazio e
    NÃO começa com "/" — fabricar uma barra ali ("/" + "") colapsaria qualquer
    caminho em "/", furando a lista fechada de rotas. Por isso só descontamos
    quando o resto JÁ começa com "/"; caso contrário o caminho original segue
    intacto e cai no 404 de sempre.
    """
    if prefixo and caminho.startswith(prefixo):
        resto = caminho[len(prefixo):]
        if resto.startswith("/"):
            return resto
    return caminho


def estado_daqui():
    """O que a tela precisa saber sobre esta máquina.

    dono_da_leitura é SEMPRE verdadeiro aqui: quem roda este servidor é o dono
    do token, por definição. É o que faz o botão "Ler agora" aparecer nesta
    tela e virar recado na do PC dela.

    leitura_diaria é SEMPRE verdadeiro aqui: é o run.sh quem sobe o relógio,
    junto do servidor, sem escolha - não existe modo "desligar e continuar
    rodando o add-on". E agendador é SEMPRE falso: não existe Agendador de
    Tarefas do Windows aqui pra ligar/desligar, então o botão que chama
    api/tiktok/diario/ligar (rota que só existe no painel.py) não pode
    aparecer - um botão que dá 404 é pior que não ter botão. O painel dela
    nunca manda essa chave, então o dashboard.html continua distinguindo os
    dois lugares só por ela ficar ausente ou não.
    """
    # A HORA VEM DAQUI, e nao de um numero escrito na pagina. Ela e ajustavel
    # na tela do add-on desde 1.3.0, e uma pagina dizendo "lendo as 21h" com o
    # relogio marcado para 1h e pior do que nao dizer hora nenhuma.
    import relogio_leitura
    base = {"dono_da_leitura": True, "leitura_em": None, "versao": VERSAO,
            "leitura_diaria": True, "agendador": False,
            "hora_da_leitura": relogio_leitura.HORA}
    try:
        base.update(tiktok.estado())
    except Exception:
        pass
    base["dono_da_leitura"] = True     # nunca sobrescrito pelo estado do módulo
    return base


class Alca(BaseHTTPRequestHandler):

    server_version = "LeituraTikTok/1.0"

    def log_message(self, formato, *args):
        # O log do add-on aparece no painel do HA; sem isto ele vira ruído.
        sys.stderr.write("%s - %s\n" % (self.address_string(), formato % args))

    def caminho(self):
        return caminho_pedido(urlparse(self.path).path,
                              self.headers.get("X-Ingress-Path"))

    def json(self, dados, status=200):
        corpo = json.dumps(dados, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(corpo)))
        self.end_headers()
        self.wfile.write(corpo)

    def do_GET(self):
        c = self.caminho()
        if c in ("/", "/dashboard.html"):
            return self.pagina()
        if c == "/api/desempenho":
            conta = (parse_qs(urlparse(self.path).query).get("conta") or [""])[0]
            try:
                d = metricas.painel_de_desempenho(
                    tiktok, conta or None, estado_daqui)
            except Exception as e:
                d = {"ok": False, "erro": str(e)}
            return self.json(d)
        # LISTA FECHADA. Tudo que não está acima não existe.
        return self.json({"erro": "nao existe esse endereco"}, 404)

    def do_POST(self):
        if self.caminho() != "/api/tiktok/puxar":
            return self.json({"erro": "nao existe esse endereco"}, 404)
        return self.json(self.ler_agora())

    def pagina(self):
        try:
            corpo = (PASTA / "dashboard.html").read_bytes()
        except Exception as e:
            return self.json({"erro": "dashboard.html nao encontrado: %s" % e}, 500)
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(corpo)))
        self.end_headers()
        self.wfile.write(corpo)

    def ler_agora(self):
        """LÊ TODOS OS PERFIS, não só o que está na tela.

        A fotografia é a única coisa daqui que não se recupera: se a leitura
        seguisse o seletor, o perfil que ela não estivesse olhando perderia o
        dia — calado, e sem volta. Um perfil que falha não impede os outros.
        """
        # configurado() e contas() no MESMO try: os dois falam com o disco, e
        # este servidor fica atrás de um túnel para a internet — nenhum dos
        # dois pode escapar como exceção crua, só como JSON de erro.
        try:
            if not tiktok.configurado():
                return {"ok": False, "erro": "conexão com o TikTok não configurada"}
            contas = tiktok.contas()
        except Exception as e:
            return {"ok": False, "erro": str(e)}
        perfis, algum = [], False
        for conta in contas:
            linha = {"conta": conta["open_id"], "nome": conta["nome"]}
            try:
                ok, d = tiktok.puxar_videos(conta["open_id"])
                videos = (d or {}).get("videos") or []
                if not videos:
                    linha["erro"] = (d or {}).get("erro", "não vieram vídeos")
                else:
                    guardou, recado = tiktok.guardar_foto(
                        conta["open_id"], videos)
                    # LEITURA PELA METADE TEM QUE APARECER NA TELA. Foi este o
                    # buraco de 06/09/2026: a leitura trouxe 958 dos 2.352
                    # vídeos, o botão disse "pronto", e só três dias depois
                    # alguém reparou que o vídeo de 2,1 milhão tinha sumido.
                    if (d or {}).get("parcial"):
                        recado += " — VEIO PELA METADE: " + str(
                            d.get("motivo") or d.get("erro") or "sem motivo")
                    linha["recado"] = recado
                    algum = algum or guardou
            except Exception as e:
                linha["erro"] = str(e)
            perfis.append(linha)
        return {"ok": algum, "perfis": perfis,
                "recado": "; ".join(
                    "%s: %s" % (p["nome"], p.get("recado") or p.get("erro"))
                    for p in perfis)}


def Servidor(porta=8099):
    """Porta 0 pede uma livre ao sistema — é como o teste sobe sem brigar com
    nada. NUNCA usar a 8777 aqui: aquela é a do painel dela."""
    return ThreadingHTTPServer(("0.0.0.0", porta), Alca)


def main():
    porta = int(os.environ.get("TIKTOK_SHOP_PORTA") or 8099)
    s = Servidor(porta)
    print("servidor de leitura no ar na porta %d (versao %s)" % (porta, VERSAO))
    print("dados em %s" % tiktok.BASE)
    s.serve_forever()


if __name__ == "__main__":
    main()

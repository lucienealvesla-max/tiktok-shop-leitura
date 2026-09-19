# -*- coding: utf-8 -*-
"""O painel pronto no disco. A tela lê um arquivo; ninguém calcula ao abrir.

POR QUE ISTO EXISTE (18/09/2026). Abrir a tela levava **44 segundos** no
Raspberry: cada `GET /api/desempenho` recalculava tudo sobre 2.430 vídeos × 15
fotografias. O log estava cheio de `BrokenPipeError` — o navegador desistia
antes de o servidor terminar. E o resultado era o MESMO a cada abertura, porque
os dados só mudam uma vez por dia, na leitura da 1h.

O QUE ELE FAZ: calcula `metricas.calcular()` uma vez e grava em
`<pasta da conta>/desempenho.json`, com uma CHAVE que diz de que dados o
cálculo saiu. Enquanto a chave bater, a tela recebe o arquivo (~80 KB, menos de
um segundo). Quando os dados mudam, a chave muda e o próximo pedido recalcula —
mas quem pede o recálculo é o relógio, logo depois da leitura da 1h, e o botão
"Ler agora", logo depois de ler; a tela só calcula se chegar antes deles (a
primeira abertura depois de uma atualização, por exemplo).

O QUE ENTRA NA CHAVE: a versão do add-on (cálculo novo, arquivo novo), o nome
e a hora de gravação da última fotografia (leitura nova, arquivo novo), quantas
fotografias há, e a hora do `catalogo.json` (a capa e o link saem dele). O dia
de hoje NÃO entra: "idade em dias" fica até um dia atrasada entre a meia-noite
e a leitura da 1h, e isso é barato demais para pagar com um cálculo de uns 4 s
na primeira abertura de cada manhã.

DUAS ABAS ABRINDO JUNTAS NÃO CALCULAM DUAS VEZES: uma trava por conta faz a
segunda esperar a primeira e ler o arquivo que ela gravou.

O ARQUIVO PODE SER APAGADO A QUALQUER MOMENTO: ele se refaz das fotografias. A
fotografia é a única coisa aqui que não se recupera, e este arquivo nunca a
toca.
"""

import json
import sys
import threading
import time
from pathlib import Path

PASTA = Path(__file__).resolve().parent
sys.path.insert(0, str(PASTA))

import metricas

ARQUIVO = "desempenho.json"

_travas = {}
_trava_das_travas = threading.Lock()


def _trava(escolhida):
    with _trava_das_travas:
        if escolhida not in _travas:
            _travas[escolhida] = threading.Lock()
        return _travas[escolhida]


def _versao():
    try:
        return (PASTA / "VERSAO").read_text(encoding="utf-8").strip() or "?"
    except OSError:
        return "?"


def _mtime(p):
    try:
        return str(int(Path(p).stat().st_mtime))
    except OSError:
        return "-"


def chave(tk, escolhida):
    """De que dados o cálculo saiu. Muda → o arquivo gravado não vale mais."""
    pasta = tk.pasta_da_conta(escolhida)
    fotos = sorted((pasta / "fotos").glob("*.json")) if (pasta / "fotos").is_dir() else []
    ultima = fotos[-1] if fotos else None
    return "|".join([
        _versao(),
        str(len(fotos)),
        ultima.name if ultima else "-",
        _mtime(ultima) if ultima else "-",
        _mtime(pasta / "catalogo.json"),
    ])


def _caminho(tk, escolhida):
    return tk.pasta_da_conta(escolhida) / ARQUIVO


def ler(tk, escolhida):
    """O painel gravado, se ainda vale. None se não há ou se os dados mudaram."""
    try:
        d = json.loads(_caminho(tk, escolhida).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if d.get("chave") != chave(tk, escolhida):
        return None
    return d.get("painel")


def _gravar(tk, escolhida, chave_, painel):
    alvo = _caminho(tk, escolhida)
    # Arquivo temporário e troca, como o catálogo: uma queda no meio da escrita
    # não pode deixar um JSON pela metade para a tela engasgar.
    temp = alvo.with_suffix(".json.novo")
    temp.write_text(json.dumps({"chave": chave_, "gravado_em": int(time.time()),
                                "painel": painel}, ensure_ascii=False),
                    encoding="utf-8")
    temp.replace(alvo)


def preparar(tk, escolhida, motivo=""):
    """Calcula e grava o painel de uma conta, se os dados mudaram. Devolve-o.

    Uma conta de cada vez: o segundo pedido pela mesma conta espera o primeiro
    e encontra o arquivo pronto. `motivo` vai para o log, para se saber quem
    pediu o cálculo — "depois da leitura da 1h", "ao abrir a tela".
    """
    with _trava(escolhida):
        pronto = ler(tk, escolhida)
        if pronto is not None:
            return pronto
        chave_ = chave(tk, escolhida)
        t0 = time.time()
        painel = metricas.calcular(tk, escolhida)
        levou = time.time() - t0
        painel["calculado_em"] = int(time.time())
        painel["levou_s"] = round(levou, 1)
        # Conta sem fotografia não ganha arquivo: não há o que guardar, e criar
        # um JSON numa pasta que só tem a ficha confundiria quem olhar o disco.
        if painel.get("tem_dados"):
            try:
                _gravar(tk, escolhida, chave_, painel)
            except OSError as e:
                print("painel de %s calculado mas nao gravado: %s" % (escolhida, e))
        print("painel de %s pronto em %.1fs%s" % (escolhida, levou, motivo))
        return painel


def preparar_todas(tk, motivo=""):
    """Todas as contas conectadas. Uma que falhe não impede as outras."""
    try:
        contas = tk.contas()
    except Exception as e:
        print("nao consegui listar as contas para preparar o painel: %s" % e)
        return
    for c in contas:
        try:
            preparar(tk, c["open_id"], motivo)
        except Exception as e:
            print("painel de %s falhou: %s" % (c.get("nome") or c["open_id"], e))


def desempenho(tk, conta=None, estado=None):
    """O que o servidor responde em GET /api/desempenho.

    A mesma forma de `metricas.painel_de_desempenho`, mas o painel vem do
    disco. O estado (hora da leitura, contas, versão) é montado agora, sempre:
    é barato e mudaria de errado se fosse gravado junto.
    """
    escolhida, erro = metricas.escolher(tk, conta)
    if erro:
        return {"ok": False, "erro": erro}
    if escolhida is None:
        return {"ok": True, "tem_dados": False, "conta": None,
                "tiktok": metricas.estado_de(estado)}
    try:
        painel = ler(tk, escolhida)
        if painel is None:
            painel = preparar(tk, escolhida, " (calculado ao abrir a tela)")
    except Exception as e:
        return {"ok": False, "erro": str(e)}
    d = dict(painel)
    d["ok"] = True
    d["conta"] = escolhida
    d["tiktok"] = metricas.estado_de(estado)
    return d

# -*- coding: utf-8 -*-
"""Os painéis que o app do TikTok não tem, feitos com o que a Display API dá.

POR QUE ISTO EXISTE (31/08/2026). Pedido dele: *"dashboards que não existam na
interface do TikTok e que sejam de suma importância para creators"*.

A IDEIA QUE SUSTENTA O ARQUIVO INTEIRO: **o TikTok mostra o número de agora; ele
nunca mostra a trajetória.** No app ela vê "12.400 visualizações". Não vê quantas
o vídeo ganhou ontem, se está acelerando ou parando, nem se um vídeo de três
semanas voltou a crescer. A API também devolve só o acumulado do momento — a
dimensão de tempo **não existe em lugar nenhum** até alguém guardar leituras
sucessivas. É o que `tiktok.guardar_foto()` faz, uma por dia.

Metade das contas aqui vive dessa série e só ganha valor com os dias passando; a
outra metade funciona já na primeira leitura. As duas estão marcadas.

DUAS REGRAS QUE VALEM PARA TUDO NESTE ARQUIVO:

1. **Mediana, não média.** No TikTok um vídeo viral distorce qualquer média: um
   de 200 mil entre nove de 800 faz a "média" dizer 20 mil, número que não
   descreve nenhum vídeo dela. A mediana descreve o dia normal.
2. **Piso de amostra.** Toda comparação diz de quantos vídeos ela saiu. Um vídeo
   com 12 visualizações e 1 compartilhamento tem "8% de taxa" e não significa
   nada. Sem o piso, o ranking enche de ruído e aponta pro lugar errado.
"""

import statistics
from datetime import datetime

# Abaixo disto, a taxa é ruído: numerador pequeno demais para dividir.
MINIMO_DE_VIEWS = 100
# Quantos vídeos um grupo precisa ter para virar conclusão na tela.
MINIMO_DE_VIDEOS = 3


# ----------------------------------------------------------------- utilidades

def _n(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return 0.0


def _mediana(valores):
    v = [x for x in valores if x is not None]
    return statistics.median(v) if v else None


def _quando(create_time):
    try:
        return datetime.fromtimestamp(int(create_time))
    except (TypeError, ValueError, OSError):
        return None


def ultimos_videos(fotos):
    """A leitura mais recente: a lista de vídeos como está hoje."""
    if not fotos:
        return []
    return fotos[-1].get("videos") or []


def serie_por_video(fotos):
    """{id: [(dia, views), ...]} em ordem, uma entrada por fotografia."""
    serie = {}
    for f in fotos:
        dia = f.get("dia")
        for v in f.get("videos") or []:
            if not v.get("id"):
                continue
            serie.setdefault(v["id"], []).append((dia, _n(v.get("view_count"))))
    for k in serie:
        serie[k].sort(key=lambda x: x[0])
    return serie


def _ganhos_diarios(pontos):
    """As diferenças entre leituras consecutivas, nunca negativas.

    Negativo aparece quando o TikTok recalcula ou o vídeo sai do ar por um dia.
    Deixar passar viraria "ganho de -3.000 views" na tela, que assusta sem
    motivo; zerar é a leitura honesta - naquele intervalo não houve ganho.
    """
    fora = []
    for i in range(1, len(pontos)):
        fora.append((pontos[i][0], max(0.0, pontos[i][1] - pontos[i - 1][1])))
    return fora


# =========================================================================
#  PRECISAM DE HISTÓRICO
# =========================================================================

def acelerando(fotos, quantos=10):
    """O que está pegando fogo AGORA: views ganhas na última leitura e em 7.

    É a pergunta mais urgente de quem posta todo dia, e o app não responde: lá
    tudo é acumulado desde a publicação. Um vídeo com 50 mil views pode estar
    parado há duas semanas, e um de 3 mil pode ter ganhado 2 mil ontem - na tela
    do TikTok os dois parecem o que não são.
    """
    if len(fotos) < 2:
        return {"pronto": False, "faltam": 2 - len(fotos), "itens": []}

    serie = serie_por_video(fotos)
    atuais = {v.get("id"): v for v in ultimos_videos(fotos)}
    itens = []
    for vid, pontos in serie.items():
        ganhos = _ganhos_diarios(pontos)
        if not ganhos:
            continue
        v = atuais.get(vid) or {}
        itens.append({
            "id": vid,
            "titulo": (v.get("title") or v.get("video_description") or "")[:60],
            "views": _n(v.get("view_count")),
            "ganho_ultimo": ganhos[-1][1],
            "ganho_7d": sum(g for _, g in ganhos[-7:]),
        })
    itens.sort(key=lambda x: -x["ganho_ultimo"])
    return {"pronto": True, "itens": itens[:quantos]}


def ressurreicoes(fotos, idade_minima=14, fator=3.0, piso=50):
    """Vídeo velho que voltou a crescer.

    POR QUE ISTO IMPORTA MAIS DO QUE PARECE: o TikTok revive vídeo antigo o tempo
    todo, e **não avisa**. Sem alguém olhando, ela descobre semanas depois - ou
    nunca. Sabendo no dia, dá pra reagir enquanto o vídeo ainda está subindo:
    fazer uma continuação, responder comentário, empurrar o link.

    A régua é o ritmo do PRÓPRIO vídeo, não um número fixo: 500 views num dia é
    ressurreição para um vídeo parado e rotina para um que acabou de sair.
    """
    if len(fotos) < 4:
        return {"pronto": False, "faltam": 4 - len(fotos), "itens": []}

    serie = serie_por_video(fotos)
    atuais = {v.get("id"): v for v in ultimos_videos(fotos)}
    agora = datetime.now()
    itens = []
    for vid, pontos in serie.items():
        ganhos = _ganhos_diarios(pontos)
        if len(ganhos) < 3:
            continue
        v = atuais.get(vid) or {}
        nasceu = _quando(v.get("create_time"))
        if not nasceu or (agora - nasceu).days < idade_minima:
            continue
        ultimo = ganhos[-1][1]
        antes = _mediana([g for _, g in ganhos[:-1]]) or 0.0
        if ultimo < piso:
            continue
        # Vídeo que estava parado de vez (mediana 0) e ganhou acima do piso já é
        # ressurreição: não dá pra multiplicar por zero e exigir um fator.
        if antes == 0 or ultimo >= antes * fator:
            itens.append({
                "id": vid,
                "titulo": (v.get("title") or v.get("video_description") or "")[:60],
                "views": _n(v.get("view_count")),
                "ganho_ultimo": ultimo,
                "ritmo_anterior": antes,
                "idade_dias": (agora - nasceu).days,
            })
    itens.sort(key=lambda x: -x["ganho_ultimo"])
    return {"pronto": True, "itens": itens}


def meia_vida(fotos, alvo=0.8):
    """Quantos dias o vídeo leva pra juntar 80% das views que tem hoje.

    Responde "por quanto tempo vale continuar empurrando um vídeo". Se a meia
    vida dela é de 2 dias, insistir no quarto dia é gastar energia no lugar
    errado; se é de 10, parar no terceiro é desistir cedo.

    Só entram vídeos que já foram vistos desde cedo pela série - de outro modo a
    conta mede quando a gente começou a olhar, não quando o vídeo cresceu.
    """
    if len(fotos) < 3:
        return {"pronto": False, "faltam": 3 - len(fotos), "dias": None, "amostra": 0}

    serie = serie_por_video(fotos)
    atuais = {v.get("id"): v for v in ultimos_videos(fotos)}
    dias = []
    for vid, pontos in serie.items():
        if len(pontos) < 3:
            continue
        v = atuais.get(vid) or {}
        nasceu = _quando(v.get("create_time"))
        primeiro = None
        try:
            primeiro = datetime.strptime(pontos[0][0], "%Y-%m-%d")
        except (ValueError, TypeError):
            continue
        # A primeira leitura tem que ser perto do nascimento do vídeo, senão a
        # série começa no meio da vida dele e a conta mente pra menos.
        if not nasceu or (primeiro - nasceu).days > 2:
            continue
        total = pontos[-1][1]
        if total < MINIMO_DE_VIEWS:
            continue
        for dia, views in pontos:
            if views >= total * alvo:
                try:
                    dias.append((datetime.strptime(dia, "%Y-%m-%d") - primeiro).days)
                except (ValueError, TypeError):
                    pass
                break
    return {"pronto": True, "dias": _mediana(dias), "amostra": len(dias)}


# =========================================================================
#  FUNCIONAM JÁ NA PRIMEIRA LEITURA
# =========================================================================

def contra_a_mediana(videos, quantos=10):
    """Cada vídeo comparado à mediana DELA, não a número genérico da internet.

    O app mostra "3.200 visualizações" e pronto. Ele não diz se 3.200 é bom para
    esta conta. Conselho de internet ("o bom é 10% de engajamento") é sobre uma
    conta média que não existe. A régua útil é a própria história dela.
    """
    vistos = [_n(v.get("view_count")) for v in videos]
    med = _mediana(vistos)
    if not med:
        return {"mediana": None, "acima": [], "abaixo": []}
    ordenados = sorted(videos, key=lambda v: -_n(v.get("view_count")))

    def linha(v):
        vw = _n(v.get("view_count"))
        return {"titulo": (v.get("title") or v.get("video_description") or "")[:60],
                "views": vw, "vezes_a_mediana": round(vw / med, 2) if med else None}

    return {"mediana": med, "amostra": len(videos),
            "acima": [linha(v) for v in ordenados[:quantos]],
            "abaixo": [linha(v) for v in ordenados[-quantos:][::-1]]}


def taxa_de_compartilhamento(videos, quantos=10):
    """Compartilhamentos por visualização, ranqueado.

    O app só mostra o total bruto, onde o vídeo grande sempre ganha - e por isso
    o ranking dele não ensina nada. A TAXA é diferente: é o sinal que mais anda
    junto com alcance, porque compartilhar é o que leva o vídeo para fora da
    audiência atual. Um vídeo pequeno com taxa alta é um vídeo que merecia mais
    alcance do que teve.

    O piso de %d views existe pra taxa não virar ruído: 1 compartilhamento em 12
    views daria 8%%, e isso não é sinal de nada.
    """ % MINIMO_DE_VIEWS
    itens = []
    for v in videos:
        vw = _n(v.get("view_count"))
        if vw < MINIMO_DE_VIEWS:
            continue
        itens.append({
            "titulo": (v.get("title") or v.get("video_description") or "")[:60],
            "views": vw,
            "compartilhamentos": _n(v.get("share_count")),
            "taxa": round(_n(v.get("share_count")) / vw * 100, 2),
        })
    itens.sort(key=lambda x: -x["taxa"])
    return {"itens": itens[:quantos], "amostra": len(itens),
            "mediana": _mediana([i["taxa"] for i in itens])}


def _agrupar(videos, chave, rotulo):
    """Agrupa por uma chave e devolve a mediana de views de cada grupo."""
    grupos = {}
    for v in videos:
        k = chave(v)
        if k is None:
            continue
        grupos.setdefault(k, []).append(_n(v.get("view_count")))
    fora = []
    for k, vistos in grupos.items():
        if len(vistos) < MINIMO_DE_VIDEOS:
            continue      # grupo pequeno demais não vira conclusão
        fora.append({"rotulo": rotulo(k), "chave": k,
                     "mediana": _mediana(vistos), "videos": len(vistos)})
    fora.sort(key=lambda x: -(x["mediana"] or 0))
    return fora


DIAS = ["segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo"]


def melhor_horario(videos):
    """Hora e dia da semana que mais renderam, nos dados DELA.

    O TikTok Studio mostra "melhor horário" para algumas contas e para outras
    não, e quando mostra é baseado em quando a audiência está online - não em
    quanto os vídeos dela renderam de fato. Aqui é a conta feita com a história
    dela, e a tela diz de quantos vídeos cada faixa saiu.
    """
    por_hora = _agrupar(videos,
                        lambda v: (_quando(v.get("create_time")).hour
                                   if _quando(v.get("create_time")) else None),
                        lambda h: "%02dh" % h)
    por_dia = _agrupar(videos,
                       lambda v: (_quando(v.get("create_time")).weekday()
                                  if _quando(v.get("create_time")) else None),
                       lambda d: DIAS[d])
    return {"por_hora": por_hora, "por_dia": por_dia}


FAIXAS = [(0, 15, "até 15s"), (15, 30, "15-30s"), (30, 45, "30-45s"),
          (45, 60, "45-60s"), (60, 90, "60-90s"), (90, 10 ** 6, "mais de 90s")]


def duracao_que_rende(videos):
    """Faixa de duração × views. Responde "que tamanho funciona no meu perfil".

    Pergunta que todo creator faz e que a internet responde com regra geral. A
    resposta real muda de conta para conta, e só os dados dela sabem.
    """
    def faixa(v):
        d = _n(v.get("duration"))
        if not d:
            return None
        for de, ate, nome in FAIXAS:
            if de <= d < ate:
                return nome
        return None
    return _agrupar(videos, faixa, lambda x: x)


def ritmo(videos):
    """Publicações por semana contra as views daquela semana.

    Responde se postar mais está de fato trazendo mais - que é a decisão mais
    cara da rotina dela (15-16 vídeos por dia). O app não cruza cadência com
    resultado em lugar nenhum.
    """
    semanas = {}
    for v in videos:
        q = _quando(v.get("create_time"))
        if not q:
            continue
        iso = q.isocalendar()
        chave = "%04d-S%02d" % (iso[0], iso[1])
        alvo = semanas.setdefault(chave, {"semana": chave, "videos": 0, "views": 0.0})
        alvo["videos"] += 1
        alvo["views"] += _n(v.get("view_count"))
    fora = sorted(semanas.values(), key=lambda x: x["semana"])
    for s in fora:
        s["views_por_video"] = round(s["views"] / s["videos"], 1) if s["videos"] else 0
    return fora


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


def _palavras(texto):
    """As palavras úteis de um título/descrição, sem acento e sem hashtag.

    Hashtag sai fora de propósito: `#fyp` e `#viral` estão em tudo e não contam
    nada sobre o assunto. O que interessa é a palavra falada no título.
    """
    import re
    import unicodedata
    limpo = re.sub(r"[#@]\S+", " ", texto or "")
    limpo = "".join(c for c in unicodedata.normalize("NFD", limpo)
                    if unicodedata.category(c) != "Mn").lower()
    return [p for p in re.findall(r"[a-z]{3,}", limpo) if p not in PARADAS]


def temas(videos, minimo=3, quantos=12):
    """Que ASSUNTO rende mais, tirado do texto do título e da descrição.

    POR QUE ISTO EXISTE. O pedido não era só ver o desempenho: era ter dado que
    permita dizer **o que gravar amanhã**. Duração, horário e ritmo respondem
    "como postar"; nenhum responde "sobre o quê". A única pista de assunto que a
    Display API dá é o texto que ela mesma escreveu - e cruzado com as views ele
    vira a pergunta certa: quais palavras aparecem nos vídeos que renderam.

    A conta é a mediana das views dos vídeos que contêm a palavra, contra a
    mediana geral. Palavra em menos de %d vídeos não entra: com um vídeo só, a
    "palavra campeã" seria só o vídeo campeão de novo.

    ISTO É PISTA, NÃO PROVA. Palavra que aparece junto de bom desempenho pode ser
    causa ou coincidência - o assunto pode ter vindo junto de um áudio em alta,
    de um horário melhor ou de sorte. Serve pra decidir o que TESTAR, não pra
    concluir. A tela precisa dizer isso.
    """ % minimo
    geral = _mediana([_n(v.get("view_count")) for v in videos])
    if not geral:
        return {"geral": None, "itens": []}

    onde = {}
    for v in videos:
        texto = (v.get("title") or "") + " " + (v.get("video_description") or "")
        for p in set(_palavras(texto)):
            onde.setdefault(p, []).append(_n(v.get("view_count")))

    itens = []
    for palavra, vistos in onde.items():
        if len(vistos) < minimo:
            continue
        med = _mediana(vistos)
        itens.append({"palavra": palavra, "videos": len(vistos),
                      "mediana": med,
                      "vezes_a_geral": round(med / geral, 2) if geral else None})
    itens.sort(key=lambda x: -(x["vezes_a_geral"] or 0))
    return {"geral": geral, "amostra": len(videos),
            "itens": itens[:quantos],
            "piores": itens[-quantos:][::-1] if len(itens) > quantos else []}


def resumo_para_conselho(fotos):
    """Um texto curto com o que importa pra recomendar o próximo vídeo.

    POR QUE EM TEXTO, e não só o JSON que a tela usa: o pedido foi que estes
    dados sirvam **também para o Claude** dizer os próximos passos. Um resumo
    denso e legível é o que cabe numa conversa sem despejar 80 KB de JSON, e é
    o que sobrevive a ser colado num chat.

    Só entra o que tem amostra suficiente. Linha sem dado é linha omitida - é
    melhor um resumo curto e verdadeiro do que um completo e inventado.
    """
    videos = ultimos_videos(fotos)
    if not videos:
        return "Ainda não há leitura da API do TikTok."

    linhas = []
    med = _mediana([_n(v.get("view_count")) for v in videos])
    linhas.append("%d vídeos lidos, %d dia(s) de histórico. Mediana: %s views."
                  % (len(videos), len(fotos),
                     ("%.0f" % med) if med else "?"))

    d = duracao_que_rende(videos)
    if d:
        # Só afirma "pior" quando existe com o que comparar. Com um grupo só, a
        # frase saía "melhor 45-60s... pior 45-60s" - dizendo duas coisas
        # opostas sobre a mesma faixa, que é pior do que não dizer nada.
        linha = ("Duração que mais rende: %s (mediana %.0f, em %d vídeos)."
                 % (d[0]["rotulo"], d[0]["mediana"], d[0]["videos"]))
        if len(d) > 1:
            linha += " Pior: %s (%.0f)." % (d[-1]["rotulo"], d[-1]["mediana"])
        else:
            linha += " É a única faixa com vídeos suficientes pra comparar."
        linhas.append(linha)

    h = melhor_horario(videos)
    if h["por_hora"]:
        linhas.append("Melhor horário: %s (mediana %.0f, %d vídeos)."
                      % (h["por_hora"][0]["rotulo"], h["por_hora"][0]["mediana"],
                         h["por_hora"][0]["videos"]))
    if h["por_dia"]:
        linhas.append("Melhor dia: %s (mediana %.0f, %d vídeos)."
                      % (h["por_dia"][0]["rotulo"], h["por_dia"][0]["mediana"],
                         h["por_dia"][0]["videos"]))

    tm = temas(videos)
    if tm["itens"]:
        top = ", ".join("%s (%.1fx, %d víd.)" % (i["palavra"], i["vezes_a_geral"], i["videos"])
                        for i in tm["itens"][:5])
        linhas.append("Assuntos acima da mediana: " + top +
                      " — pista para testar, não prova.")

    c = taxa_de_compartilhamento(videos)
    if c["itens"]:
        linhas.append("Mais compartilhado por view: \"%s\" (%.2f%%). Mediana: %.2f%%."
                      % (c["itens"][0]["titulo"], c["itens"][0]["taxa"],
                         c["mediana"] or 0))

    a = acelerando(fotos)
    if a["pronto"] and a["itens"] and a["itens"][0]["ganho_ultimo"] > 0:
        linhas.append("Crescendo agora: \"%s\" (+%.0f views na última leitura)."
                      % (a["itens"][0]["titulo"], a["itens"][0]["ganho_ultimo"]))
    r = ressurreicoes(fotos)
    if r["pronto"] and r["itens"]:
        linhas.append("RESSUSCITOU: \"%s\", %d dias de idade, +%.0f views."
                      % (r["itens"][0]["titulo"], r["itens"][0]["idade_dias"],
                         r["itens"][0]["ganho_ultimo"]))
    mv = meia_vida(fotos)
    if mv["pronto"] and mv["dias"] is not None:
        linhas.append("Meia-vida: %.0f dia(s) para juntar 80%% das views (%d vídeos)."
                      % (mv["dias"], mv["amostra"]))
    return "\n".join(linhas)


def tudo(fotos):
    """Todos os painéis numa chamada só."""
    videos = ultimos_videos(fotos)
    return {
        "dias_de_historico": len(fotos),
        "videos": len(videos),
        "acelerando": acelerando(fotos),
        "ressurreicoes": ressurreicoes(fotos),
        "meia_vida": meia_vida(fotos),
        "contra_a_mediana": contra_a_mediana(videos),
        "compartilhamento": taxa_de_compartilhamento(videos),
        "horario": melhor_horario(videos),
        "duracao": duracao_que_rende(videos),
        "ritmo": ritmo(videos),
        "temas": temas(videos),
        "resumo": resumo_para_conselho(fotos),
    }


def painel_de_desempenho(tk, conta=None, estado=None):
    """Os dashboards da API do TikTok. Uma resposta só.

    Sai das FOTOGRAFIAS diárias, não de uma chamada à API: a série de tempo é o
    que dá valor a quase tudo aqui, e ela só existe porque alguém guardou as
    leituras. Abrir a tela não dispara chamada ao TikTok.

    MORA AQUI, E NÃO NO painel.py, porque o servidor do Raspberry precisa da
    mesma resposta e o painel.py não vai para lá (quase 3.000 linhas presas a ffmpeg).

    `tk` é o módulo tiktok, e `estado` é uma função sem argumentos: o painel
    informa se a tarefa agendada do Windows existe, e o add-on informa outra
    coisa. Este arquivo não pode passar a saber o que é agendador do Windows.
    """
    def _estado():
        # O estado é o enfeite ao lado do número; o número é o que ela veio ver.
        # Um agendador indisponível não pode esvaziar a tela inteira.
        try:
            return estado() if estado else {}
        except Exception:
            return {}

    try:
        lista = tk.contas()
    except Exception as e:
        return {"ok": False, "erro": str(e)}

    # QUAL PERFIL. A tela manda o open_id escolhido; sem ele, o primeiro
    # conectado. Perfil pedido que não existe mais (ela desconectou noutra aba)
    # cai no primeiro em vez de dar erro — tela vazia com mensagem técnica é
    # pior que tela certa do perfil vizinho, que ela reconhece na hora.
    ids = [c["open_id"] for c in lista]
    escolhida = conta if conta in ids else (ids[0] if ids else None)
    if escolhida is None:
        return {"ok": True, "tem_dados": False, "conta": None, "tiktok": _estado()}

    try:
        fotos = tk.fotos(escolhida)
    except Exception as e:
        return {"ok": False, "erro": str(e)}
    if not fotos:
        return {"ok": True, "tem_dados": False, "conta": escolhida,
                "tiktok": _estado()}

    try:
        d = tudo(fotos)
    except Exception as e:
        return {"ok": False, "erro": str(e)}
    d["ok"] = True
    d["tem_dados"] = True
    d["conta"] = escolhida
    d["tiktok"] = _estado()
    return d

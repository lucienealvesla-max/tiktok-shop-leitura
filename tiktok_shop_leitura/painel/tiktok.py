# -*- coding: utf-8 -*-
"""Puxa os números dos vídeos direto do TikTok, pela Display API.

POR QUE ISTO EXISTE (31/08/2026). Ela quer os dados de visualização sem ter que
baixar planilha toda semana. A pesquisa da API está registrada no CLAUDE.md; o
resumo que importa aqui:

  - A conta dela é **Creator**, e a Display API funciona com conta pessoal ou
    de criadora. Não exige conta Business, não exige CNPJ.
  - As diretrizes de revisão proíbem app "for private or personal use", então o
    caminho de app aprovado está fechado. O **sandbox** existe justamente pra
    usar sem submeter à revisão, com até 10 contas do próprio desenvolvedor.
  - Como o painel é um programa local, o app tem que ser registrado como
    **Desktop**: só o tipo Desktop aceita `http://localhost:<porta>` como
    endereço de retorno. App Web exige https, que aqui não existe.

O QUE ELE TRAZ, e o que não traz. A Display API dá por vídeo: id, data, título,
descrição, duração, visualizações, curtidas, comentários e compartilhamentos.
**Não dá tempo de exibição, retenção nem origem do tráfego** - isso só existe na
Accounts API, que exige conta Business (e conta Business perde os áudios em
alta), ou no export do TikTok Studio.

DESLIGADO POR PADRÃO. Sem o arquivo de configuração, nada aqui roda e o painel
segue como sempre - sem falar com a internet, que é a exigência dela desde o
começo. Ligar é uma decisão dela, não um efeito colateral de atualizar.
"""

import base64
import hashlib
import json
import os
import re
import secrets
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

PASTA = Path(__file__).resolve().parent

# ONDE OS DADOS MORAM. Por padrão ao lado deste arquivo, como sempre foi.
# A variável existe por causa do add-on do Home Assistant: lá o container é
# reconstruído a cada atualização e só /share sobrevive, então guardar ao lado
# do código apagaria o histórico a cada versão nova. Série temporal perdida não
# se recupera depois — é o motivo de este projeto guardar fotografias diárias.
# String vazia conta como "não informado": é o que uma variável declarada e não
# preenchida entrega, e cair na raiz do disco seria pior que ignorar.
BASE = Path(os.environ.get("TIKTOK_SHOP_DADOS") or PASTA)
CONFIG = BASE / "tiktok.json"             # client_key / client_secret (dela)
CONTAS = BASE / ".tiktok_contas"          # uma pasta por perfil conectado

# VARIOS PERFIS (04/09/2026). Ela tem mais de um. Antes, o token morava num
# arquivo so e a fotografia do dia se chamava `AAAA-MM-DD.json`, sem dizer de
# qual conta: conectar o segundo perfil substituia o token do primeiro, e a
# leitura do segundo **sobrescrevia a fotografia do dia** do primeiro.
#
# Isso e a unica perda do sistema que nao se recupera - o TikTok so mostra o
# numero acumulado de agora, entao a trajetoria de um video existe apenas
# porque guardamos leituras sucessivas. Hoje cada conta tem sua pasta:
#
#   .tiktok_contas/<pasta da conta>/token.json     a autorizacao
#                                  /ficha.json     open_id + nome de exibicao
#                                  /fotos/AAAA-MM-DD.json
#
# A IDENTIDADE E O `open_id`, nunca o nome: ela pode renomear o perfil no
# TikTok, e guardar por nome faria o historico sumir da tela com os arquivos
# intactos no disco - que e exatamente o que parece perda de dados.

AUTORIZAR = "https://www.tiktok.com/v2/auth/authorize/"
TOKEN_URL = "https://open.tiktokapis.com/v2/oauth/token/"
LISTA_URL = "https://open.tiktokapis.com/v2/video/list/"

ESCOPOS = "user.info.basic,video.list"

# O que se pede por vídeo. `video_description` entra porque é nela que mora o
# CÓDIGO (G14-A-CTA2) - sem isso o casamento com o arquivo montado volta a
# depender só da duração, que já foi medida e quase não separa nada.
CAMPOS = ["id", "create_time", "title", "video_description", "duration",
          "view_count", "like_count", "comment_count", "share_count",
          "share_url", "cover_image_url"]

_pendente = {}     # state -> code_verifier, entre o "entrar" e o "retorno"


def configurado():
    """Configurado = tem arquivo E tem chave dentro.

    So conferir se o arquivo existe deixava passar o caso do arquivo criado com
    os campos em branco (que e exatamente como ele nasce, esperando ela colar):
    a tela dizia "falta autorizar", oferecia o botao, e o botao dava erro. Agora
    o arquivo pela metade continua contando como "falta configurar", que e a
    verdade, e a tela mostra o passo a passo.
    """
    if not CONFIG.is_file():
        return False
    cfg = _config()
    return bool((cfg.get("client_key") or "").strip())


def _config():
    try:
        return json.loads(CONFIG.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _nome_de_pasta(open_id):
    """Nome de pasta a partir do open_id, que chega pela rede.

    Saneia em vez de recusar - recusar deixaria ela sem conectar por um detalhe
    que nao e culpa dela. O sufixo com o resumo do open_id existe porque o
    saneamento pode juntar dois ids diferentes no mesmo texto; sem ele, duas
    contas dividiriam a mesma pasta, que e o bug que este arquivo inteiro
    existe pra impedir.
    """
    limpo = re.sub(r"[^A-Za-z0-9_-]", "_", str(open_id or ""))
    resumo = hashlib.sha256(str(open_id or "").encode("utf-8")).hexdigest()[:8]
    return "c_" + limpo[:40].lstrip("-_") + "_" + resumo


def pasta_da_conta(open_id, criar=False):
    p = CONTAS / _nome_de_pasta(open_id)
    if criar:
        (p / "fotos").mkdir(parents=True, exist_ok=True)
    return p


def guardar_token(d, nome=None):
    """Grava a autorizacao da conta que ela mesma identifica.

    O `open_id` vem DENTRO da resposta do TikTok. Por isso reconectar a mesma
    conta atualiza em vez de duplicar, e por isso quem chama nao precisa saber
    de antemao qual perfil ela escolheu na tela do TikTok.
    """
    d = dict(d)
    nome = nome or d.pop("nome", None)
    d.pop("nome", None)
    open_id = d.get("open_id") or ""
    pasta = pasta_da_conta(open_id, criar=True)
    d["obtido_em"] = int(time.time())
    alvo = pasta / "token.json"
    alvo.write_text(json.dumps(d), encoding="utf-8")
    try:
        os.chmod(alvo, 0o600)           # não impede muito no Windows, mas não custa
    except OSError:
        pass

    antiga = _ficha(open_id)
    (pasta / "ficha.json").write_text(json.dumps({
        "open_id": open_id,
        "nome": nome or antiga.get("nome") or "perfil",
        "desde": antiga.get("desde") or int(time.time()),
    }), encoding="utf-8")
    return True


def _ficha(open_id):
    try:
        return json.loads((pasta_da_conta(open_id) / "ficha.json")
                          .read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def token_de(open_id):
    try:
        return json.loads((pasta_da_conta(open_id) / "token.json")
                          .read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def contas():
    """Os perfis conectados, do mais antigo pro mais novo. Nunca levanta."""
    if not CONTAS.is_dir():
        return []
    fora = []
    for pasta in sorted(CONTAS.iterdir()):
        if not pasta.is_dir():
            continue
        try:
            ficha = json.loads((pasta / "ficha.json").read_text(encoding="utf-8"))
            token = json.loads((pasta / "token.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue                    # pasta pela metade nao vira perfil na tela
        if not token.get("access_token"):
            continue
        quando = None
        if token.get("obtido_em"):
            quando = datetime.fromtimestamp(
                token["obtido_em"]).strftime("%d/%m %H:%M")
        dias = len(list((pasta / "fotos").glob("*.json")))             if (pasta / "fotos").is_dir() else 0
        fora.append({"open_id": ficha.get("open_id", ""),
                     "nome": ficha.get("nome") or "perfil",
                     "conectado_em": quando,
                     "desde": ficha.get("desde") or 0,
                     "dias": dias})
    fora.sort(key=lambda c: c["desde"])
    return fora


def _desafio(verificador):
    """O code_challenge do PKCE do TikTok.

    ATENÇÃO: o TikTok pede **SHA256 em HEXADECIMAL**, e não o base64url que o
    RFC 7636 usa e que toda biblioteca de OAuth gera por padrão. Usar base64url
    aqui devolve "invalid code_verifier" na hora da troca - erro que aponta pro
    verificador quando o errado é o desafio, e por isso custa caro de achar.
    """
    return hashlib.sha256(verificador.encode("ascii")).hexdigest()


def url_de_login(endereco_de_retorno):
    """(url, erro). Manda ela pro TikTok autorizar."""
    cfg = _config()
    if not cfg.get("client_key"):
        return None, "falta o client_key no painel/tiktok.json"
    verificador = "".join(secrets.choice(
        "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~")
        for _ in range(64))
    estado = secrets.token_urlsafe(16)
    _pendente[estado] = {"verificador": verificador, "retorno": endereco_de_retorno,
                         "quando": time.time()}
    # Limpa pedidos velhos: sem isso, cada tentativa abandonada fica de lembrança
    # na memória do painel até ele reiniciar.
    for k in [k for k, v in _pendente.items() if time.time() - v["quando"] > 900]:
        _pendente.pop(k, None)

    q = urllib.parse.urlencode({
        "client_key": cfg["client_key"],
        "scope": ESCOPOS,
        "response_type": "code",
        "redirect_uri": endereco_de_retorno,
        "state": estado,
        "code_challenge": _desafio(verificador),
        "code_challenge_method": "S256",
    })
    return AUTORIZAR + "?" + q, None


def _pedir(url, dados=None, cabecalhos=None, metodo=None):
    """(ok, dados). Nunca levanta: quem chama é uma rota do painel."""
    corpo = None
    if dados is not None:
        corpo = urllib.parse.urlencode(dados).encode("utf-8") \
            if isinstance(dados, dict) else dados
    req = urllib.request.Request(url, data=corpo, method=metodo)
    for k, v in (cabecalhos or {}).items():
        req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return True, json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            return False, json.loads(e.read().decode("utf-8"))
        except Exception:
            return False, {"erro": "HTTP %s" % e.code}
    except Exception as e:
        return False, {"erro": str(e)}


def trocar_codigo(code, estado):
    """Troca o código pelo token. (ok, mensagem)"""
    pend = _pendente.pop(estado, None)
    if not pend:
        # State não confere: ou expirou, ou o pedido não saiu daqui. Recusar é o
        # certo - é a proteção contra alguém induzir a troca de um código alheio.
        return False, "pedido de login não reconhecido (tente entrar de novo)"
    cfg = _config()
    ok, d = _pedir(TOKEN_URL, {
        "client_key": cfg.get("client_key", ""),
        "client_secret": cfg.get("client_secret", ""),
        "code": urllib.parse.unquote(code),
        "grant_type": "authorization_code",
        "redirect_uri": pend["retorno"],
        "code_verifier": pend["verificador"],
    }, {"Content-Type": "application/x-www-form-urlencoded"})
    if not ok or not d.get("access_token"):
        return False, str(d.get("error_description") or d.get("erro") or d)
    # O nome de exibicao nao vem na troca do codigo - so o open_id. Buscar aqui
    # e o que permite a tela dizer "Perfil A / Perfil B" em vez de mostrar dois
    # identificadores opacos e ela ter que adivinhar qual e qual. Se a busca
    # falhar, conecta mesmo assim: perfil sem rotulo bonito e melhor que perfil
    # nao conectado.
    guardar_token(d, nome=_nome_no_tiktok(d.get("access_token")))
    return True, "conectado"


def _nome_no_tiktok(token):
    """O display_name da conta, ou None. Nunca levanta."""
    try:
        ok, d = _pedir(
            "https://open.tiktokapis.com/v2/user/info/?fields=open_id,display_name",
            None, {"Authorization": "Bearer " + str(token)}, "GET")
        if ok:
            return ((d.get("data") or {}).get("user") or {}).get("display_name")
    except Exception:
        pass
    return None


def _valido(open_id):
    """Token de acesso válido, renovando se preciso. (token, erro)

    O de acesso dura 24h e o de renovação 365 dias. A renovação PODE devolver um
    refresh_token diferente - guardar o novo é obrigatório, senão daqui a um ano
    a conexão morre sozinha e ninguém lembra por quê.
    """
    t = token_de(open_id)
    if not t:
        return None, "não conectado"
    idade = time.time() - t.get("obtido_em", 0)
    if idade < (t.get("expires_in", 86400) - 300):
        return t["access_token"], None
    cfg = _config()
    ok, d = _pedir(TOKEN_URL, {
        "client_key": cfg.get("client_key", ""),
        "client_secret": cfg.get("client_secret", ""),
        "grant_type": "refresh_token",
        "refresh_token": t.get("refresh_token", ""),
    }, {"Content-Type": "application/x-www-form-urlencoded"})
    if not ok or not d.get("access_token"):
        return None, "não consegui renovar o acesso: " + str(
            d.get("error_description") or d.get("erro") or d)
    # A renovacao pode devolver um open_id ausente: sem ele, guardar_token
    # abriria uma pasta nova e o historico desta conta ficaria orfao.
    d.setdefault("open_id", open_id)
    guardar_token(d)
    return d["access_token"], None


def puxar_videos(open_id, limite=None, tentativas=4, espera=20):
    """Baixa a lista de vídeos com os números. (ok, dados)

    SEM TETO por padrao (04/09/2026). Havia um limite de 200, e ele escondia o
    video MAIS VISTO dela - 2.102.276 views, publicado em 01/06/2026, muito
    alem dos 200 mais recentes. Ela percebeu olhando a tela: "ela tem video com
    mais de 2 milhoes de views e parece que nao vieram".

    E MESMO SEM TETO A LEITURA ENCOLHEU (07/09/2026), que é um problema
    diferente e pior, porque não tinha sintoma:

        04/09 -> 2.328 vídeos, desde 28/08/2024
        05/09 -> 1.478 vídeos, só desde 02/04/2026
        06/09 ->   958 vídeos, só desde 02/06/2026

    A paginação para no meio — a API recusa a página seguinte — e o código
    antigo devolvia o que tinha com `parcial: True`, `puxar_diario` gravava, e
    a tela mostrava um terço da conta com cara de conta inteira. O vídeo de 2,1
    milhão sumiu da tela no dia 06 sem uma linha de aviso.

    DUAS RESPOSTAS, e as duas são necessárias:

    1. **Aqui: insistir.** A página que falhou é tentada de novo, do MESMO
       cursor, depois de uma espera que dobra. Se a recusa for limite de ritmo
       — a explicação mais provável, porque a conta inteira são 117 pedidos
       seguidos — esperar resolve, e a leitura termina completa.
    2. **No catalogo.py: não esquecer.** Se nem insistindo vier tudo, o que já
       foi visto uma vez continua na tela. Insistir reduz a chance; o catálogo
       tira a consequência.

    `parcial` continua saindo daqui, agora com `paginas` e `motivo` junto: sem
    isso a próxima investigação recomeça do zero, olhando arquivo por arquivo
    como esta recomeçou.
    """
    token, erro = _valido(open_id)
    if not token:
        return False, {"erro": erro}

    videos, cursor, tem_mais = [], None, True
    paginas, erro_final = 0, None
    while tem_mais and (limite is None or len(videos) < limite):
        corpo = {"max_count": 20}
        if cursor:
            corpo["cursor"] = cursor
        ok, d = _pedir(LISTA_URL + "?fields=" + ",".join(CAMPOS),
                       json.dumps(corpo).encode("utf-8"),
                       {"Authorization": "Bearer " + token,
                        "Content-Type": "application/json"})
        if not ok:
            erro_final = (d.get("error") or {}).get("message") or d.get("erro") or str(d)
            # A MESMA PÁGINA DE NOVO, esperando cada vez mais. Só desiste depois
            # de `tentativas`; a espera dobrando é o que dá tempo de a janela de
            # limite virar sem inundar a API de pedidos iguais.
            for tentativa in range(1, tentativas):
                time.sleep(espera * (2 ** (tentativa - 1)))
                ok, d = _pedir(LISTA_URL + "?fields=" + ",".join(CAMPOS),
                               json.dumps(corpo).encode("utf-8"),
                               {"Authorization": "Bearer " + token,
                                "Content-Type": "application/json"})
                if ok:
                    erro_final = None
                    break
                erro_final = ((d.get("error") or {}).get("message")
                              or d.get("erro") or str(d))
        if not ok:
            # Devolve o que já veio: meia lista é melhor que nada, e a tela diz
            # que veio pela metade.
            return bool(videos), {"erro": erro_final, "videos": videos,
                                  "parcial": True, "paginas": paginas,
                                  "motivo": "a API recusou a página %d mesmo "
                                            "depois de %d tentativas: %s"
                                            % (paginas + 1, tentativas, erro_final)}
        dados = d.get("data") or {}
        veio = dados.get("videos") or []
        videos.extend(veio)
        paginas += 1
        cursor = dados.get("cursor")
        tem_mais = bool(dados.get("has_more")) and cursor is not None
    return True, {"videos": videos if limite is None else videos[:limite],
                  "parcial": False, "paginas": paginas,
                  "motivo": "a API disse que não há mais páginas"}


def gravar_na_pasta_de_dados(videos, pasta, perfil=None):
    """Grava o que veio da API como CSV na pasta de dados. (ok, mensagem)

    DE PROPÓSITO no mesmo formato que o export do TikTok Studio: assim o leitor,
    o casamento e o dashboard funcionam sem uma linha de mudança, e a API vira
    só mais um jeito de encher a mesma pasta. Se amanhã a API fechar, o caminho
    da planilha continua inteiro.
    """
    if pasta is None:
        return False, "a pasta de dados não está acessível"
    linhas = ["Video title,Post time,Video views,Likes,Comments,Shares,Video duration,Description"]
    for v in videos:
        quando = ""
        if v.get("create_time"):
            try:
                quando = datetime.fromtimestamp(int(v["create_time"])).strftime("%Y-%m-%d %H:%M")
            except (ValueError, OSError):
                quando = ""
        # A descrição vai junto e SEM cortar: é onde o código do vídeo aparece.
        def cel(x):
            s = str(x if x is not None else "").replace('"', "'")
            return '"' + s.replace("\n", " ").replace("\r", " ") + '"'
        linhas.append(",".join([
            cel(v.get("title") or v.get("video_description") or ""),
            cel(quando),
            cel(v.get("view_count") or 0),
            cel(v.get("like_count") or 0),
            cel(v.get("comment_count") or 0),
            cel(v.get("share_count") or 0),
            cel(v.get("duration") or 0),
            cel(v.get("video_description") or ""),
        ]))
    # Cada perfil na SUA subpasta: com um nome fixo, o segundo perfil
    # sobrescreveria o CSV do primeiro, e a tela mostraria os numeros de um
    # perfil sob o nome do outro.
    if perfil:
        try:
            import dados as _dados
            pasta = _dados.subpasta_do_perfil(pasta, perfil)
            pasta.mkdir(parents=True, exist_ok=True)
        except (ImportError, OSError) as e:
            return False, str(e)
    alvo = pasta / "tiktok_api.csv"
    try:
        alvo.write_text("\n".join(linhas) + "\n", encoding="utf-8")
    except OSError as e:
        return False, str(e)
    return True, "gravei %d vídeo(s) em %s" % (len(videos), alvo.name)


def guardar_foto(open_id, videos):
    """Grava a leitura de hoje, crua. (ok, mensagem)

    POR QUE ISTO E O CORACAO DO DASHBOARD. O TikTok mostra o numero ACUMULADO de
    agora; a API tambem. Nem um nem outro mostram a TRAJETORIA: quantas views o
    video ganhou ontem, se esta acelerando, se um video de tres semanas voltou a
    crescer. Essa dimensao de tempo **nao existe em lugar nenhum** ate alguem
    guardar leituras sucessivas.

    Uma por dia basta - a segunda do mesmo dia sobrescreve. E o que se guarda e
    o CRU, nao o agregado: metrica que eu inventar daqui a dois meses vai poder
    ser calculada sobre este passado.
    """
    pasta = pasta_da_conta(open_id) / "fotos"
    try:
        pasta.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        return False, str(e)
    # O `share_url` ENTRA (07/09/2026), e a capa NÃO. Os dois vinham da API e
    # os dois eram jogados fora aqui, mas eles têm custos diferentes:
    #
    #   - o link tem ~55 caracteres, nunca muda, e é o que responde "qual vídeo
    #     é este" — 92 vídeos dela começam com os mesmos 40 caracteres de
    #     título. Guardar custa ~130 KB por dia e vale cada byte.
    #   - o endereço da capa tem ~300 caracteres, é ASSINADO e EXPIRA. Guardar
    #     numa fotografia por dia seriam ~700 KB diários de endereço que já
    #     nasce vencendo, num cartão de Raspberry. A capa mora só no catálogo,
    #     que é um arquivo por conta, reescrito a cada leitura em vez de somado.
    magros = []
    for v in videos or []:
        magros.append({k: v.get(k) for k in
                       ("id", "create_time", "duration", "view_count",
                        "like_count", "comment_count", "share_count",
                        "title", "video_description", "share_url")})
    alvo = pasta / (datetime.now().strftime("%Y-%m-%d") + ".json")
    # A FOTOGRAFIA DO DIA E UMA, e uma leitura parcial nao pode encolhe-la.
    # Cenario real: a tarefa das 21h grava os 2.327 videos; ela aperta "Ler
    # agora", a leitura falha no meio e volta 500. Substituindo, os outros 1.827
    # ficariam com um buraco NAQUELE dia - e buraco na serie nao se recupera.
    # A uniao pelo id resolve os dois lados: mantem quem ja estava e atualiza os
    # numeros de quem voltou agora.
    try:
        antes = json.loads(alvo.read_text(encoding="utf-8"))
        juntos = {v.get("id"): v for v in (antes.get("videos") or [])}
        leituras = int(antes.get("leituras") or 1)
    except (OSError, ValueError):
        juntos, leituras = {}, 0
    if juntos:
        for v in magros:
            juntos[v.get("id")] = v
        magros = list(juntos.values())
    try:
        # `leituras` é quantas vezes a API foi consultada HOJE para esta conta.
        # É o que deixa `puxar_diario` insistir numa leitura que veio pela
        # metade sem virar laço infinito de pedidos se a API estiver fechada.
        alvo.write_text(json.dumps({"lido_em": int(time.time()),
                                    "leituras": leituras + 1,
                                    "videos": magros}), encoding="utf-8")
    except OSError as e:
        return False, str(e)

    # O CATALOGO, logo depois da fotografia e nunca antes: a fotografia é a
    # única coisa insubstituível aqui, e um erro no catálogo não pode custar o
    # dia na série. Por isso ele vem depois e não derruba nada — o catálogo se
    # reconstrói das fotografias a qualquer momento, e a fotografia não.
    recado_catalogo = ""
    try:
        import catalogo
        # O CATÁLOGO RECEBE O BRUTO, não `magros`: é dele que sai a capa, que
        # de propósito não entra na fotografia.
        ok_cat, recado_catalogo = catalogo.atualizar(
            pasta_da_conta(open_id), videos,
            datetime.now().strftime("%Y-%m-%d"))
        if not ok_cat:
            recado_catalogo = "catálogo não gravou: " + str(recado_catalogo)
    except Exception as e:
        recado_catalogo = "catálogo não gravou: %s" % e
    return True, "%d video(s) fotografados em %s%s" % (
        len(magros), alvo.name, (" · " + recado_catalogo) if recado_catalogo else "")


def fotografia_de_hoje(open_id):
    """Os videos da fotografia de HOJE desta conta, ja unidos. [] se nao houver.

    Existe para o CSV sair daqui, e nao da leitura crua. A fotografia e uniao;
    o CSV era escrito com o que a ULTIMA leitura trouxe, entao uma leitura
    parcial encolhia o CSV enquanto a fotografia ficava inteira - dois numeros
    para o mesmo dia, e o casamento com os arquivos montados saindo do menor.
    """
    alvo = (pasta_da_conta(open_id) / "fotos" /
            (datetime.now().strftime("%Y-%m-%d") + ".json"))
    try:
        return json.loads(alvo.read_text(encoding="utf-8")).get("videos") or []
    except (OSError, ValueError):
        return []


def fotos(open_id):
    """Todas as fotografias DESTA conta, da mais antiga pra mais nova."""
    pasta = pasta_da_conta(open_id) / "fotos"
    if not pasta.is_dir():
        return []
    fora = []
    for p in sorted(pasta.glob("*.json")):
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        d["dia"] = p.stem
        fora.append(d)
    return fora


def estado():
    """O que a tela precisa saber pra decidir o que mostrar.

    As quatro chaves antigas continuam aqui de proposito: a tela le todas elas
    em varios lugares, e trocar tudo de uma vez transformaria uma mudanca de
    dados numa reescrita da pagina. `contas` e a nova, e e por ela que o
    seletor de perfil se monta.
    """
    cs = contas()
    return {"configurado": configurado(),
            "conectado": bool(cs),
            "conectado_em": cs[0]["conectado_em"] if cs else None,
            "dias_de_historico": max([c["dias"] for c in cs] or [0]),
            "contas": cs}

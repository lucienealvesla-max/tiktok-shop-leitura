# Leitura TikTok Shop

Lê os números do TikTok uma vez por dia e serve o dashboard de desempenho.

## Antes de ligar: os dados

O add-on **não faz o login do TikTok**. Ele consome uma pasta de contas já
autorizadas, que você coloca em `/share/tiktok-shop/`:

```
/share/tiktok-shop/
  tiktok.json                     as chaves do seu app (client_key/client_secret)
  .tiktok_contas/
    c_<perfil>/
      ficha.json                  nome e open_id do perfil
      token.json                  a autorizacao
      fotos/                      as leituras diarias, uma por dia
```

Ponha esses arquivos ali (pelo add-on **Samba share** ou **Advanced SSH**) antes
de iniciar. **`/share` sobrevive à reconstrução do add-on** — é por isso que os
dados moram lá e não dentro da imagem. Atualizar o add-on **não apaga o seu
histórico**.

Sem esses arquivos o add-on **sobe assim mesmo** e a tela diz que não há conta
conectada. O log avisa o que está faltando, em vez de falhar em silêncio.

## O que ele faz depois de ligado

- **Uma vez por dia, à hora que você escolher** (opção `hora_da_leitura`, na
  aba Configuração do add-on), lê todos os perfis conectados e guarda uma
  fotografia crua por perfil. Se a leitura do dia já existir e estiver
  completa, ele sai quieto — disparo repetido não gasta chamada.
- **Lê os seguidores junto** (desde a 1.5.0): uma chamada a mais por dia, e o
  número entra na mesma fotografia. É o que faz existir a série "quantos por
  dia", que o app não tem. Precisa do escopo `user.info.stats` — veja abaixo.
- **Serve o dashboard** pela barra lateral (marque "Mostrar na barra lateral").

## Plano de gravação, aceleração por produto e roteiro por IA (1.8.0)

Três painéis que a Owra vende e cabem aqui com o dado que já existe:

**Plano de gravação de hoje** — quantos vídeos gravar e de que tipo. O tamanho
é a **sua cadência** (mediana de vídeos por dia no mês; em 19/09/2026, 8), não
um número de manual. Metade em campeões (produtos que vendem), um quarto em
apostas (parte 2 do que largou bem), um ou dois para refazer, o resto em
novo — produto ainda não testado, porque sem isso a conta para de descobrir.
Sem relatório de vendas, os campeões viram "novo" e a lista diz por quê.

**Produtos acelerando / comissão mudou** — dentro do painel de Vendas, quando
há **duas semanas** de linhas na pasta: pedidos desta semana contra a
anterior por produto (acelerando = pelo menos 2 pedidos e 1,5× a anterior),
e comissão por pedido que mudou 15% ou mais. Os dois entram na pauta
("PRODUTO ACELERANDO", "COMISSÃO MUDOU").

**Roteiro pronto para gravar** — pelo agente de IA que o Home Assistant já
tem. Na configuração do add-on, `agente_ia` recebe o id do agente (ex.:
`conversation.google_ai_conversation`; veja em Ferramentas de desenvolvedor →
Estados → `conversation.`). Depois da leitura da 1h o add-on pede, para até
**três** vídeos apontados pela pauta (EMPURRE HOJE, REFAÇA, EMPURRE O QUE
VENDE), três ganchos, um roteiro de 60–90 s em cinco blocos e um título — com
o que se sabe do vídeo. O que o texto do vídeo não diz (material, prova,
preço) vira lacuna entre colchetes para ela preencher, não invenção. O texto
vai para `<conta>/roteiros.json` e aparece dobrado sob a linha da pauta
("Roteiro pronto"). Vídeo com roteiro dos últimos 7 dias não gasta outra
chamada. Para testar sem esperar: `python3 /app/painel/roteiro.py gerar`.

## O resumo do dia no celular

Desde a 1.7.0 o add-on manda, **uma vez por dia**, um resumo pelo Home
Assistant: seguidores e quanto mudaram, ritmo de views contra a regra, as
primeiras linhas da pauta (é onde "vídeo decolou" e "produto vendeu" moram)
e as vendas de 7 dias, se houver fonte.

Na aba Configuração do add-on:

- **`avisar`**: os serviços de notificação, um por linha — por exemplo
  `notify.mobile_app_sm_s928b` (o celular com o app do Home Assistant). Vazio
  = não avisa. Para ver os nomes: Ferramentas de desenvolvedor → Serviços →
  digite `notify`.
- **`hora_do_aviso`**: quando sai (padrão 8h). Não é a hora da leitura, de
  propósito: a leitura roda à 1h, e ninguém quer push a essa hora.

Um arquivo por conta guarda o dia já avisado; reiniciar o add-on não repete o
resumo. Para testar sem esperar a hora: `python3 /app/painel/aviso.py mostrar`
imprime o texto; `... enviar` manda agora.

## Seguidores: o escopo que a conta precisa ter

O Programa de Recompensas do Criador mede seguidores, e a API só os entrega
com o escopo **`user.info.stats`** (até fevereiro de 2024 vinham no
`user.info.basic`; o TikTok separou). Dois lugares precisam tê-lo:

1. **O app**, em developers.tiktok.com → seu app → *Scopes* → *Add scopes* →
   `user.info.stats`. Sem isso o login nem oferece o escopo.
2. **A conta**, que precisa **entrar de novo** depois disso — autorização já
   dada não ganha escopo sozinha. O login mora no computador (é para
   `localhost` que o TikTok devolve); depois de entrar, copie o `token.json`
   novo para `/share/tiktok-shop/.tiktok_contas/<perfil>/`.

Enquanto a conta não tiver o escopo, o cartão de seguidores diz exatamente
isso ("a conta precisa ser autorizada de novo com o escopo user.info.stats"),
e o motivo fica gravado na fotografia do dia (`perfil_erro`). Nenhum número
velho é mostrado no lugar.

## Qual a melhor hora

**O padrão é 1h da manhã.** Era 21h até a versão 1.3.0, e o 21h era palpite. Os
dados desmentiram: nos últimos 60 dias ela publicou **de 5h da manhã até 23h56**,
e em 11 dos 14 últimos dias o último vídeo saiu **depois das 22h**.

A leitura das 21h fechava o dia com uma a três publicações ainda por vir. Esses
vídeos só entravam na fotografia do dia seguinte, já com um dia de vida — e são
justamente os vídeos novos, que o painel da **Largada** existe para pegar
enquanto ainda dá para reagir.

À 1h da manhã o dia anterior está inteiro, ela não está postando, e a máquina
está ociosa. **Se você mudar a hora, mude uma vez e deixe:** a série compara
leitura com leitura, e mudar o horário toda semana faz o "ganhou desde ontem"
comparar 20 horas com 28 sem avisar.

Regra geral, se o padrão de publicação mudar: **uma a duas horas depois do
último vídeo do dia.**

## Reinício não perde mais o dia

Se o add-on subir **depois** da hora marcada — atualização, watchdog, falta de
memória no Raspberry — ele confere na hora se a leitura de hoje já aconteceu, em
vez de esperar calado até o dia seguinte. Antes dava para passar dias sem leitura
com a tela dizendo "lendo sozinho todo dia".

O log agora conta tudo isso. Até a 1.3.0 o `PYTHONUNBUFFERED` não estava
definido, então **nenhuma linha do relógio ou da leitura diária chegava ao log**
— só as do servidor web, que saem por outro caminho. Era possível ficar dias sem
leitura sem nada aparecer.

**Um perfil que falha não impede os outros.** A fotografia é a única coisa aqui
que não se recupera, então um token vencido num perfil não pode custar o dia dos
demais.

## O catálogo: por que nada some mais da tela

A leitura da API **encolhe sozinha** de vez em quando. Aconteceu aqui:

| leitura | vídeos | mais antigo |
|---|---|---|
| 04/09/2026 | 2.328 | 28/08/2024 |
| 05/09/2026 | 1.478 | 02/04/2026 |
| 06/09/2026 | **958** | 02/06/2026 |
| 07/09/2026 | **958**, e **2.352** na segunda tentativa | 28/08/2024 |

No dia 06 o vídeo de **2.102.442 visualizações** — o maior da conta — parou de
vir, e a tela passou a dizer que o melhor vídeo tinha 277 mil. (Os 2.352 da
última linha são o catálogo inteiro; os 2.328 de 04/09 são só o que aquele dia
trouxe, antes de ela publicar mais.) A mediana, os
assuntos e o "melhor horário" passaram a descrever os últimos três meses
fingindo ser a conta inteira. **Nenhum erro apareceu.**

Duas coisas mudaram por causa disso:

- **O add-on insiste, e funciona.** Quando a API recusa uma página, ele tenta
  de novo do mesmo ponto, esperando cada vez mais (20s, 40s, 80s). Se ainda vier
  pela metade, tenta de novo mais tarde no mesmo dia — até três vezes. Em
  07/09/2026 a leitura tinha trazido 958 vídeos; a segunda tentativa, minutos
  depois, trouxe os **2.352**, de volta até 28/08/2024.

  **Não é limite de ritmo nem teto do sandbox.** A Display API permite 600
  pedidos por minuto e a conta inteira são 117; e um teto teria parado a segunda
  tentativa no mesmo lugar. O que a API faz nas vezes em que para continua sem
  explicação — mas o log agora registra em qual página ela recusou.
- **O add-on não esquece.** Um arquivo `catalogo.json` por perfil guarda o
  último número conhecido de **todo vídeo que já apareceu em alguma leitura**.
  Os painéis de retrato (vale refazer, parcerias, quantos vídeos passam de 1
  minuto) saem dele.

O que você vê na tela quando a leitura veio incompleta: um aviso em vermelho
dizendo quantos vídeos vieram dos que o painel conhece. **Nada é perdido** — o
que muda é a atualidade: vídeo que não veio hoje aparece com o número do dia em
que veio pela última vez.

Os painéis de trajetória — *Acelerando*, *Ressuscitou*, *Largada* e o ganho de
views da *Monetização* — continuam saindo só de leitura de verdade, nunca do
catálogo. Misturar o número de anteontem ali inventaria ganho que não houve.

O catálogo se reconstrói sozinho das fotografias, então apagá-lo não perde nada.

## A tela abre em menos de um segundo

Até a 1.3.2 abrir a tela levava **44 segundos** no Raspberry: cada abertura
recalculava 21 painéis sobre 2.430 vídeos × 15 leituras, e o navegador
desistia antes de o servidor terminar. Desde a 1.4.0 o painel é **calculado
uma vez, logo depois da leitura da 1h**, e gravado em
`<pasta da conta>/desempenho.json`; a tela lê o arquivo. Ele se refaz sozinho
quando os dados mudam (leitura nova, "Ler agora", versão nova do add-on) e
pode ser apagado a qualquer momento — nasce de novo das fotografias.

A linha de estado no topo diz **quando** o painel foi calculado e quanto levou.
Se você ler agora e a tela não mudar, é ali que se confere.

## O que a tela responde

Foram 21 painéis; ficaram **8**, com um critério só: o painel responde alguma
coisa que o app do TikTok não responde? Ranking de hashtag, "melhor horário",
mediana da conta, ritmo semanal, meia-vida, comentado e compartilhado por view
saíram — ou o Analytics do TikTok já mostra, ou o número saía de 4 vídeos e era
ruído.

**O que fazer amanhã** — o primeiro painel, e o único escrito em frase. Junta o
resto da tela em uma lista de ações: grave mais longo, empurre este vídeo hoje,
refaça aquele. Cada linha diz de onde saiu.

**Monetização** — as três regras do Programa de Recompensas do Criador ao lado
do medido: **views ganhas nos últimos 30 dias** (a regra pede 100 mil; até
completar 30 dias de leitura o número é projetado e a tela diz isso),
**seguidores** (a regra pede 10 mil; lido uma vez por dia com o escopo
`user.info.stats`, com o ganho desde a leitura anterior e em 7 dias — e, se a
conta ainda não tiver o escopo, a tela diz isso em vez de mostrar um número
velho) e
**quantos vídeos do período são elegíveis** — sem link de loja e acima de 1
minuto. **Vídeo com link de produto não recebe recompensa**: a Creator Academy
lista "Sponsored, TikTok One, Shop, Duet, Stitch, and Photo Mode" como
excluídos. Ele ganha comissão, que é o painel de Vendas — duas receitas, duas
regras. Medido em 19/09/2026: 240 dos 252 vídeos do mês tinham link, e zero
eram sem link e longos; a conta batia seguidores e views e não tinha um vídeo
elegível. O painel diz isso em vez de fingir que a regra de 1 minuto vale para
o que ela grava. Vídeo de loja é reconhecido pela `#tiktokshop` na descrição
(aproximação: a API não diz se há produto ancorado).

Embaixo, quantas views novas cada faixa de duração ganhou por vídeo: medido
nos dados dela, o vídeo de mais de 1 minuto ganhava **de 5 a 7 vezes** mais
que o curto — e em vídeo de loja, view é clique no produto. É por isso que
"grave mais longo" continua na pauta, agora com o motivo certo.

**Lançamentos** — todo vídeo dos últimos 7 dias, do mais novo para o mais
velho, com idade, views, quanto ganhou na última leitura (e por dia) e o total
contra a mediana da conta. Nas primeiras 48 h aparece também a **largada**:
quanto o vídeo fez nas primeiras horas, comparado com os outros da
**mesma idade**. Reagir a um vídeo que está subindo só vale enquanto ele sobe —
e a janela, medida nos dados dela, é de uns 2 dias.

**Acelerando agora** — views ganhas desde a última leitura e em 7 dias, por
vídeo. O app só mostra o acumulado.

**Ressuscitou** — vídeo com mais de 14 dias que voltou a crescer. O TikTok não
avisa.

**Vale refazer** — vídeos abaixo da sua mediana de views cujo público
compartilhou ou comentou muito acima do normal. Não são vídeos ruins: são vídeos
bons que não foram entregues.

**Vendas** (desde a 1.6.0) — comissão do mês contra a meta, o que vendeu **por
vídeo** (com pedidos por mil views) e os produtos que rendem. É a régua que
substitui "views" para quem vende. Veja a seção abaixo sobre de onde vêm os
dados.

**Parcerias e marcas** — qual parceria rende mais, em views. Comissão por marca
entra quando a Central de Afiliados estiver ligada.

## Vendas: de onde vêm, e o que ainda não está verificado

A Display API do TikTok não tem pedido nenhum. Vendas moram na **Central de
Afiliados do TikTok Shop**, que é outro app, outro portal (Partner Center) e
outra autorização. Há dois caminhos, e os dois podem coexistir:

**1. Export da Central (funciona hoje, sem aprovação nenhuma).** No app do
TikTok, Central de Afiliados → Dados/Desempenho → relatório **por vídeo** →
exportar. Ponha o `.csv` em `/share/tiktok-shop/vendas/`. O painel lê todos
os CSVs dessa pasta, reconhece as colunas pelo nome (vídeo, link, produto,
pedidos, GMV, comissão, data — em português ou inglês) e diz na tela **que
colunas encontrou e quais faltaram**. Sem coluna de vídeo (id ou link), as
vendas entram nos totais mas não na tabela por vídeo.

**2. API de afiliado (pedido a pedido, todo dia).** Precisa de um app no
Partner Center do TikTok Shop (`partner.tiktokshop.com`, separado do portal
de desenvolvedor), com os escopos de *Affiliate Creator*, e da autorização
da criadora com a conta de afiliada. Depois:

```
/share/tiktok-shop/afiliado.json
  {"app_key": "...", "app_secret": "..."}
```

A autorização devolve um `code` no endereço de retorno do app; troque-o pelo
token com `python3 /app/painel/afiliado.py conectar <code>` (de dentro do
container do add-on). A partir daí a leitura da 1h também puxa os pedidos,
guarda a **resposta crua** em `/share/tiktok-shop/vendas/api/AAAA-MM-DD.json`
e o painel lê dali.

O que está **verificado** neste caminho: a assinatura dos pedidos (testada
contra a fixture da própria documentação do TikTok — `afiliado.py testar`),
a origem da API, o cabeçalho do token, e a troca/renovação do token. O que
**não está**: o corpo exato e os campos da resposta de
`/affiliate_creator/202405/orders/search`, e se o pedido traz o id do vídeo
que vendeu. Por isso a resposta é guardada crua antes de qualquer
interpretação, e o log da primeira leitura lista os campos que vieram — se a
adivinhação de nomes estiver errada, ajusta-se `vendas.py` sem perder um dia.

**Meta do mês:** a opção `meta_mensal` (aba Configuração do add-on), em
reais. Com ela, o cartão de vendas diz quanto já deu, que percentual é, e em
quanto fecha o mês no ritmo atual.

Toda comparação diz de quantos vídeos saiu, e nenhuma usa média — um viral
distorce qualquer média, e a mediana descreve o dia normal.

Se o painel do computador (`painel.py`) copia `metricas.py` e `conteudo.py`
daqui, atenção: `conteudo.tudo()` não existe mais e `conteudo.pauta()` recebe
os painéis prontos em vez de recalculá-los. `metricas.painel_de_desempenho()`
continua com a mesma assinatura.

## Qual vídeo é qual

O título não identifica vídeo nenhum nesta conta: **92 vídeos começam com os
mesmos 40 caracteres** ("🖌️✨🖌️ Kit de pincéis que não acumulam pr"), outros 77
com outro começo, 35 com outro. São 15 publicações por dia, muitas do mesmo
produto com cortes diferentes — pelo título, "refaça este vídeo" mandava
adivinhar qual dos 92.

Toda linha que fala de um vídeo agora traz:

- a **capa**, que se reconhece de relance;
- o **título clicável**, que abre o vídeo no TikTok;
- a **data com a hora**, que separa duas publicações do mesmo produto no mesmo
  dia.

O título também aparece sem as hashtags e menções, então os 60 caracteres
visíveis descrevem o vídeo em vez de gastar metade com `#hobby #tik`.

**Isso só vale para leituras feitas a partir da versão 1.2.0.** O link e a capa
sempre vieram da API e eram descartados antes de guardar; os vídeos lidos antes
disso aparecem sem os dois até a próxima leitura completa passar por eles.

O link fica guardado na fotografia (são ~55 caracteres, e nunca mudam). **A capa
não**: o endereço dela é assinado e expira, então guardar uma cópia por dia
seriam ~700 KB diários de endereço já vencido no cartão do Raspberry. A capa
mora só no `catalogo.json`, que é reescrito a cada leitura em vez de somado —
e quando um endereço expira, a imagem simplesmente não aparece, sem quebrar a
tela.

## Só uma máquina pode ler

O `refresh_token` do TikTok é **rotativo**: renovar pode devolver um novo, e quem
não guardar o novo perde a conexão. Duas máquinas lendo a mesma conta **derrubam
uma à outra**, e o sintoma aparece dias depois.

Se você já lia de outro lugar, desligue lá **antes** de ligar aqui. A ordem
segura é: suba o add-on e confirme que a tela mostra seus perfis, **depois**
desligue a leitura antiga, **e só então** clique em "Ler agora".

## Atualizar

Quando houver versão nova, o Home Assistant mostra **Atualizar** na página do
add-on. Seus dados em `/share/tiktok-shop/` não são tocados.

Confira na tela que a versão exibida é a que você instalou. Versão velha rodando
sem ninguém perceber é o erro mais caro deste tipo de instalação.

## Quando algo não funciona

- **"nenhum perfil conectado"** — falta `tiktok.json` ou a pasta
  `.tiktok_contas/` em `/share/tiktok-shop/`. O log diz qual.
- **"A última leitura trouxe X dos Y vídeos"** — a API veio pela metade. O
  add-on já tentou de novo sozinho; o catálogo cobre o resto e nada foi perdido.
  Se aparecer todo dia, veja o log: ele diz em que página a API recusou.
- **A tela abre dizendo quantas leituras faltam** — está certo. Vários painéis
  só existem depois de duas ou três fotografias. Não é defeito: é a série ainda
  sendo construída.
- **Um perfil aparece sem nenhum dado** — ele está conectado mas nunca leu.
  Clique em "Ler agora" e leia o log: ele diz o motivo por perfil.
- **A conexão morreu sozinha depois de um tempo** — quase sempre é outra máquina
  lendo a mesma conta. Veja a seção acima.
- **O add-on não aparece na loja** — ele é só `aarch64`. Numa instalação de 32
  bits ele simplesmente não é listado, sem mensagem de erro.

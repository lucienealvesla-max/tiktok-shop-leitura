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
- **Serve o dashboard** pela barra lateral (marque "Mostrar na barra lateral").

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

No dia 06 o vídeo de **2.102.442 visualizações** — o maior da conta — parou de
vir, e a tela passou a dizer que o melhor vídeo tinha 277 mil. A mediana, os
assuntos e o "melhor horário" passaram a descrever os últimos três meses
fingindo ser a conta inteira. **Nenhum erro apareceu.**

Duas coisas mudaram por causa disso:

- **O add-on insiste.** Quando a API recusa uma página, ele tenta de novo, do
  mesmo ponto, esperando cada vez mais (20s, 40s, 80s). Se ainda vier pela
  metade, tenta de novo mais tarde no mesmo dia — até três vezes.
- **O add-on não esquece.** Um arquivo `catalogo.json` por perfil guarda o
  último número conhecido de **todo vídeo que já apareceu em alguma leitura**.
  Os painéis de retrato (mediana, assuntos, horário, duração) saem dele.

O que você vê na tela quando a leitura veio incompleta: um aviso em vermelho
dizendo quantos vídeos vieram dos que o painel conhece. **Nada é perdido** — o
que muda é a atualidade: vídeo que não veio hoje aparece com o número do dia em
que veio pela última vez.

Os painéis de trajetória — *Acelerando*, *Ressuscitou*, *Largada*, *Meia-vida* —
continuam saindo só de leitura de verdade, nunca do catálogo. Misturar o número
de anteontem ali inventaria ganho que não houve.

O catálogo se reconstrói sozinho das fotografias, então apagá-lo não perde nada.

## O que a tela responde

Metade dos painéis diz **o que aconteceu**; a outra metade diz **o que gravar**.

**O que fazer amanhã** — o primeiro painel, e o único escrito em frase. Junta o
resto da tela em uma lista de ações: empurre este vídeo hoje, refaça aquele,
volte a este assunto. Cada linha diz de onde saiu.

**Largada** — quanto o vídeo fez nas primeiras horas, comparado com os outros da
**mesma idade**. Reagir a um vídeo que está subindo só vale enquanto ele sobe.

**Vale refazer** — vídeos abaixo da sua mediana de views cujo público
compartilhou ou comentou muito acima do normal. Não são vídeos ruins: são vídeos
bons que não foram entregues.

**Assunto que rendia e você parou** — assuntos acima da sua mediana que sumiram
da rotina há mais de 21 dias. Pauta pronta, com público já testado.

**Hashtags que rendem** — o assunto rotulado por você. Hashtag que você põe em
todo vídeo aparece perto de 1,0x sozinha, sem precisar de lista negra.

**Parcerias e marcas** — qual parceria rende mais.

**Assunto em duas palavras** e **Como o título começa** — o assunto e o gancho,
medidos. Trocar a abertura é a mudança mais barata que existe.

**Comentado por visualização** — onde o público está pedindo conteúdo:
comentário é dúvida, e dúvida é pauta pronta.

**Quantos vídeos por dia** — se postar mais no mesmo dia está diluindo cada
vídeo. Os últimos 3 dias ficam de fora, porque vídeo de ontem ainda está sendo
entregue.

Toda comparação diz de quantos vídeos saiu, e nenhuma usa média — um viral
distorce qualquer média, e a mediana descreve o dia normal.

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

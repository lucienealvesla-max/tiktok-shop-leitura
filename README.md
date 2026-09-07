# Leitura TikTok Shop — add-on para Home Assistant

Lê os números dos seus vídeos do TikTok **uma vez por dia**, à hora que você
escolher, e guarda a leitura crua. Serve um dashboard de desempenho pela barra lateral do Home Assistant.

## Por que isto existe

O TikTok mostra o número **acumulado de agora**. A API também. Nem um nem outro
mostram a **trajetória**: quantas visualizações o vídeo ganhou ontem, se está
acelerando, se um vídeo de três semanas voltou a crescer.

**Essa dimensão de tempo não existe em lugar nenhum até alguém guardar leituras
sucessivas.** É só isso que este add-on faz — e é por isso que ele mora numa
máquina que fica ligada: um dia sem leitura é um buraco que não se recupera
depois.

Rodar num computador que às vezes está desligado significa perder dias, e dia
perdido não volta.

## O que ele NÃO faz

- Não processa vídeo. Nenhum ffmpeg, nenhuma transcrição.
- Não fala com o Google Drive nem com nenhum armazenamento externo.
- Não posta nada, não altera nada na sua conta. Só lê.

Ele tem **três rotas** e recusa qualquer outra, porque a tela é servida pelo
Ingress e pode acabar atrás de um túnel para a internet.

## O que você precisa antes

1. **Home Assistant OS em aarch64** (Raspberry Pi 4 de 64 bits, por exemplo).
2. **Um app de desenvolvedor do TikTok**, do tipo **Desktop** — só ele aceita
   `http://localhost:<porta>` como endereço de retorno. Você precisa do
   `client_key` e do `client_secret`, com os escopos `user.info.basic` e
   `video.list`.
3. **A conexão já autorizada.** Este add-on não faz o login: ele consome uma
   pasta de contas já autorizadas. Veja a documentação do add-on.

## Instalar

Ajustes → Add-ons → Loja de add-ons → ⋮ → **Repositórios** → cole a URL deste
repositório. O add-on aparece na loja. Depois, siga a aba **Documentação**.

## Um aviso que vale mais que o resto

O `refresh_token` do TikTok **é rotativo**: renovar pode devolver um token novo,
e quem não guardar o novo perde a conexão.

**Se duas máquinas lerem a mesma conta, uma derruba a outra** — e o sintoma
aparece dias depois, sem nada ligando causa e efeito. Se você já lê de outro
lugar (uma tarefa agendada no PC, um script, outro servidor), **desligue lá
antes** de ligar aqui.

## Licença e afiliação

Não é um produto do TikTok nem tem qualquer afiliação com a ByteDance. Use por
sua conta, respeitando os termos da API do TikTok.

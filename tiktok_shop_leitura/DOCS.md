# Leitura TikTok Shop

Lê os números do TikTok todo dia às 21h e serve o dashboard de desempenho.

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

- **Todo dia às 21h**, lê todos os perfis conectados e guarda uma fotografia
  crua por perfil. Se a leitura do dia já existir, ele sai quieto — disparo
  repetido não gasta chamada.
- **Serve o dashboard** pela barra lateral (marque "Mostrar na barra lateral").

**Por que 21h e não de manhã:** o número da noite descreve melhor o que o vídeo
fez naquele dia.

**Um perfil que falha não impede os outros.** A fotografia é a única coisa aqui
que não se recupera, então um token vencido num perfil não pode custar o dia dos
demais.

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
- **A tela abre dizendo quantas leituras faltam** — está certo. Vários painéis
  só existem depois de duas ou três fotografias. Não é defeito: é a série ainda
  sendo construída.
- **Um perfil aparece sem nenhum dado** — ele está conectado mas nunca leu.
  Clique em "Ler agora" e leia o log: ele diz o motivo por perfil.
- **A conexão morreu sozinha depois de um tempo** — quase sempre é outra máquina
  lendo a mesma conta. Veja a seção acima.
- **O add-on não aparece na loja** — ele é só `aarch64`. Numa instalação de 32
  bits ele simplesmente não é listado, sem mensagem de erro.

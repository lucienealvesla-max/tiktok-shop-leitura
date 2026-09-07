ARG BUILD_FROM=ghcr.io/home-assistant/aarch64-base-python:3.12-alpine3.19
FROM ${BUILD_FROM}

# O REPOSITORIO E PRIVADO, entao o add-on nao pode se clonar sozinho no build
# sem guardar uma credencial aqui dentro. Os arquivos sao copiados para a pasta
# do add-on por Samba/SSH, e daqui para a imagem.
COPY painel/ /app/painel/
COPY run.sh /run.sh
RUN chmod a+x /run.sh

# O COMMIT DE QUE ESTA IMAGEM FOI CONSTRUIDA. Sem isto, o Pi pode ficar rodando
# uma versao velha sem ninguem perceber - a mesma classe de "pagina nova
# conversando com servidor velho" que ja custou uma rodada neste projeto.
ARG VERSAO=desconhecida
ENV TIKTOK_SHOP_VERSAO=${VERSAO}

# SEM ISTO O RELOGIO E MUDO. O python bufferiza a saida padrao quando ela nao
# e um terminal - e no add-on nao e. O resultado: as linhas de stderr (os
# pedidos HTTP) apareciam no log do Home Assistant e NENHUM print() do relogio
# ou da leitura diaria aparecia, nunca. Sem elas nao havia como saber se a
# leitura automatica estava viva, quando ela ia rodar, ou por que a API tinha
# recusado uma pagina - a investigacao que descobriu a leitura encolhendo teve
# de ser feita arquivo por arquivo no disco por causa desta linha faltando.
ENV PYTHONUNBUFFERED=1

# Onde os dados moram: /share, que sobrevive a reconstrucao.
ENV TIKTOK_SHOP_DADOS=/share/tiktok-shop
ENV TIKTOK_SHOP_PORTA=8099

CMD [ "/run.sh" ]

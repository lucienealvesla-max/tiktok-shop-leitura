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

# Onde os dados moram: /share, que sobrevive a reconstrucao.
ENV TIKTOK_SHOP_DADOS=/share/tiktok-shop
ENV TIKTOK_SHOP_PORTA=8099

CMD [ "/run.sh" ]

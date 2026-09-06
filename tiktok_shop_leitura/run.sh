#!/usr/bin/with-contenv bashio
set -e

mkdir -p "${TIKTOK_SHOP_DADOS}"

bashio::log.info "Leitura TikTok Shop - versao ${TIKTOK_SHOP_VERSAO}"
bashio::log.info "dados em ${TIKTOK_SHOP_DADOS}"

if [ ! -f "${TIKTOK_SHOP_DADOS}/tiktok.json" ]; then
  bashio::log.warning "Sem tiktok.json em ${TIKTOK_SHOP_DADOS}."
  bashio::log.warning "Copie tiktok.json e a pasta .tiktok_contas para la."
  bashio::log.warning "Ate isso, a tela sobe e diz que nao ha conta conectada."
fi

# O RELOGIO E O SERVIDOR, os dois em segundo plano. "set -e" nao cobre
# processo em background: se so o relogio morrer (a doc do add-on avisa dos
# 4 GB divididos com o Home Assistant), o servidor ficava de pe sozinho, o
# watchdog via ele vivo e ficava verde, e a leitura parava pra sempre sem
# ninguem notar. "wait -n" devolve assim que QUALQUER um dos dois cair, e o
# "exit" com o codigo dele derruba o container inteiro - e' isso que faz o
# watchdog do HA reiniciar os dois juntos.
python3 /app/painel/relogio_leitura.py &
python3 /app/painel/servidor_leitura.py &
wait -n
exit $?

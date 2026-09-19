#!/usr/bin/with-contenv bashio
set -e

mkdir -p "${TIKTOK_SHOP_DADOS}"

# A hora escolhida na tela do add-on chega ao relogio por aqui. Se a opcao
# faltar (instalacao antiga que ainda nao gravou as opcoes), o proprio relogio
# tem um padrao - variavel vazia nao pode virar "leitura as 0h" por acidente.
export TIKTOK_SHOP_HORA="$(bashio::config 'hora_da_leitura')"

# A versao vem do arquivo ao lado do codigo: o build-arg do Supervisor nunca
# chega (ver servidor_leitura._versao), e o log dizia "desconhecida" sempre.
VERSAO_REAL="$(cat /app/painel/VERSAO 2>/dev/null || echo "${TIKTOK_SHOP_VERSAO}")"
bashio::log.info "Leitura TikTok Shop - versao ${VERSAO_REAL}"
bashio::log.info "leitura automatica todo dia as ${TIKTOK_SHOP_HORA}h"
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

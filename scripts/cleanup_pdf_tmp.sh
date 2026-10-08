#!/bin/bash
# Barre los notepdf_* que hayan podido dejar colgados renders que
# terminaron en timeout o con SIGKILL (worker muerto antes de su finally).
#
# Los workdir se crean en <DATA_ROOT>/pdf_tmp/ desde pdf._pdf_workdir() y se
# borran al final del render con shutil.rmtree; este script es la red de
# seguridad para los casos en los que el worker muere y se salta ese
# finally. Es seguro ejecutarlo mientras gunicorn corre: borra directorios
# con prefijo notepdf_ y solo directorios, no toca nada mas.
#
# Pensado para cron diario (ver /etc/cron.d/cogny-pdf-tmpclean).

set -euo pipefail

ROOT="/var/www/cogny/data/pdf_tmp"
if [[ ! -d "$ROOT" ]]; then
    echo "$(date -Is) pdf_tmpclean: $ROOT no existe, nada que hacer" >&2
    exit 0
fi

# Borra los workdir con mas de 1 dia. 1 dia y no 0 porque el render de una
# boveda muy grande (cientos de MB) puede llegar a tardar varias horas con
# --timeout 300 + cola de gunicorn, y un timeout limpio reintenta y crea
# otro workdir antes de que el original tenga tiempo de limpiarse.
removed=0
while IFS= read -r d; do
    rm -rf -- "$d"
    removed=$((removed + 1))
done < <(find "$ROOT" -maxdepth 1 -mindepth 1 -type d -name 'notepdf_*' -mtime +1 -print 2>/dev/null)

echo "$(date -Is) pdf_tmpclean: borrados $removed directorios de $ROOT" >&2

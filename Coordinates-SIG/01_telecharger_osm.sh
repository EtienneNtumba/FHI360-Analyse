#!/usr/bin/env bash
# Télécharge les trois exports OpenStreetMap RDC utilisés comme référence.
# Source : OpenStreetMap RDC (OSM-RDC), dépôt GitHub opendatalabrdc/OSM_Exports
# Données OpenStreetMap du 2019-11-05, licence ODbL.
set -euo pipefail

BASE="https://github.com/opendatalabrdc/osm_exports/raw/master/data"
mkdir -p sources_osm

for f in osm_rd_congo_poi_health.geojson osm_rd_congo_poi_education.geojson rd_congo_localities.geojson; do
  echo "Téléchargement de $f"
  curl -sSL -o "sources_osm/$f" "$BASE/$f"
done

ls -lh sources_osm
echo
echo "Rappel : ces exports datent de 2019. Ils servent de contrôle, pas de vérité."
echo "Pour des données récentes, voir la section Sources du README (GRID3 v9.0, DHIS2 SNIS)."

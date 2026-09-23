# Coordonnées des sites de la riposte BVD, Ituri

Chaîne reproductible qui part de la liste de sites telle qu'elle a été fournie, la confronte aux
données publiques accessibles, et produit un tableau où chaque coordonnée porte sa source et son
niveau de fiabilité.

État actuel : 54 sites, 41 avec une coordonnée retenue, 13 à relever.
Aucune de ces coordonnées n'est un relevé GPS effectué sur place. Ce sont des valeurs héritées,
contrôlées ou proposées. Le relevé terrain reste la seule source qui fait foi.

## Contenu

| Fichier | Rôle |
|---|---|
| `sites_bruts.csv` | La liste d'origine, 54 lignes, casse et orthographe inchangées |
| `decisions.csv` | Les arbitrages : pour chaque site, ce qu'on garde, remplace, complète ou relève |
| `01_telecharger_osm.sh` | Télécharge les trois exports OpenStreetMap RDC |
| `02_extraire_references.py` | Cherche dans OSM les points dont le nom ressemble à chaque site |
| `03_construire_tableau.py` | Assemble la liste brute et les arbitrages en un tableau final |
| `04_verifier_grid3.py` | Confronte les coordonnées retenues aux couches GRID3 |
| `05_carte_html.py` | Produit une carte HTML autonome des sites retenus |
| `vendor/` | Leaflet 1.9.4 (licence BSD-2-Clause), intégré dans la carte |
| `sorties/candidats_osm.csv` | Les candidats trouvés par l'étape 2, avec score de nom et distance |
| `sorties/coordonnees_ituri.csv` | Le tableau final |
| `sorties/carte_ituri.html` | La carte, à ouvrir dans un navigateur |

## Prérequis

```bash
python3 -m pip install pandas geopandas   # geopandas seulement pour l'étape 4
```

`curl` est nécessaire pour l'étape 1.

## Enchaînement

```bash
bash 01_telecharger_osm.sh                 # remplit sources_osm/
python3 02_extraire_references.py          # écrit sorties/candidats_osm.csv
# ouvrir sorties/candidats_osm.csv, arbitrer, reporter dans decisions.csv
python3 03_construire_tableau.py           # écrit sorties/coordonnees_ituri.csv
python3 04_verifier_grid3.py \
  --sites sorties/coordonnees_ituri.csv \
  --zones <zones_de_sante_GRID3> --champ-zone <colonne> \
  --fosa <structures_GRID3> --champ-nom <colonne>

python3 05_carte_html.py --leaflet vendor   # écrit sorties/carte_ituri.html
```

L'étape 2 propose, elle ne tranche pas. L'étape 3 ne fait qu'appliquer `decisions.csv` : si un
arbitrage change, il se change dans ce fichier, pas dans le code.

L'étape 4 demande les couches GRID3, qui ne sont pas redistribuées ici. Lancée sans `--champ-zone`
ni `--champ-nom`, elle affiche les colonnes disponibles des couches.

L'étape 5 produit une page unique : chaque site est un point cliquable étiqueté avec son nom, coloré
selon la fiabilité de sa position, filtrable par zone de santé. Le fond satellite sert à vérifier
qu'un point tombe sur une emprise bâtie. Avec `--leaflet vendor`, la bibliothèque est intégrée au
fichier : seules les tuiles de fond exigent une connexion, les points et les noms restent lisibles
hors ligne.

## Sources

### 1. La liste d'origine

54 lignes fournies au format zone de santé, nom du site, latitude, longitude. Trente-deux lignes
portaient une coordonnée. Aucune n'était accompagnée d'une source ni d'une date. Le nombre de
décimales suggère des origines différentes : les valeurs à sept décimales et plus ressemblent à des
relevés d'appareil, celles à quatre ou cinq décimales à des valeurs recopiées d'une base ou d'une
carte. Plusieurs coïncident au mètre près avec des points de village, ce qui indique un géocodage
par localité et non un relevé devant la structure.

### 2. OpenStreetMap RDC, export du 5 novembre 2019

Dépôt : <https://github.com/opendatalabrdc/OSM_Exports>, dossier `data`.
Fichiers utilisés : structures de santé, établissements d'enseignement, localités. Licence ODbL,
attribution OpenStreetMap obligatoire en cas de diffusion.

C'est la seule source de points précise que la chaîne télécharge automatiquement. Limites : export
de 2019, couverture inégale, Bunia presque vide, les structures ouvertes pour la riposte 2026 en
sont évidemment absentes. Le fichier santé porte en interne un titre « POI Éducation », erreur de
l'éditeur, son contenu est bien sanitaire.

### 3. GRID3, version 9.0

Portail : <https://data.grid3.org>, miroir sur <https://data.humdata.org>.
Couches utiles : structures de santé v9.0 (août 2026), aires de santé v9.0, zones de santé v9.0, et
le paquet Ituri publié en juillet 2026 pour la riposte. Licence CC BY 4.0. Ce paquet harmonise les
données de plus de trente organisations, dont l'OMS, l'UNICEF, MSF, OCHA et les équipes sanitaires
provinciales. Produit dans l'urgence, il peut comporter des omissions.

Non téléchargé par la chaîne : les fichiers sont volumineux et le portail demande une navigation
manuelle. C'est la première comparaison à faire, via l'étape 4.

### 4. DHIS2 du SNIS, accès par la DPS Ituri

Pour les identifiants officiels des structures et leurs coordonnées quand elles sont renseignées.
Les coordonnées y sont en GeoJSON, longitude d'abord.

```bash
# identifiant de la zone de santé
curl -sg -u "$USER_SNIS:$PASS_SNIS" \
  "$DHIS2/api/organisationUnits.json?filter=name:ilike:nyankunde&fields=id,name,level&paging=false"

# structures de la zone, en CSV : aire de santé, nom, latitude, longitude, identifiant
curl -sg -u "$USER_SNIS:$PASS_SNIS" \
  "$DHIS2/api/organisationUnits.json?filter=path:like:UID_ZONE&fields=id,name,geometry,parent[name]&paging=false" \
  | jq -r '.organisationUnits[] | select(.geometry.type=="Point")
           | [.parent.name, .name, .geometry.coordinates[1], .geometry.coordinates[0], .id] | @csv'
```

### 5. Sources documentaires utilisées pour interpréter, pas pour produire des coordonnées

- Radio Okapi, 5 août 2026 : centre de traitement de 100 lits inauguré à Rwankole, près de Bunia.
- Ouragan.cd, août 2026 : ce centre est implanté dans l'enceinte de l'hôpital de Rwankole. C'est ce
  qui justifie de retenir, pour `CTE Rwankole`, les coordonnées de la ligne `Rwankole Centre
  Hospalier` de la liste d'origine.
- Actualite.cd, juin 2026 : centre de traitement de 42 lits installé dans les bâtiments du Centre
  médical évangélique de Bunia. C'est probablement la ligne `CME`.
- OMS AFRO, septembre 2026 : 25 structures de prise en charge en Ituri au 1er septembre, dont 15
  centres de traitement et 10 centres de transit, dans 19 zones de santé. La liste complète, avec
  coordonnées, est détenue par la commission prise en charge du COUSP et l'équipe de gestion de
  l'information de l'OMS à Bunia.
- ALIMA, septembre 2026 : centres de traitement de Rwampara, CME-Bunia, Nizi et Lita.
- Wikipédia, <https://en.wikipedia.org/wiki/Nia_Nia> : localité de Nia-Nia, 1.407138, 27.607355.
  Une autre source la place à 1.4260, 27.6164, soit 2,3 km plus loin.

## Lire le tableau final

| Colonne | Contenu |
|---|---|
| `province`, `zone_sante`, `site` | identité du site, zone harmonisée en casse normale |
| `zone_sante_origine` | la zone telle qu'écrite dans la liste d'origine |
| `type` | type déduit du nom : HGR, CSR, CS, PS, CT, CTE, ou à préciser |
| `latitude`, `longitude` | la valeur d'origine, jamais modifiée |
| `latitude_retenue`, `longitude_retenue` | la valeur à utiliser aujourd'hui |
| `source_retenue` | d'où vient cette valeur |
| `fiabilite` | voir ci-dessous |
| `action` | garder, remplacer, completer, relever |
| `reference_utilisee` | le point OSM qui a servi de contrôle ou de remplacement |
| `ecart_origine_reference_m` | distance entre la valeur d'origine et cette référence |
| `commentaire` | ce qui a été constaté et ce qu'il reste à faire |
| `source_terrain`, `date_releve` | colonnes vides, à remplir après le relevé |

Niveaux de fiabilité :

- **bonne** : la valeur tombe sur l'emprise de la structure cartographiée. Une seule ligne, HGR Bunia.
- **moyenne** : un point nommé et cohérent existe, mais rien ne prouve qu'il vise le bon bâtiment.
- **faible** : position de village, de ville ou de chef-lieu, ou point dont l'identité reste douteuse.
  Marge de quelques centaines de mètres à deux kilomètres.
- **inconnue** : valeur d'origine sans aucune référence pour la contrôler.
- **vide** : aucune coordonnée, ligne à relever.

## Limites connues

1. L'alignement de la liste d'origine a été vérifié sur la version complète à 54 lignes. Deux
   ancrages permettent de le recontrôler après toute manipulation de tableur : `HGR Getty Etat` doit
   porter 1.208943535 / 30.17427439 et `CSR de Nana` 1.42773 / 30.47389.
2. Les structures ouvertes pour la riposte 2026 (CT, CTE) n'existent dans aucun registre antérieur.
   Seules la liste de la commission prise en charge et le relevé terrain les donnent.
3. `ISTM Nyakunde` est rattaché à la zone de Nyankunde dans la liste, mais le point cartographié se
   trouve à Bunia. À trancher avant usage.
4. Quatre lignes n'ont pas de nom de site (Aru, Logo, Komanda, Niania). La coordonnée retenue y est
   le chef-lieu de la zone, ce qui ne remplace pas un site.
5. Les coordonnées des centres de traitement et de transit ne doivent pas figurer dans les exports
   partenaires ni dans une diffusion publique.

## Ce qui reste à faire

1. Lancer l'étape 4 sur GRID3 v9.0 et arbitrer les divergences dans `decisions.csv`.
2. Demander aux bureaux centraux de zone de Bunia, Rwampara, Nizi et Nyankunde leur liste de
   structures par aire de santé, qui couvre probablement la moitié des 13 lignes à relever.
3. Pour les noms qui sont aussi des noms d'aires de santé (Kigonze, Rwambuzi, Lembabo, Hoho, Uhuru,
   Saio, Bunia-cité), prendre le centroïde de l'aire GRID3 comme position provisoire.
4. Relever sur place. Dans le formulaire Kobo, une question `geopoint` avec la contrainte
   `selected-at(., 3) <= 10` impose une précision de 10 m au plus. Ajouter une photo de l'enseigne et
   le nom exact tel qu'il est écrit. Le relevé se fait à l'entrée de la structure elle-même : pour un
   centre de traitement, l'entrée du centre, pas le portail de l'hôpital qui l'héberge.
5. Reporter chaque relevé dans `source_terrain` et `date_releve`, et passer l'action à `garder`.

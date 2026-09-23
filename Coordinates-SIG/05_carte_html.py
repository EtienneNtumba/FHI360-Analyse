#!/usr/bin/env python3
"""Génère une carte HTML autonome à partir de sorties/coordonnees_ituri.csv.

Chaque site retenu est un point cliquable, étiqueté avec son nom, coloré selon la fiabilité
de sa coordonnée. Deux fonds de carte : plan OpenStreetMap et imagerie satellite, cette
dernière servant à vérifier qu'un point tombe bien sur une emprise bâtie.

Usage :
  python3 05_carte_html.py [--sites sorties/coordonnees_ituri.csv]
                           [--leaflet vendor] [--sortie sorties/carte_ituri.html]

Avec --leaflet, Leaflet est intégré dans le fichier : la carte fonctionne sans accès au CDN,
seules les tuiles de fond exigent une connexion. Sans --leaflet, la page charge Leaflet depuis
unpkg.com.
"""
import argparse
import csv
import json
import os

COULEURS = {
    "bonne": "#2E7D32",
    "moyenne": "#1F4E79",
    "faible": "#EF6C00",
    "inconnue": "#78909C",
}


def famille(fiabilite):
    f = (fiabilite or "").split(" ")[0].strip()
    return f if f in COULEURS else "inconnue"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sites", default="sorties/coordonnees_ituri.csv")
    ap.add_argument("--leaflet", default=None, help="dossier contenant leaflet.js et leaflet.css")
    ap.add_argument("--sortie", default="sorties/carte_ituri.html")
    a = ap.parse_args()

    with open(a.sites, encoding="utf-8-sig") as f:
        lignes = list(csv.DictReader(f))

    points, manquants, groupes = [], [], {}
    for r in lignes:
        nom = r["site"].strip() or f"{r['zone_sante']} (site non nommé)"
        if not r["latitude_retenue"]:
            manquants.append({"zone": r["zone_sante"], "nom": nom, "commentaire": r["commentaire"]})
            continue
        cle = (round(float(r["latitude_retenue"]), 6), round(float(r["longitude_retenue"]), 6))
        fiche = {
            "nom": nom, "zone": r["zone_sante"], "type": r["type"],
            "fiabilite": r["fiabilite"] or "inconnue", "famille": famille(r["fiabilite"]),
            "source": r["source_retenue"], "action": r["action"],
            "origine": f"{r['latitude']}, {r['longitude']}" if r["latitude"] else "",
            "ecart": r["ecart_origine_reference_m"], "commentaire": r["commentaire"],
        }
        if cle in groupes:
            groupes[cle]["fiches"].append(fiche)
        else:
            groupes[cle] = {"lat": cle[0], "lon": cle[1], "fiches": [fiche]}
    points = list(groupes.values())

    zones = sorted({f["zone"] for p in points for f in p["fiches"]})
    if a.leaflet:
        css = open(os.path.join(a.leaflet, "leaflet.css"), encoding="utf-8").read()
        js = open(os.path.join(a.leaflet, "leaflet.js"), encoding="utf-8").read()
        tete = f"<style>{css}</style>\n<script>{js}</script>"
    else:
        tete = ('<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">\n'
                '<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>')

    html = GABARIT.replace("__TETE__", tete)
    html = html.replace("__POINTS__", json.dumps(points, ensure_ascii=False))
    html = html.replace("__MANQUANTS__", json.dumps(manquants, ensure_ascii=False))
    html = html.replace("__ZONES__", json.dumps(zones, ensure_ascii=False))
    html = html.replace("__COULEURS__", json.dumps(COULEURS, ensure_ascii=False))
    html = html.replace("__NB_POINTS__", str(sum(len(p["fiches"]) for p in points)))
    html = html.replace("__NB_MANQUANTS__", str(len(manquants)))

    os.makedirs(os.path.dirname(a.sortie) or ".", exist_ok=True)
    with open(a.sortie, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"{sum(len(p['fiches']) for p in points)} sites cartographiés, {len(manquants)} sans coordonnée")
    print(f"Carte écrite dans {a.sortie}")


GABARIT = """<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Sites de la riposte BVD, Ituri</title>
__TETE__
<style>
  :root { --ardoise:#37474F; --bord:#CFD8DC; }
  * { box-sizing:border-box; }
  html, body { height:100%; margin:0; font-family:"Inter",system-ui,sans-serif; color:var(--ardoise); }
  #page { display:flex; height:100%; }
  #carte { flex:1; }
  #panneau { width:330px; border-left:1px solid var(--bord); overflow-y:auto; padding:16px; background:#FAFAFA; font-size:13px; }
  h1 { font-size:16px; margin:0 0 4px; }
  h2 { font-size:13px; margin:18px 0 6px; text-transform:uppercase; letter-spacing:.04em; color:#607D8B; }
  .compte { color:#607D8B; font-size:12px; margin-bottom:8px; }
  .legende div { display:flex; align-items:center; gap:8px; margin:4px 0; }
  .pastille { width:12px; height:12px; border-radius:50%; border:2px solid #fff; box-shadow:0 0 0 1px rgba(0,0,0,.25); }
  ul { margin:6px 0; padding-left:18px; }
  li { margin:3px 0; }
  .avis { margin-top:18px; padding:10px; background:#FFF3E0; border-left:3px solid #EF6C00; font-size:12px; line-height:1.45; }
  .etiquette { background:rgba(255,255,255,.88); border:1px solid var(--bord); border-radius:3px;
               padding:1px 4px; font-size:11px; font-weight:600; white-space:nowrap; box-shadow:none; }
  .leaflet-tooltip-left.etiquette::before, .leaflet-tooltip-right.etiquette::before { display:none; }
  .popup b { font-size:13px; }
  .popup table { border-collapse:collapse; margin-top:6px; font-size:12px; }
  .popup td { padding:1px 6px 1px 0; vertical-align:top; }
  .popup td:first-child { color:#607D8B; white-space:nowrap; }
  @media (max-width:800px) { #page { flex-direction:column; } #panneau { width:auto; max-height:45%; border-left:none; border-top:1px solid var(--bord); } }
</style>
</head>
<body>
<div id="page">
  <div id="carte"></div>
  <div id="panneau">
    <h1>Sites de la riposte BVD, Ituri</h1>
    <div class="compte">__NB_POINTS__ sites positionnés, __NB_MANQUANTS__ sans coordonnée</div>
    <h2>Fiabilité de la position</h2>
    <div class="legende" id="legende"></div>
    <h2>Zones de santé</h2>
    <div id="zones"></div>
    <h2>Sans coordonnée</h2>
    <ul id="manquants"></ul>
    <div class="avis">
      Aucune de ces positions n'est un relevé GPS de terrain. Vérifier sur le fond satellite que le
      point tombe sur une emprise bâtie, puis relever à l'entrée de la structure.
      Ne pas diffuser les positions des centres de traitement et de transit.
    </div>
  </div>
</div>
<script>
const POINTS = __POINTS__, MANQUANTS = __MANQUANTS__, ZONES = __ZONES__, COULEURS = __COULEURS__;

const carte = L.map("carte", { zoomControl:true }).setView([1.65, 30.15], 8);
const plan = L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
  maxZoom:19, attribution:"&copy; OpenStreetMap"
}).addTo(carte);
const satellite = L.tileLayer(
  "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
  { maxZoom:19, attribution:"Esri, Maxar, Earthstar Geographics" });
L.control.layers({ "Plan OpenStreetMap": plan, "Imagerie satellite": satellite }).addTo(carte);
L.control.scale({ imperial:false }).addTo(carte);

const couches = {};
ZONES.forEach(z => couches[z] = L.layerGroup().addTo(carte));

function popup(p) {
  return '<div class="popup">' + p.fiches.map(f =>
    "<b>" + f.nom + "</b><table>"
    + "<tr><td>Zone</td><td>" + f.zone + "</td></tr>"
    + "<tr><td>Position</td><td>" + p.lat.toFixed(6) + ", " + p.lon.toFixed(6) + "</td></tr>"
    + "<tr><td>Fiabilité</td><td>" + f.fiabilite + "</td></tr>"
    + "<tr><td>Source</td><td>" + f.source + "</td></tr>"
    + (f.origine ? "<tr><td>Valeur d'origine</td><td>" + f.origine + "</td></tr>" : "")
    + (f.ecart ? "<tr><td>Écart mesuré</td><td>" + f.ecart + " m</td></tr>" : "")
    + "<tr><td>Note</td><td>" + f.commentaire + "</td></tr>"
    + "</table>").join("<hr>") + "</div>";
}

const etiquettes = [];
POINTS.forEach(p => {
  const principale = p.fiches[0];
  const marqueur = L.circleMarker([p.lat, p.lon], {
    radius:7, weight:2, color:"#fff",
    fillColor:COULEURS[principale.famille], fillOpacity:1
  }).bindPopup(popup(p), { maxWidth:340 });
  const nom = p.fiches.map(f => f.nom).join(" / ");
  const info = marqueur.bindTooltip(nom, { permanent:true, direction:"right", offset:[8,0], className:"etiquette" });
  marqueur.addTo(couches[principale.zone]);
  etiquettes.push(marqueur);
});

function ajusterEtiquettes() {
  const visible = carte.getZoom() >= 9;
  etiquettes.forEach(m => { const t = m.getTooltip(); if (t) t.setOpacity(visible ? 1 : 0); });
}
carte.on("zoomend", ajusterEtiquettes);
ajusterEtiquettes();

const groupe = L.featureGroup(Object.values(couches).flatMap(c => c.getLayers()));
if (groupe.getLayers().length) carte.fitBounds(groupe.getBounds().pad(0.15));

const legende = document.getElementById("legende");
Object.entries(COULEURS).forEach(([nom, couleur]) => {
  const d = document.createElement("div");
  d.innerHTML = '<span class="pastille" style="background:' + couleur + '"></span><span>' + nom + "</span>";
  legende.appendChild(d);
});

const boite = document.getElementById("zones");
ZONES.forEach(z => {
  const l = document.createElement("label");
  l.style.display = "block";
  l.innerHTML = '<input type="checkbox" checked> ' + z;
  l.querySelector("input").addEventListener("change", e => {
    e.target.checked ? carte.addLayer(couches[z]) : carte.removeLayer(couches[z]);
  });
  boite.appendChild(l);
});

const liste = document.getElementById("manquants");
MANQUANTS.forEach(m => {
  const li = document.createElement("li");
  li.textContent = m.nom + " (" + m.zone + ")";
  li.title = m.commentaire;
  liste.appendChild(li);
});
</script>
</body>
</html>
"""


if __name__ == "__main__":
    main()

# Flight Watch — Paris → Sud Thaïlande & USA

Agent de veille tarifaire qui surveille des allers-retours au départ de
Paris sur les 9 prochains mois (séjours de 14 à 21 nuits) et envoie un mail
dès qu'un AR complet passe sous le budget de la route. Tourne quotidiennement
sur GitHub Actions.

Routes suivies (toutes à 300 € sauf mention contraire, voir `config.py`) :
- Sud Thaïlande : Phuket (HKT), Surat Thani (URT), Krabi (KBV), Bangkok (BKK)
- USA : Miami (MIA), Las Vegas (LAS), New York-JFK (JFK), Los Angeles (LAX),
  Washington-Dulles (IAD), Chicago (ORD)

## Architecture

```
flight_watch/
  config.py            routes, budgets, fenêtre de recherche, durées de séjour
  providers/
    base.py            classe abstraite Provider (une méthode : search())
    travelpayouts.py    source principale, gratuite (Aviasales Data API)
    serpapi.py           source optionnelle (Google Flights via SerpAPI)
  core/
    models.py            dataclass Offer (offre normalisée, quelle que soit la source)
    matrix.py              fenêtre de dates / durées de séjour à scanner
    merge.py                 fusion multi-sources + dédoublonnage
    state.py                  lecture/écriture de l'historique JSON versionné
    alerting.py                règle de déclenchement des alertes
    digest.py                   déclenchement + calcul du récap bi-hebdo
    mailer.py                    rendu HTML + envoi SMTP
  main.py                orchestration du run complet
data/state.json        historique des prix, recommité par le workflow
.github/workflows/flight-watch.yml   cron quotidien + déclenchement manuel
tests/                  tests unitaires (dédoublonnage, alertes, récap)
```

Ajouter une source de prix = ajouter une classe dans `providers/` qui
implémente `Provider.search()`, sans toucher au reste du code.

## Pourquoi seulement 2 sources (pas de GDS type Amadeus)

Vérification faite en septembre 2026 : **Amadeus a fermé tout son portail
Self-Service** (décommissionné le 17 juillet 2026), et **Kiwi.com Tequila
API** est passée en accès partenaire sur candidature uniquement. Il n'existe
plus de GDS gratuit en self-service accessible pour un projet personnel.
`providers/base.py` reste une interface abstraite : si vous obtenez un accès
GDS plus tard (Amadeus Enterprise, ou une autre source), il suffit d'ajouter
une classe dans `providers/` sans rien changer ailleurs.

## Sources de prix

### Travelpayouts / Aviasales Data API (principale, gratuite)

- Couvre AirAsia, Scoot, Thai Vietjet, Nok Air, Thai Lion, etc.
- Endpoint `v2/prices/latest` : prix les moins chers vus en cache par les
  utilisateurs d'Aviasales dans les dernières 48h, filtrés sur la route et la
  fenêtre de dates voulues.
- **Limite à connaître** : ce sont des prix *agrégés/cache*, pas une
  recherche live. Sur des routes peu cherchées (Surat Thani, Krabi depuis
  Paris), certaines dates peuvent n'avoir aucune donnée en cache — ce n'est
  pas un bug, c'est la nature de cette API gratuite.
- L'API de recherche *temps réel* de Travelpayouts existe mais nécessite
  50 000 visiteurs/mois sur un site pour y avoir accès, et interdit
  explicitement l'usage automatisé dans ses CGU — elle n'est donc pas
  utilisée ici.

### SerpAPI Google Flights (optionnelle, désactivée par défaut)

- Agrège quasiment tout (low-cost + GDS + compagnies du Golfe/chinoises/
  turques), donc c'est la seule façon de couvrir les billets longue distance
  maintenant qu'Amadeus est fermé.
- **Désactivée par défaut** (`SERPAPI_ENABLED=false`) car son tier gratuit
  (250 requêtes/mois, tous produits SerpAPI confondus) ne couvre qu'une
  fraction de la matrice complète. Voir calcul de quota ci-dessous avant de
  l'activer.
- Limite technique : SerpAPI ne sépare pas explicitement les segments aller
  et retour dans un aller-retour ; les compagnies sont agrégées et le nombre
  d'escales est reporté en tant que total (aller + retour confondus).

## Créer les comptes API

### Travelpayouts (obligatoire)

1. Créer un compte sur [travelpayouts.com](https://www.travelpayouts.com/)
   (gratuit, aucune carte bancaire).
2. Lors de l'inscription, créer un "Project" (site, blog, app, page
   sociale...) — c'est une formalité de la plateforme, ce n'est pas une
   véritable condition d'usage pour la Data API (contrairement à l'API de
   recherche temps réel qui exige 50 000 visiteurs/mois).
3. Récupérer le token API sur
   [travelpayouts.com/developers/api](https://www.travelpayouts.com/developers/api).
4. Le mettre dans le secret GitHub `TRAVELPAYOUTS_TOKEN`.

### SerpAPI (optionnel)

1. Créer un compte sur [serpapi.com](https://serpapi.com/) — 250 requêtes
   gratuites/mois à l'inscription.
2. Récupérer la clé API sur le dashboard.
3. La mettre dans le secret GitHub `SERPAPI_API_KEY`.
4. Activer la source en mettant la variable de repo (Settings → Secrets and
   variables → Actions → Variables) `SERPAPI_ENABLED` à `true`. Elle reste
   `false` par défaut si non définie.

### SMTP (obligatoire, pour l'envoi des mails)

N'importe quel compte SMTP fonctionne (Gmail avec un mot de passe
d'application, un compte transactionnel type Brevo/Mailjet, etc.).

## Secrets à définir sur GitHub

Repo → Settings → Secrets and variables → Actions :

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `TRAVELPAYOUTS_TOKEN` | secret | oui | Token Travelpayouts |
| `SERPAPI_API_KEY` | secret | non | Clé SerpAPI, si activé |
| `SERPAPI_ENABLED` | variable | non | `true` pour activer SerpAPI (défaut : désactivé) |
| `SMTP_HOST` | secret | oui | Hôte SMTP |
| `SMTP_PORT` | secret | oui | Port SMTP (587 en général) |
| `SMTP_USERNAME` | secret | oui | Identifiant SMTP |
| `SMTP_PASSWORD` | secret | oui | Mot de passe / mot de passe d'application |
| `MAIL_FROM` | secret | oui | Adresse expéditeur |
| `MAIL_TO` | secret | oui | Adresse destinataire (la vôtre) |

Le workflow a besoin de la permission `contents: write` (déjà configurée
dans `.github/workflows/flight-watch.yml`) pour recommiter
`data/state.json` après chaque run.

## Calcul du quota d'appels par exécution

**Travelpayouts** : 10 routes × 2 durées de séjour (14 et 21 nuits) = **20
appels HTTP par run**, un par route/durée (`v2/prices/latest` retourne
jusqu'à `limit` résultats en un seul appel, pas un appel par date). En cron
quotidien : ~600 appels/mois. Très largement sous les limites par défaut de
Travelpayouts (des centaines de requêtes/minute).

**SerpAPI** (si activé) : le nombre de dates de départ possibles dans la
fenêtre (9 mois, pas de 7 jours) est d'environ 39 par route. Avec 10 routes ×
2 durées, la matrice complète représenterait ~780 appels *par run* — bien
trop pour le tier gratuit. C'est pourquoi `SerpApiProvider` échantillonne
avec un budget d'appels configurable (`config.SERPAPI_MAX_CALLS_PER_RUN`,
20 par défaut) partagé entre toutes les combinaisons route/durée d'un run :

- `SERPAPI_MAX_CALLS_PER_RUN=20` (défaut) × cron quotidien = jusqu'à 600
  appels/mois si le budget est toujours consommé → **dépasse le tier
  gratuit (250/mois)**. À réserver à un plan payant, ou à réduire la
  constante.
- Pour rester sous le tier gratuit : descendre `SERPAPI_MAX_CALLS_PER_RUN`
  autour de 8 (8 × 30 ≈ 240/mois).
- Pour une couverture large et fiable : plan payant SerpAPI à partir de
  25 $/mois pour 1000 requêtes, avec `SERPAPI_MAX_CALLS_PER_RUN` remonté en
  conséquence.

## Utilisation locale

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env   # puis renseigner les valeurs
python -m flight_watch.main
```

## Tests

```bash
pip install -r requirements-dev.txt
pytest
```

Couvre : le dédoublonnage/fusion multi-sources (`test_merge.py`), le
parsing des réponses API simulées par provider (`test_providers.py`), la
règle de déclenchement des alertes (`test_alerting.py`), la mise à jour de
l'historique (`test_state.py`) et le déclenchement/calcul du récap bi-hebdo
(`test_digest.py`).

## Workflow GitHub Actions

`.github/workflows/flight-watch.yml` tourne tous les jours à 6h UTC (cron)
et peut être lancé manuellement depuis l'onglet Actions
(`workflow_dispatch`). Après chaque run, `data/state.json` est recommité
automatiquement s'il a changé.

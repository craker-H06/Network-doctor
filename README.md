# Network Doctor

Outil de diagnostic réseau pour un laboratoire ou un réseau d'entreprise que vous administrez. La version 0.1 vérifie une cible explicite, puis contrôle sa disponibilité ICMP.

English summary: Network Doctor is a defensive admin tool. It checks one host you name. It does not discover hosts and it does not scan the Internet.

## Périmètre

L'administrateur fournit l'adresse ou le nom. Le programme refuse :

- une cible vide ;
- une plage réseau ;
- une adresse hors de `ALLOWED_NETWORKS` ;
- une adresse publique, sauf autorisation explicite d'un hôte listé ;
- les adresses multicast, réservées, lien-local et non spécifiées ;
- tout champ JSON autre que `target` et `count`.

Le nombre de paquets est limité à 4. Le délai d'attente est limité à 5 secondes. `ping` est lancé sans shell, avec l'adresse déjà validée.

## État de la V1

| Fonction | État |
| --- | --- |
| Vérification de la cible | Disponible |
| Disponibilité ICMP et latence de la réponse | Disponible |
| Résolution DNS utilisée pour autoriser un nom | Disponible en interne |
| Consultation DNS comme diagnostic séparé | Prévu |
| Ports autorisés | Prévu |
| Informations réseau | Prévu |
| Analyse de route | Prévu |
| Historique SQLite | Prévu |
| Rapport | Prévu |
| Interface web | Disponible : console de laboratoire sur `/` |

Nmap n'est pas encore utilisé. Il entrera avec la vérification de ports, limitée à une liste de ports autorisés.

## Documentation

- [Architecture](docs/architecture.md)
- [Sécurité](docs/securite.md)
- [Politique de signalement](SECURITY.md)

## Prérequis

- Python 3.12 ou plus récent
- `iputils-ping` sur Debian
- Docker et Docker Compose, uniquement si vous lancez le conteneur

## Installation sur Debian

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip iputils-ping
git clone <url-du-depot> network-doctor
cd network-doctor
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
cp .env.example .env
```

Éditez `.env` et inscrivez uniquement les réseaux du laboratoire. Le fichier `.env` reste local : il est ignoré par Git.

Vérifiez ensuite le projet :

```bash
pytest
```

Démarrez l'API sur la machine locale :

```bash
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Contrôlez le service :

```bash
curl -s http://127.0.0.1:8000/health
curl -s -X POST http://127.0.0.1:8000/api/v1/diagnostics/ping \
  -H 'Content-Type: application/json' \
  -d '{"target":"192.168.1.10","count":1}'
```

`192.168.1.10` doit appartenir à `ALLOWED_NETWORKS`. Sinon la réponse est un HTTP 400 et aucun ping n'est envoyé. La console de laboratoire est sur `http://127.0.0.1:8000/`. La documentation de l'API reste sur `http://127.0.0.1:8000/docs`.

Arrêtez le serveur avec `Ctrl+C`. Quittez l'environnement virtuel avec `deactivate`.

## Docker

Le conteneur publie l'API seulement sur la boucle locale et ne garde que la capacité nécessaire à ICMP.

```bash
cp .env.example .env
docker compose up --build
```

Les valeurs par défaut du programme s'appliquent. Pour un autre réseau de laboratoire, ajoutez une section `environment` au service `api` de `docker-compose.yml`, par exemple `ALLOWED_NETWORKS: "192.168.1.0/24"`. Ne passez pas le conteneur en mode privilégié.

Dans le conteneur, `127.0.0.1` désigne le conteneur lui-même. Pour joindre une machine du laboratoire, indiquez son adresse de réseau, présente dans la liste autorisée.

## Variables

| Variable | Défaut | Rôle |
| --- | --- | --- |
| `ALLOWED_NETWORKS` | RFC1918 et `127.0.0.0/8` | Réseaux diagnosticables |
| `ALLOW_PUBLIC_TARGETS` | `false` | Autorise une adresse publique seulement si elle est listée |
| `PING_TIMEOUT_SECONDS` | `2` | Attente par réponse, de 1 à 5 |
| `MAX_PING_COUNT` | `4` | Plafond de paquets, de 1 à 4 |

Une liste vide, un préfixe IPv4 inférieur à `/8`, un préfixe IPv6 inférieur à `/7`, ou `0.0.0.0/0` empêche le démarrage.

## API

`POST /api/v1/diagnostics/ping`

```json
{"target": "10.1.1.1", "count": 1}
```

Réponse lorsque l'hôte répond :

```json
{
  "target": "10.1.1.1",
  "resolved_ip": "10.1.1.1",
  "reachable": true,
  "packets_sent": 1,
  "packets_received": 1,
  "latency_ms": 0.42,
  "detail": "L'hôte répond à ICMP."
}
```

Un hôte autorisé qui ne répond pas produit `reachable: false` avec le statut HTTP 200. Une cible refusée produit le statut 400. Un système qui ne peut pas émettre d'ICMP produit le statut 503.

## Développement

Les fonctions de validation et d'interprétation sont testées sans réseau. Un test supplémentaire ping `127.0.0.1` lorsque la commande `ping` existe.

```bash
pytest
```

La licence est MIT. Voir [LICENSE](LICENSE).

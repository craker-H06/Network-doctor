# Architecture

Network Doctor est une application FastAPI. La version 0.1 expose un seul diagnostic : la disponibilité ICMP d'un hôte nommé par l'administrateur.

## Flux d'une requête

1. `POST /api/v1/diagnostics/ping` reçoit un JSON strict : `target` et, au plus, `count`.
2. Pydantic refuse les champs inconnus, donc aucune option de `ping` ne peut être glissée dans la requête.
3. `prepare_host` contrôle la forme de la cible, résout un nom si besoin, puis ne retient qu'une adresse présente dans `ALLOWED_NETWORKS`.
4. `build_ping_command` fabrique une liste d'arguments fixe. L'adresse canonique est le dernier argument. Le shell n'est pas utilisé.
5. La sortie est traduite en `PingResponse`. Un hôte silencieux reste un résultat HTTP 200. Une cible illégale est un HTTP 400. Un `ping` inutilisable est un HTTP 503.

## Modules

| Module | Rôle |
| --- | --- |
| `app/main.py` | Application, `/health` et console `/` |
| `app/api/routes/diagnostics.py` | Adaptation HTTP |
| `app/schemas/diagnostic.py` | Contrats d'entrée et de sortie |
| `app/core/config.py` | Réglages et bornes |
| `app/services/target_validator.py` | Autorisation de la cible |
| `app/services/ping_service.py` | Exécution et lecture du ping |
| `app/models/` | Réservé à l'historique SQLite |
| `app/templates/` et `app/static/` | Console de laboratoire |

## Hors de cette version

DNS en tant que diagnostic séparé, ports, informations d'interface, traceroute, historique et rapport. La console web couvre le contrôle ICMP. La résolution DNS existe déjà, uniquement pour vérifier qu'un nom pointe vers une adresse autorisée avant le ping.

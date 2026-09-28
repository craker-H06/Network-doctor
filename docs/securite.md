# Sécurité

Network Doctor sert à un administrateur qui connaît déjà la machine ou le nom à contrôler. Il ne découvre pas des hôtes et ne parcourt pas Internet.

## Menaces prises en compte

- Cible vide, trop large, ou remplacée par une plage.
- Adresse publique diagnostiquée par erreur.
- Nom d'hôte qui se résout vers une adresse hors périmètre.
- Caractères transmis à un shell.
- Options de `ping` injectées par un champ JSON supplémentaire.
- Rafale ICMP provoquée par un nombre de paquets ou un délai non borné.
- Liste d'autorisation égale à tout l'Internet (`0.0.0.0/0`, `::/0`, préfixe trop court).

## Contrôles de la version 0.1

- La cible est obligatoire. Il n'existe pas de cible par défaut.
- Seul un hôte est accepté. Tout masque réseau dans la cible est refusé.
- L'adresse doit appartenir à `ALLOWED_NETWORKS`.
- Un préfixe d'autorisation inférieur à `/8` en IPv4, ou à `/7` en IPv6, empêche le démarrage.
- Les adresses non spécifiées, multicast, réservées, lien-local et IPv4-mappées sont refusées.
- `ALLOW_PUBLIC_TARGETS` vaut `false` par défaut. Une adresse publique doit être explicitement listée et le réglage doit être activé.
- Pour un nom, le programme résout d'abord, puis ping l'adresse autorisée. Le nom n'est jamais passé à `ping`.
- `count` est compris entre 1 et 4. Le délai d'attente est compris entre 1 et 5 secondes.
- `subprocess` reçoit une liste d'arguments et `shell` n'est pas activé.
- L'API n'est publiée que sur `127.0.0.1` dans Compose.

## Ce qui reste à la charge de l'administrateur

Choisissez des réseaux que vous administrez. N'exposez pas le port 8000 sur Internet. Sous Docker, la capacité `NET_RAW` est limitée à l'envoi ICMP ; elle ne doit pas être élargie en mode privilégié.

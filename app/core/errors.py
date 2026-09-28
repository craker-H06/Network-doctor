"""Erreurs métier remontées à l'API."""


class NetworkDoctorError(Exception):
    """Erreur applicative dont le message peut être montré à l'administrateur."""


class TargetRejectedError(NetworkDoctorError):
    """La cible est absente, invalide ou hors du périmètre autorisé."""


class PingExecutionError(NetworkDoctorError):
    """Le contrôle ICMP n'a pas pu être exécuté sur cette machine."""

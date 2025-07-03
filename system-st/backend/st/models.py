import uuid
from django.db import models
from django.contrib.auth import get_user_model
from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver
from services.odoo_client import create_odoo_partner

User = get_user_model()

# === PROFIL UTILISATEUR ===
class Profil(models.Model):
    ROLES = [
        ('entrepreneur', 'Entrepreneur'),
        ('consultant', 'Consultant'),
        ('gestionnaire', 'Gestionnaire'),
        ('administrateur', 'Administrateur'),
    ]

    DOMAINES = [
        ('informatique', 'Informatique'),
        ('comptabilite', 'Comptabilité'),
        ('juridique', 'Juridique'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profil')
    role = models.CharField(max_length=20, choices=ROLES, default='entrepreneur')
    domaine = models.CharField(max_length=50, choices=DOMAINES, blank=True, null=True)
    odoo_partner_id = models.IntegerField(null=True, blank=True)
    adresse_livraison = models.TextField(blank=True, null=True)
    adresse_facturation = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.user.username} ({self.role})"

# Crée automatiquement un profil pour chaque nouvel utilisateur
# Synchroniser à la création d’un utilisateur
@receiver(post_save, sender=User)
def create_profil(sender, instance, created, **kwargs):
    if created:
        profil = Profil.objects.create(user=instance)

        try:
            partner_id = create_odoo_partner(instance.username, instance.email, profil.role)

            if partner_id:
                profil.odoo_partner_id = partner_id
                profil.save()

        except Exception as e:
            print(f"Erreur de synchronisation Odoo : {e}")


@receiver(post_save, sender=User)
def save_profil(sender, instance, **kwargs):
    if hasattr(instance, 'profil'):
        instance.profil.save()


# === DEMANDE DE SERVICE ===
class Demande(models.Model):
    STATUT_CHOICES = [
        ('en_attente', 'En attente'),
        ('validee', 'Validée'),
        ('refusee', 'Refusée'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    titre = models.CharField(max_length=255)
    description = models.TextField()
    date_creation = models.DateTimeField(auto_now_add=True)
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default='en_attente')
    entrepreneur = models.ForeignKey(User, on_delete=models.CASCADE, related_name='demandes')

    DOMAINE_CHOICES = [
        ('informatique', 'Informatique'),
        ('comptabilite', 'Comptabilité'),
        ('juridique', 'Juridique'),
        # ajoute d'autres domaines selon besoin
    ]

    consultant_cible = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                         related_name='demandes_reçues')
    domaine = models.CharField(max_length=100, choices=DOMAINE_CHOICES, blank=True, null=True)
    est_publique = models.BooleanField(default=False)
    statut_validation = models.CharField(
        max_length=20,
        choices=[('en_attente', 'En attente'), ('validee', 'Validée'), ('refusee', 'Refusée')],
        default='en_attente'
    ),
    consultants_attribues = models.ManyToManyField(User, related_name='demandes_attribuees', blank=True)

    def __str__(self):
        return self.titre


# === OFFRE DES CONSULTANTS ===
class Offre(models.Model):
    prix = models.FloatField()
    delai = models.CharField(max_length=100)
    statut = models.CharField(
        max_length=20,
        choices=[('soumise', 'Soumise'), ('acceptee', 'Acceptée'), ('refusee', 'Refusée')],
        default='soumise'
    )
    est_reutilisable = models.BooleanField(default=False)
    prestataire = models.ForeignKey(User, on_delete=models.CASCADE, related_name='offres')
    demande = models.ForeignKey(Demande, on_delete=models.CASCADE)
    date_creation = models.DateTimeField(auto_now_add=True)
    bon_commande_odoo_id = models.IntegerField(null=True, blank=True)

    ETAT_CHOICES = [
        ('en_attente', 'En attente'),
        ('en_cours', 'En cours'),
        ('termine', 'Terminé'),
    ]

    etat_avancement = models.CharField(max_length=20, choices=ETAT_CHOICES, default='en_attente')

    def __str__(self):
        return f"Offre de {self.prestataire.username} pour {self.demande.titre} - {self.prix}€"

# == Test notification ==
class Notification(models.Model):
    TYPE_CHOICES = [
        ('offre_soumise', 'Nouvelle offre reçue'),
        ('offre_acceptee', 'Offre acceptée'),
        ('offre_refusee', 'Offre refusée'),
        ('nouvelle_demande', 'Nouvelle demande'),
        ('message_recu', 'Message reçu'),
    ]
    utilisateur = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    type = models.CharField(max_length=50, choices=TYPE_CHOICES)
    contenu = models.TextField()
    date_envoi = models.DateTimeField(auto_now_add=True)
    lu = models.BooleanField(default=False)

    def __str__(self):
        cible = f"→ {self.consultant_cible.username}" if self.consultant_cible else ""
        dom = f"[{self.domaine}]" if self.domaine else ""
        return f"{self.titre} {dom} {cible}".strip()

    def __str__(self):
        return f"{self.utilisateur.username} - {self.type}"

class Message(models.Model):
    auteur = models.ForeignKey(User, on_delete=models.CASCADE, related_name='messages_envoyes')
    destinataire = models.ForeignKey(User, on_delete=models.CASCADE, related_name='messages_recus')
    contenu = models.TextField()
    date_envoi = models.DateTimeField(auto_now_add=True)
    lu = models.BooleanField(default=False)

    def __str__(self):
        return f"De {self.auteur.username} à {self.destinataire.username}"

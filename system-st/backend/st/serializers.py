from rest_framework import serializers
from .models import Demande
from .models import Offre
from .models import Message
from .models import Notification

class DemandeSerializer(serializers.ModelSerializer):
    nombre_offres = serializers.SerializerMethodField()
    entrepreneur_username = serializers.CharField(source='entrepreneur.username', read_only=True)
    consultants_attribues = serializers.PrimaryKeyRelatedField(many=True, read_only=True)

    class Meta:
        model = Demande
        fields = '__all__'
        read_only_fields = ['id', 'date_creation', 'statut', 'entrepreneur']

    def get_nombre_offres(self, obj):
        return Offre.objects.filter(demande=obj).count()

class OffreSerializer(serializers.ModelSerializer):
    #demande = serializers.PrimaryKeyRelatedField(queryset=Demande.objects.all())
    prestataire_username = serializers.CharField(source='prestataire.username', read_only=True)
    demande_titre = serializers.CharField(source='demande.titre', read_only=True)  # ➔ on ajoute cette ligne
    demande_entrepreneur_id = serializers.IntegerField(source='demande.entrepreneur.id', read_only=True)
    demande_entrepreneur_username = serializers.CharField(source='demande.entrepreneur.username', read_only=True)

    class Meta:
        model = Offre
        fields = '__all__'
        read_only_fields = ['prestataire', 'date_creation']

class MessageSerializer(serializers.ModelSerializer):
    auteur_username = serializers.CharField(source='auteur.username', read_only=True)
    destinataire_username = serializers.CharField(source='destinataire.username', read_only=True)

    class Meta:
        model = Message #Notification
        fields = '__all__'
        read_only_fields = ['auteur', 'date_envoi', 'lu']

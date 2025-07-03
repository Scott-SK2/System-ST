from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import api_view, permission_classes, action
from rest_framework.response import Response
from django.db.models import Q
from django.contrib.auth import authenticate, get_user_model
from rest_framework import serializers
from .models import Demande, Offre, Message, Notification
from .serializers import DemandeSerializer, OffreSerializer, MessageSerializer
from rest_framework.permissions import IsAuthenticated
from services.odoo_client import creer_bon_commande_odoo, get_or_create_service_product
from services.odoo_client import delete_odoo_partner

from rest_framework.decorators import api_view

User = get_user_model()

class EmailOrUsernameTokenSerializer(TokenObtainPairSerializer):
    def validate(self, attrs):
        username_or_email = attrs.get("username")
        password = attrs.get("password")

        user = (
            User.objects.filter(email=username_or_email).first()
            or User.objects.filter(username=username_or_email).first()
        )

        if not user:
            raise serializers.ValidationError("Utilisateur introuvable.")

        authenticated_user = authenticate(username=user.username, password=password)

        if not authenticated_user:
            raise serializers.ValidationError("Mot de passe incorrect.")

        return super().validate({"username": user.username, "password": password})


class EmailOrUsernameTokenView(TokenObtainPairView):
    serializer_class = EmailOrUsernameTokenSerializer

# ====================================================
@api_view(['POST'])
def register_user(request):
    data = request.data
    User = get_user_model()

    if User.objects.filter(username=data['username']).exists():
        return Response({'error': 'Nom d’utilisateur déjà utilisé'}, status=400)
    if User.objects.filter(email=data['email']).exists():
        return Response({'error': 'Email déjà utilisé'}, status=400)

    user = User.objects.create_user(
        username=data['username'],
        email=data['email'],
        password=data['password'],
    )
    profil = user.profil
    profil.role = data.get('role', 'entrepreneur')
    if profil.role == 'entrepreneur':
        profil.adresse_livraison = data.get('adresse_livraison')
        profil.adresse_facturation = data.get('adresse_facturation')
    if profil.role == 'consultant':
        profil.domaine = data.get('domaine')
    profil.save()

    # Adresses → à stocker selon ton modèle étendu (à discuter)
    return Response({'message': 'Utilisateur créé'}, status=201)
# ==================== TEST TOKEN ====================
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def test_token(request):
    return Response({
        "message": "Token valide ✅",
        "utilisateur": request.user.username,
        "id": request.user.id,
        "role": request.user.profil.role
    })

# ==================== DEMANDES ====================
class DemandeViewSet(viewsets.ModelViewSet):
    queryset = Demande.objects.all()
    serializer_class = DemandeSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.profil.role in ['gestionnaire', 'administrateur']:
            return Demande.objects.all()
        return Demande.objects.filter(entrepreneur=user)

    def perform_create(self, serializer):
        user = self.request.user
        demande = serializer.save(entrepreneur=user)

        if demande.consultant_cible:
            demande.statut = 'validee'
            demande.save()
            Notification.objects.create(
                utilisateur=demande.consultant_cible,
                type='nouvelle_demande',
                contenu=f"Vous avez été directement ciblé pour « {demande.titre} »"
            )
        elif demande.domaine:
            demande.statut = 'validee'
            demande.est_publique = True
            demande.save()
            consultants = User.objects.filter(profil__role='consultant', profil__domaine=demande.domaine)
            for c in consultants:
                Notification.objects.create(
                    utilisateur=c,
                    type='nouvelle_demande',
                    contenu=f"Nouvelle demande dans votre domaine : {demande.titre}"
                )
        else:
            demande.statut = 'en_attente'
            if demande.statut != 'validee':
                demande.statut = 'validee'
            demande.save()
            gestionnaires = User.objects.filter(profil__role='gestionnaire')
            for g in gestionnaires:
                Notification.objects.create(
                    utilisateur=g,
                    type='nouvelle_demande',
                    contenu=f"Demande ouverte à valider : {demande.titre}"
                )

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def attribuer(self, request, pk=None):
        if request.user.profil.role not in ['gestionnaire', 'administrateur']:
            return Response({"error": "Accès refusé"}, status=403)

        try:
            demande = self.get_object()
            consultants_ids = request.data.get('consultants', [])
            consultants = User.objects.filter(id__in=consultants_ids, profil__role='consultant')
            demande.consultants_attribues.set(consultants)
            demande.save()

            for c in consultants:
                Notification.objects.create(
                    utilisateur=c,
                    type='nouvelle_demande',
                    contenu=f"Vous avez été attribué à la demande « {demande.titre} »"
                )

            return Response({"message": "Demande attribuée avec succès ✅"})
        except Exception as e:
            return Response({"error": str(e)}, status=500)

    def destroy(self, request, *args, **kwargs):
        if request.user.profil.role not in ['gestionnaire', 'administrateur']:
            return Response({"error": "Seul un gestionnaire peut supprimer une demande."}, status=403)
        return super().destroy(request, *args, **kwargs)

# ==================== OFFRES ====================
class OffreViewSet(viewsets.ModelViewSet):
    serializer_class = OffreSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.profil.role == "entrepreneur":
            return Offre.objects.filter(demande__entrepreneur=user)
        if user.profil.role == "consultant":
            return Offre.objects.filter(prestataire=user)
        return Offre.objects.all()

    def perform_create(self, serializer):
        offre = serializer.save(prestataire=self.request.user)
        Notification.objects.create(
            utilisateur=offre.demande.entrepreneur,
            type='offre_soumise',
            contenu=f"{offre.prestataire.username} a soumis une offre pour « {offre.demande.titre} »"
        )

    @action(detail=True, methods=['patch'])
    def accepter(self, request, pk=None):
        offre = self.get_object()
        if offre.demande.entrepreneur != request.user:
            return Response({"error": "Non autorisé."}, status=403)

        offre.statut = 'acceptee'
        offre.save()

        Notification.objects.create(
            utilisateur=offre.prestataire,
            type='offre_acceptee',
            contenu=f"Votre offre pour « {offre.demande.titre} » a été acceptée."
        )

        # Générer automatiquement le bon de commande dans Odoo
        try:
            #from services.odoo_client import get_or_create_service_product, creer_bon_commande_odoo

            product_id = get_or_create_service_product()
            lignes = [{
                "product_id": product_id,
                "product_uom_qty": 1,
                "price_unit": offre.prix,
                "name": f"Réalisation de la demande : {offre.demande.titre}",
            }]

            partner_id = offre.demande.entrepreneur.profil.odoo_partner_id
            bon_commande_id = creer_bon_commande_odoo(partner_id, lignes)
            offre.bon_commande_odoo_id = bon_commande_id
            offre.save()

            print(f"✅ Bon de commande généré : ID {bon_commande_id}")  # utile pour debug

        except Exception as e:
            return Response({"error": f"Offre acceptée mais erreur bon de commande : {str(e)}"})

        return Response({
            "message": "Offre acceptée et bon de commande généré ✅",
            "bon_commande_id": offre.bon_commande_odoo_id
        })

    @action(detail=True, methods=['patch'], permission_classes=[IsAuthenticated])
    def changer_etat(self, request, pk=None):
        offre = self.get_object()
        if offre.prestataire != request.user:
            return Response({"error": "Non autorisé"}, status=403)

        nouvel_etat = request.data.get('etat')
        if nouvel_etat not in ['en_attente', 'en_cours', 'termine']:
            return Response({"error": "État invalide"}, status=400)

        offre.etat_avancement = nouvel_etat
        offre.save()
        return Response({"message": f"État mis à jour : {nouvel_etat}"})

    #A Supprimer
    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def generer_facture(self, request, pk=None):
        offre = self.get_object()

        if request.user != offre.prestataire:
            return Response({"error": "Non autorisé"}, status=403)

            # Vérifie s’il y a déjà une facture
        if offre.facture_odoo_id:
            return Response({"message": "Facture déjà générée", "facture_id": offre.facture_odoo_id})

        product_id = get_or_create_service_product()

        lignes = [{
            "product_id": product_id, #1,  # tu peux définir un produit fixe dans Odoo ou en créer dynamiquement
            "quantity": 1,
            "price_unit": offre.prix,
            "description": f"Réalisation de la demande : {offre.demande.titre}",
        }]
        facture_id = creer_facture_client(offre.demande.entrepreneur.profil.odoo_partner_id, lignes)

        try:
            facture_id = creer_facture_client(offre.demande.entrepreneur.profil.odoo_partner_id, lignes)
            offre.facture_odoo_id = facture_id
            offre.save()

            return Response({"message": "Facture générée ✅", "facture_id": facture_id})
        except Exception as e:
            return Response({"error": str(e)}, status=500)


# ==================== DEMANDES PUBLIQUES ====================
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def demandes_globales(request):
    user = request.user
    if user.profil.role != "consultant":
        return Response({"error": "Consultants uniquement."}, status=403)

    demandes = Demande.objects.filter(
        statut='validee'
    ).filter(
        Q(consultants_attribues__in=[user]) |  # <-- clé ici !
        Q(consultant_cible=user) |
        Q(est_publique=True, domaine=user.profil.domaine)
    ).distinct()

    serializer = DemandeSerializer(demandes, many=True)
    return Response(serializer.data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def demandes_gestionnaire(request):
    if request.user.profil.role not in ['gestionnaire', 'administrateur']:
        return Response({"error": "Accès refusé"}, status=403)
    demandes = Demande.objects.all().order_by('-date_creation')
    serializer = DemandeSerializer(demandes, many=True)
    return Response(serializer.data)

# ==================== VALIDATION ====================
@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def valider_ou_refuser_demande(request, pk):
    try:
        demande = Demande.objects.get(pk=pk)
        action = request.data.get('action')
        consultant_id = request.data.get('consultant')
        domaine = request.data.get('domaine')

        if action == 'valider':
            demande.statut = 'validee'
            demande.save()

            if consultant_id:
                consultant = User.objects.get(id=consultant_id)
                demande.consultants_attribues.set([consultant])
                Notification.objects.create(
                    utilisateur=consultant,
                    type='nouvelle_demande',
                    contenu=f"Vous avez été désigné pour « {demande.titre} »"
                )
            elif domaine:
                consultants = User.objects.filter(profil__role='consultant', profil__domaine=domaine)
                demande.est_publique = True
                demande.domaine = domaine
                demande.save()
                for c in consultants:
                    Notification.objects.create(
                        utilisateur=c,
                        type='nouvelle_demande',
                        contenu=f"Nouvelle demande dans votre domaine : {demande.titre}"
                    )
            else:
                consultants = User.objects.filter(profil__role='consultant')
                for c in consultants:
                    Notification.objects.create(
                        utilisateur=c,
                        type='nouvelle_demande',
                        contenu=f"Nouvelle demande publiée : {demande.titre}"
                    )

        elif action == 'refuser':
            demande.statut = 'refusee'
            demande.save()

        else:
            return Response({"error": "Action inconnue"}, status=400)

        return Response({"message": f"Demande {action} avec succès ✅"})

    except Demande.DoesNotExist:
        return Response({"error": "Demande introuvable"}, status=404)

# ==================== MESSAGES ====================
class MessageViewSet(viewsets.ModelViewSet):
    serializer_class = MessageSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        return Message.objects.filter(Q(auteur=user) | Q(destinataire=user)).order_by('date_envoi')

    def perform_create(self, serializer):
        auteur = self.request.user
        destinataire = serializer.validated_data['destinataire']

        offre_existe = Offre.objects.filter(
            (Q(prestataire=auteur, demande__entrepreneur=destinataire) |
             Q(prestataire=destinataire, demande__entrepreneur=auteur)),
            statut='acceptee'
        ).exists()

        if not offre_existe:
            raise serializers.ValidationError("Vous ne pouvez discuter qu’après acceptation d’une offre.")

        Notification.objects.create(
            utilisateur=destinataire,
            type='message_recu',
            contenu=f"Nouveau message de {auteur.username}"
        )
        serializer.save(auteur=auteur)

# ==================== NOTIFICATIONS ====================
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def mes_notifications(request):
    user = request.user
    notifications = Notification.objects.filter(utilisateur=user).order_by('-date_envoi')
    return Response([{
        "id": n.id,
        "type": n.type,
        "contenu": n.contenu,
        "date_envoi": n.date_envoi,
        "lu": n.lu
    } for n in notifications])

@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def marquer_notification_lue(request, pk):
    try:
        notification = Notification.objects.get(id=pk, utilisateur=request.user)
        notification.lu = True
        notification.save()
        return Response({"message": "Notification lue ✅"})
    except Notification.DoesNotExist:
        return Response({"error": "Notification introuvable"}, status=404)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def liste_consultants(request):
    if request.user.profil.role not in ['gestionnaire', 'entrepreneur', 'administrateur']:
        return Response({"error": "Accès refusé"}, status=403)

    consultants = User.objects.filter(profil__role='consultant')
    data = [{"id": c.id, "username": c.username} for c in consultants]
    return Response(data)

@api_view(['GET', 'POST', 'DELETE'])
@permission_classes([IsAuthenticated])
def gestion_utilisateurs(request):
    if request.user.profil.role != 'administrateur':
        return Response({"error": "Accès refusé"}, status=status.HTTP_403_FORBIDDEN)

    if request.method == 'GET':
        users = User.objects.all()
        data = []
        for u in users:
            profil = getattr(u, 'profil', None)
            data.append({
                "id": u.id,
                "username": u.username,
                "role": profil.role if profil else "",
                "domaine": profil.domaine if profil else ""
            })
        return Response(data)

    elif request.method == 'POST':
        username = request.data.get("username")
        password = request.data.get("password")
        role = request.data.get("role")
        domaine = request.data.get("domaine")

        if not username or not password or not role:
            return Response({"error": "Champs requis manquants"}, status=400)

        if User.objects.filter(username=username).exists():
            return Response({"error": "Ce nom d'utilisateur existe déjà."}, status=400)

        user = User.objects.create_user(username=username, password=password)
        user.profil.role = role

        if role == "consultant" and domaine:
            user.profil.domaine = domaine
        elif domaine:
            return Response({"error": "Seuls les consultants peuvent avoir un domaine."}, status=400)

        user.profil.save()
        return Response({"message": f"Utilisateur {username} créé ✅"}, status=201)

    elif request.method == 'DELETE':
        user_id = request.data.get("id")
        try:
            user = User.objects.get(id=user_id)

            # Supprimer le partenaire Odoo s'il existe
            partner_id = getattr(user.profil, 'odoo_partner_id', None)
            if partner_id:
                delete_odoo_partner(partner_id)

            user.delete()
            return Response({"message": "Utilisateur supprimé ✅"})
        except User.DoesNotExist:
            return Response({"error": "Utilisateur introuvable"}, status=404)

@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def modifier_profil_utilisateur(request):
    admin = request.user
    if not hasattr(admin, 'profil') or admin.profil.role != 'administrateur':
        return Response({"error": "Accès interdit"}, status=403)

    user_id = request.data.get('id')
    nouveau_role = request.data.get('role')
    nouveau_domaine = request.data.get('domaine')

    try:
        cible = get_user_model().objects.get(id=user_id)
        if nouveau_role:
            cible.profil.role = nouveau_role

        if nouveau_domaine is not None:
            if cible.profil.role != 'consultant' and not (nouveau_role == 'consultant'):
                return Response({"error": "Seuls les consultants peuvent avoir un domaine."}, status=400)
            cible.profil.domaine = nouveau_domaine

        cible.profil.save()
        return Response({"message": "Profil mis à jour ✅"})
    except Exception as e:
        return Response({"error": str(e)}, status=500)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def generer_facture_odoo(request):
    data = request.data
    partner_id = data.get('partner_id')
    lignes = data.get('lignes')

    if not partner_id or not lignes:
        return Response({'error': 'Données incomplètes'}, status=400)

    try:
        facture_id = creer_facture_client(partner_id, lignes)
        return Response({'message': 'Facture créée', 'id': facture_id})
    except Exception as e:
        return Response({'error': str(e)}, status=500)

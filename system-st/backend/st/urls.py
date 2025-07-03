from django.urls import path, include
from .views import test_token
from rest_framework.routers import DefaultRouter
from .views import DemandeViewSet, OffreViewSet
from .views import demandes_globales
from .views import MessageViewSet
from .views import mes_notifications
from .views import marquer_notification_lue
from .views import demandes_gestionnaire
from .views import valider_ou_refuser_demande
from .views import liste_consultants
from .views import gestion_utilisateurs
from .views import modifier_profil_utilisateur
from .views import EmailOrUsernameTokenView
from .views import register_user

router = DefaultRouter()
#router.register(r'demandes', DemandeViewSet)
router.register(r'demandes', DemandeViewSet, basename='demande')
router.register(r'offres', OffreViewSet, basename='offre')
router.register(r'messages', MessageViewSet, basename='message')

urlpatterns = [
    path('', include(router.urls)),
    path('test-token/', test_token),
    path('demandes-globales/', demandes_globales, name='demandes_globales'),
    path('notifications/', mes_notifications, name='mes_notifications'),
    path('notifications/<int:pk>/lue/', marquer_notification_lue, name='marquer_notification_lue'),
    path('demandes-gestionnaire/', demandes_gestionnaire, name='demandes_gestionnaire'),
    path('demande/<uuid:pk>/statut/', valider_ou_refuser_demande, name='valider_ou_refuser_demande'),
    path('utilisateurs-consultants/', liste_consultants, name='liste_consultants'),
    path('admin/users/', gestion_utilisateurs, name='gestion_utilisateurs'),
    path('admin/users/modifier-profil/', modifier_profil_utilisateur, name='modifier_profil_utilisateur'),
    path('token/', EmailOrUsernameTokenView.as_view(), name='token_obtain_pair'),
    path('register/', register_user, name='register_user'),

]

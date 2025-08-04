import xmlrpc.client
import os

# Paramètres Odoo (à adapter selon l'environnement)
ODOO_URL = os.getenv('ODOO_URL', '')
ODOO_DB = os.getenv('ODOO_DB', '')
ODOO_USERNAME = os.getenv('ODOO_USERNAME', '')
ODOO_PASSWORD = os.getenv('ODOO_PASSWORD', '')

# 1. Connexion initiale (authentification)
common = xmlrpc.client.ServerProxy(f'{ODOO_URL}/xmlrpc/2/common')
uid = common.authenticate(ODOO_DB, ODOO_USERNAME, ODOO_PASSWORD, {})

# 2. Création de l’objet de communication avec les modèles
models = xmlrpc.client.ServerProxy(f'{ODOO_URL}/xmlrpc/2/object')

def creer_bon_commande_odoo(partner_id, lignes_produits):
    """
    Crée un bon de commande (sale.order) dans Odoo.
    :param partner_id: ID du client
    :param lignes_produits: liste de dicts {product_id, product_uom_qty, price_unit, name}
    """
    try:
        bon_commande_id = models.execute_kw(ODOO_DB, uid, ODOO_PASSWORD,
            'sale.order', 'create', [{
                'partner_id': partner_id,
                'order_line': [
                    (0, 0, {
                        'product_id': ligne['product_id'],
                        'product_uom_qty': ligne['product_uom_qty'],
                        'price_unit': ligne['price_unit'],
                        'name': ligne.get('name', "Prestation de service"),
                    }) for ligne in lignes_produits
                ]
            }]
        )
        return bon_commande_id
    except Exception as e:
        print(f"❌ Erreur création bon de commande Odoo : {e}")
        raise

def create_odoo_partner(name, email, role):
    partner_vals = {
        'name': name,
        'email': email,
        'is_company': False,
        'company_type': 'person',
        'customer_rank': 1 if role == "entrepreneur" else 0,
        'supplier_rank': 1 if role == "consultant" else 0,
    }

    partner_id = models.execute_kw(
        ODOO_DB, uid, ODOO_PASSWORD,
        'res.partner', 'create',
        [partner_vals]
    )
    return partner_id

def delete_odoo_partner(partner_id):
    if not partner_id:
        return
    try:
        models.execute_kw(
            ODOO_DB, uid, ODOO_PASSWORD,
            'res.partner', 'unlink',
            [[partner_id]]
        )
        print(f"🗑️ Partenaire Odoo {partner_id} supprimé")
    except Exception as e:
        print(f"Erreur lors de la suppression dans Odoo : {e}")

def get_or_create_service_product():
    """
    Récupère le produit "Prestation de service", ou le crée s'il n'existe pas.
    Retourne l'ID du produit.
    """
    try:
        # 1. Rechercher un produit déjà existant
        produits = models.execute_kw(
            ODOO_DB, uid, ODOO_PASSWORD,
            'product.product', 'search_read',
            [[['name', '=', 'Prestation de service']]],
            {'fields': ['id'], 'limit': 1}
        )

        if produits:
            return produits[0]['id']

        # 2. Créer le produit si inexistant
        product_id = models.execute_kw(
            ODOO_DB, uid, ODOO_PASSWORD,
            'product.product', 'create',
            [{
                'name': 'Prestation de service',
                'type': 'service',
                'sale_ok': True,
                'purchase_ok': False,
                'list_price': 0.0,
            }]
        )
        return product_id

    except Exception as e:
        print(f"❌ Erreur lors de la création du produit : {e}")
        raise

def test_odoo_connection():
    try:
        common = xmlrpc.client.ServerProxy(f'{ODOO_URL}/xmlrpc/2/common')
        uid = common.authenticate(ODOO_DB, ODOO_USERNAME, ODOO_PASSWORD, {})
        if uid:
            print(f"✅ Connexion réussie à Odoo avec UID {uid}")
            return uid
        else:
            print("❌ Échec de l'authentification.")
            return None
    except Exception as e:
        print(f"❌ Erreur de connexion à Odoo : {e}")
        return None
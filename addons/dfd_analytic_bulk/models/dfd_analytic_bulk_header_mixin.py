# Part of DorFAdoo. See LICENSE file for full copyright and licensing details.
from odoo import models


class DfdAnalyticBulkHeaderMixin(models.AbstractModel):
    """Le champ de distribution analytique posé en en-tête du document.

    Réservé aux modèles où le widget peut prendre le focus sans réveiller le
    module de numérisation des factures — donc les commandes, pas les
    factures. Voir ``dfd.analytic.bulk.mixin`` pour le détail de la panne.

    Sur une commande, ce champ a en plus un sens propre : au moment de passer
    commande, on sait pour quel chantier on achète, et ça se conserve. Il
    complète ``project_id`` sans le remplacer — laissé vide, le comportement
    natif reprend la main.
    """

    _name = 'dfd.analytic.bulk.header.mixin'
    _inherit = ['dfd.analytic.bulk.mixin', 'analytic.mixin']
    _description = "Header Analytic Distribution"

    def _compute_analytic_distribution(self):
        # ``analytic.mixin`` déclare le champ calculé-modifiable et laisse aux
        # modèles concrets le soin de le remplir. Ici il n'y a rien à déduire :
        # un en-tête ne se devine pas, il se saisit. On réassigne la valeur
        # existante pour que le calcul soit défini — c'est ce que fait déjà
        # ``purchase.order.line._compute_analytic_distribution``.
        for record in self:
            record.analytic_distribution = record.analytic_distribution

    def _dfd_header_distribution(self):
        self.ensure_one()
        return self.analytic_distribution

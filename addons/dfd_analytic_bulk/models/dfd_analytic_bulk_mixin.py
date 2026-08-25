# Part of DorFAdoo. See LICENSE file for full copyright and licensing details.
from odoo import _, models
from odoo.exceptions import UserError

# Les seuls modèles autorisés à porter une distribution analytique d'en-tête.
# Le wizard s'y réfère pour refuser tout autre res_model : un oubli ferme, il
# n'ouvre pas.
ALLOWED_MODELS = ('account.move', 'purchase.order', 'sale.order')


class DfdAnalyticBulkMixin(models.AbstractModel):
    """Une distribution analytique posée en en-tête, appliquée d'un geste aux lignes.

    Le champ ``analytic_distribution`` vient de ``analytic.mixin``. Il n'a
    aucun effet comptable propre : rien ne le lit hors le bouton ci-dessous.
    Pas de surcharge de ``_post``, pas de surcharge du moteur analytique, pas
    de champ stocké ajouté sur les lignes.
    """

    _name = 'dfd.analytic.bulk.mixin'
    _inherit = ['analytic.mixin']
    _description = "Header Analytic Distribution"

    def _compute_analytic_distribution(self):
        # ``analytic.mixin`` déclare le champ calculé-modifiable et laisse aux
        # modèles concrets le soin de le remplir. Ici il n'y a rien à déduire :
        # un en-tête ne se devine pas, il se saisit. On réassigne la valeur
        # existante pour que le calcul soit défini — c'est ce que fait déjà
        # ``purchase.order.line._compute_analytic_distribution``.
        for record in self:
            record.analytic_distribution = record.analytic_distribution

    # ------------------------------------------------------------------
    # À redéfinir par chaque modèle
    # ------------------------------------------------------------------

    def _dfd_analytic_target_lines(self):
        """Les lignes que le bouton a le droit de toucher.

        Redéfini modèle par modèle, parce que ``display_type`` ne se lit pas
        pareil de l'un à l'autre : sur ``account.move.line`` une ligne de
        produit vaut ``'product'``, sur les lignes de commande elle ne vaut
        rien du tout. Filtrer partout sur l'absence de ``display_type``
        viderait les factures de toutes leurs lignes.
        """
        raise NotImplementedError

    def _dfd_check_writable(self):
        """Garde-fou propre au modèle, appelé avant toute écriture."""
        return

    # ------------------------------------------------------------------
    # Le bouton
    # ------------------------------------------------------------------

    def action_dfd_apply_analytic(self):
        """Appliquer la distribution d'en-tête aux lignes de produit.

        Si aucune ligne ne porte déjà autre chose, on écrit directement. Sinon
        on ouvre le wizard : une ventilation manuelle ne s'écrase jamais sans
        que quelqu'un l'ait demandé.
        """
        self.ensure_one()
        self._dfd_check_analytic_ready()
        lines = self._dfd_analytic_target_lines()
        if not lines:
            raise UserError(_("This document has no product line to allocate."))

        conflicts = lines.filtered(
            lambda line: line.analytic_distribution
            and line.analytic_distribution != self.analytic_distribution
        )
        if conflicts:
            return self._dfd_open_apply_wizard(len(lines), len(conflicts))
        return self._dfd_apply_analytic(mode='overwrite')

    def _dfd_apply_analytic(self, mode='empty'):
        """Écrire la distribution d'en-tête. Appelé par le bouton et le wizard."""
        self.ensure_one()
        self._dfd_check_analytic_ready()
        lines = self._dfd_analytic_target_lines()
        if mode == 'empty':
            lines = lines.filtered(lambda line: not line.analytic_distribution)
        # Une ligne qui porte déjà exactement la même distribution n'est pas
        # réécrite : chaque écriture fait retirer puis recréer ses écritures
        # analytiques par _inverse_analytic_distribution.
        lines = lines.filtered(
            lambda line: line.analytic_distribution != self.analytic_distribution
        )
        if lines:
            lines.write({'analytic_distribution': self.analytic_distribution})
        return self._dfd_applied_notification(len(lines))

    # ------------------------------------------------------------------
    # Contrôles
    # ------------------------------------------------------------------

    def _dfd_check_analytic_ready(self):
        self.ensure_one()
        if not self.analytic_distribution:
            raise UserError(_("Set the analytic distribution in the header first."))
        self._dfd_check_analytic_company()
        self._dfd_check_writable()

    def _dfd_check_analytic_company(self):
        """Un compte analytique d'une autre société n'a rien à faire sur ces lignes.

        La base compte six sociétés ; rien dans le widget n'empêche de choisir
        le compte de la voisine.
        """
        self.ensure_one()
        account_ids = self._get_analytic_account_ids_from_distributions(
            self.analytic_distribution
        )
        accounts = self.env['account.analytic.account'].browse(sorted(account_ids)).exists()
        foreign = accounts.filtered(
            lambda account: account.company_id and account.company_id != self.company_id
        )
        if foreign:
            raise UserError(_(
                "These analytic accounts belong to another company than %(company)s: %(accounts)s",
                company=self.company_id.display_name,
                accounts=", ".join(foreign.mapped('display_name')),
            ))

    # ------------------------------------------------------------------
    # Retours d'écran
    # ------------------------------------------------------------------

    def _dfd_open_apply_wizard(self, line_count, conflict_count):
        wizard = self.env['dfd.analytic.bulk.apply'].create({
            'res_model': self._name,
            'res_id': self.id,
            'line_count': line_count,
            'conflict_count': conflict_count,
        })
        return {
            'type': 'ir.actions.act_window',
            'name': _("Apply analytic distribution"),
            'res_model': 'dfd.analytic.bulk.apply',
            'res_id': wizard.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def _dfd_applied_notification(self, count):
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'type': 'success',
                'message': _("Analytic distribution applied to %(count)s line(s).", count=count),
                'next': {'type': 'ir.actions.act_window_close'},
            },
        }

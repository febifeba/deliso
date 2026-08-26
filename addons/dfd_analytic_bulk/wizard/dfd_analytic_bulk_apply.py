# Part of DorFAdoo. See LICENSE file for full copyright and licensing details.
from odoo import _, api, fields, models
from odoo.exceptions import AccessError

from ..models.dfd_analytic_bulk_mixin import ALLOWED_MODELS


class DfdAnalyticBulkApply(models.TransientModel):
    """Choisir ce qu'on pose sur les lignes, et demander avant d'écraser.

    Sur une facture, c'est ici que se saisit la distribution : le champ ne peut
    pas vivre en en-tête sans faire planter l'écran de numérisation. Sur une
    commande, elle arrive déjà remplie depuis l'en-tête et l'assistant ne
    s'ouvre que s'il y a du travail manuel à préserver.

    Un champ laissé vide n'est pas touché sur les lignes. C'est la règle qui
    permet de ne poser qu'une taxe sans rien changer d'autre.
    """

    _name = 'dfd.analytic.bulk.apply'
    _inherit = ['analytic.mixin']
    _description = "Allocate Lines to Analytic Accounts"

    res_model = fields.Char(string="Document Model", required=True, readonly=True)
    res_id = fields.Integer(string="Document", required=True, readonly=True)
    line_count = fields.Integer(string="Product Lines", readonly=True)
    conflict_count = fields.Integer(string="Lines Already Allocated", readonly=True)
    message = fields.Char(compute='_compute_message')

    company_id = fields.Many2one('res.company', compute='_compute_document')
    show_accounting_fields = fields.Boolean(compute='_compute_document')
    tax_type = fields.Char(compute='_compute_document')

    account_id = fields.Many2one(
        'account.account',
        string="General Account",
        help="Leave empty to keep the account already on each line.",
    )
    tax_ids = fields.Many2many(
        'account.tax',
        string="Taxes",
        help="Leave empty to keep the taxes already on each line.",
    )

    mode = fields.Selection(
        selection=[
            ('empty', "Only fill in the empty lines"),
            ('overwrite', "Overwrite every line"),
        ],
        string="Scope",
        default='empty',
        required=True,
        help="Applies to the analytic distribution only.",
    )

    # ------------------------------------------------------------------

    def _dfd_document(self):
        self.ensure_one()
        if self.res_model in ALLOWED_MODELS and self.res_id:
            return self.env[self.res_model].browse(self.res_id).exists()
        return None

    def _compute_analytic_distribution(self):
        # Saisie libre : rien à déduire, mais le calcul doit être défini.
        for wizard in self:
            wizard.analytic_distribution = wizard.analytic_distribution

    @api.depends('res_model', 'res_id')
    def _compute_document(self):
        for wizard in self:
            document = wizard._dfd_document()
            wizard.company_id = document.company_id if document else False
            wizard.show_accounting_fields = bool(document) and document._dfd_supports_accounting_fields()
            # Une facture fournisseur appelle des taxes d'achat, une facture
            # client des taxes de vente : proposer les deux mélangées serait
            # une invitation à se tromper.
            if document and document._name == 'account.move':
                wizard.tax_type = 'purchase' if document.move_type in (
                    'in_invoice', 'in_refund', 'in_receipt'
                ) else 'sale'
            else:
                wizard.tax_type = False

    @api.depends('line_count', 'conflict_count')
    def _compute_message(self):
        for wizard in self:
            if wizard.conflict_count:
                wizard.message = _(
                    "%(conflicts)s of the %(total)s product lines are already allocated. "
                    "What should be done with them?",
                    conflicts=wizard.conflict_count,
                    total=wizard.line_count,
                )
            else:
                wizard.message = _(
                    "The analytic distribution will be applied to the %(total)s product lines.",
                    total=wizard.line_count,
                )

    def action_apply(self):
        self.ensure_one()
        # Le bouton est masqué hors du groupe analytique ; le masquage n'est
        # pas un refus, on refuse aussi ici.
        if not self.env.user.has_group('analytic.group_analytic_accounting'):
            raise AccessError(_("You are not allowed to manage analytic accounting."))
        if self.res_model not in ALLOWED_MODELS:
            raise AccessError(_(
                "Model %s does not support bulk analytic allocation.", self.res_model
            ))
        document = self._dfd_document()
        document.check_access('write')
        return document._dfd_apply(
            distribution=self.analytic_distribution,
            mode=self.mode,
            account=self.account_id,
            taxes=self.tax_ids,
        )

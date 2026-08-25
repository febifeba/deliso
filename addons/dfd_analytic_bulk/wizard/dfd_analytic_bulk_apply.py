# Part of DorFAdoo. See LICENSE file for full copyright and licensing details.
from odoo import _, api, fields, models
from odoo.exceptions import AccessError

from ..models.dfd_analytic_bulk_mixin import ALLOWED_MODELS


class DfdAnalyticBulkApply(models.TransientModel):
    """Choisir le chantier, et demander avant d'écraser.

    Sur une facture, c'est ici que se saisit la distribution : le champ ne
    peut pas vivre en en-tête sans faire planter l'écran de numérisation. Sur
    une commande, la distribution arrive déjà remplie depuis l'en-tête et
    l'assistant ne s'ouvre que s'il y a du travail manuel à préserver.

    Une ventilation posée à la main et effacée sans prévenir est la façon la
    plus sûre de perdre la confiance de l'utilisateur : le défaut ne touche
    donc que les lignes vides.
    """

    _name = 'dfd.analytic.bulk.apply'
    _inherit = ['analytic.mixin']
    _description = "Allocate Lines to Analytic Accounts"

    res_model = fields.Char(string="Document Model", required=True, readonly=True)
    res_id = fields.Integer(string="Document", required=True, readonly=True)
    line_count = fields.Integer(string="Product Lines", readonly=True)
    conflict_count = fields.Integer(string="Lines Already Allocated", readonly=True)
    message = fields.Char(compute='_compute_message')
    mode = fields.Selection(
        selection=[
            ('empty', "Only fill in the empty lines"),
            ('overwrite', "Overwrite every line"),
        ],
        string="Scope",
        default='empty',
        required=True,
    )

    def _compute_analytic_distribution(self):
        # Saisie libre : rien à déduire, mais le calcul doit être défini.
        for wizard in self:
            wizard.analytic_distribution = wizard.analytic_distribution

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
        document = self.env[self.res_model].browse(self.res_id)
        document.check_access('write')
        return document._dfd_apply_analytic(self.analytic_distribution, mode=self.mode)

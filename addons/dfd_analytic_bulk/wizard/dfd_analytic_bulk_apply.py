# Part of DorFAdoo. See LICENSE file for full copyright and licensing details.
from odoo import _, api, fields, models
from odoo.exceptions import AccessError

from ..models.dfd_analytic_bulk_mixin import ALLOWED_MODELS


class DfdAnalyticBulkApply(models.TransientModel):
    """Demander avant d'écraser.

    C'est le point de conception le plus important du module : une ventilation
    posée à la main et effacée sans prévenir est la façon la plus sûre de
    perdre la confiance de l'utilisateur. Le défaut ne touche donc que les
    lignes vides.
    """

    _name = 'dfd.analytic.bulk.apply'
    _description = "Apply Analytic Distribution to Lines"

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

    @api.depends('line_count', 'conflict_count')
    def _compute_message(self):
        for wizard in self:
            wizard.message = _(
                "%(conflicts)s of the %(total)s product lines already carry a different "
                "analytic distribution. What should be done with them?",
                conflicts=wizard.conflict_count,
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
                "Model %s does not carry a header analytic distribution.", self.res_model
            ))
        document = self.env[self.res_model].browse(self.res_id)
        document.check_access('write')
        return document._dfd_apply_analytic(mode=self.mode)

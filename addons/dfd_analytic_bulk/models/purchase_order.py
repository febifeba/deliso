# Part of DorFAdoo. See LICENSE file for full copyright and licensing details.
from odoo import models


class PurchaseOrder(models.Model):
    _name = 'purchase.order'
    _inherit = ['purchase.order', 'dfd.analytic.bulk.mixin']

    def _dfd_analytic_target_lines(self):
        # Sur purchase.order.line, display_type ne vaut quelque chose que pour
        # une section, une sous-section ou une note : une ligne ordinaire n'en
        # a pas. C'est l'inverse d'account.move.line.
        return self.order_line.filtered(lambda line: not line.display_type)

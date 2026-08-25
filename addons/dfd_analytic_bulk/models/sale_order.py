# Part of DorFAdoo. See LICENSE file for full copyright and licensing details.
from odoo import models


class SaleOrder(models.Model):
    _name = 'sale.order'
    _inherit = ['sale.order', 'dfd.analytic.bulk.mixin']

    def _dfd_analytic_target_lines(self):
        # Même lecture que sur purchase.order.line : pas de display_type sur
        # une ligne ordinaire.
        return self.order_line.filtered(lambda line: not line.display_type)

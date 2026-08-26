# Part of DorFAdoo. See LICENSE file for full copyright and licensing details.
from odoo import models


class SaleOrder(models.Model):
    _name = 'sale.order'
    _inherit = ['sale.order', 'dfd.analytic.bulk.header.mixin']

    def _dfd_target_lines(self):
        """Ordinary lines only -- same reading as ``purchase.order.line``."""
        return self.order_line.filtered(lambda line: not line.display_type)


class SaleOrderLine(models.Model):
    _name = 'sale.order.line'
    _inherit = ['sale.order.line', 'dfd.analytic.bulk.line.mixin']

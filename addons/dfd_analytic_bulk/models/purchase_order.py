# Part of DorFAdoo. See LICENSE file for full copyright and licensing details.
from odoo import models


class PurchaseOrder(models.Model):
    _name = 'purchase.order'
    _inherit = ['purchase.order', 'dfd.analytic.bulk.header.mixin']

    def _dfd_target_lines(self):
        """Ordinary lines only.

        On ``purchase.order.line``, ``display_type`` holds a value only for a
        section, a subsection or a note: an ordinary line has none. That is
        the exact opposite of ``account.move.line``.
        """
        return self.order_line.filtered(lambda line: not line.display_type)


class PurchaseOrderLine(models.Model):
    _name = 'purchase.order.line'
    _inherit = ['purchase.order.line', 'dfd.analytic.bulk.line.mixin']

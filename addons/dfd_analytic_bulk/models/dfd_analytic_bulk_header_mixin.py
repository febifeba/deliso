# Part of DorFAdoo. See LICENSE file for full copyright and licensing details.
from odoo import models


class DfdAnalyticBulkHeaderMixin(models.AbstractModel):
    """The analytic distribution field, carried in the document header.

    Reserved for the models where the widget can take focus without waking
    the invoice digitisation module -- so orders, never invoices. See
    ``dfd.analytic.bulk.mixin`` for the details of that crash.

    On an order the field also carries meaning of its own: at ordering time
    you already know which site you are buying for, and the field keeps it. It
    complements ``project_id`` rather than replacing it -- left empty, Odoo's
    native cascade takes over again.
    """

    _name = 'dfd.analytic.bulk.header.mixin'
    _inherit = ['dfd.analytic.bulk.mixin', 'analytic.mixin']
    _description = "Header Analytic Distribution"

    def _compute_analytic_distribution(self):
        """Define the compute ``analytic.mixin`` leaves to concrete models.

        There is nothing to infer here: a header is not guessed, it is typed.
        Reassigning the existing value keeps the compute well defined -- the
        same thing ``purchase.order.line._compute_analytic_distribution``
        does for the lines it does not touch.
        """
        for record in self:
            record.analytic_distribution = record.analytic_distribution

    def _dfd_header_distribution(self):
        self.ensure_one()
        return self.analytic_distribution

# Part of DorFAdoo. See LICENSE file for full copyright and licensing details.
from odoo import models


class AccountMove(models.Model):
    # Deliberately NOT dfd.analytic.bulk.header.mixin: an analytic_distribution
    # field in an invoice header breaks the form as soon as it takes focus,
    # whenever account_invoice_extract is installed. The distribution is typed
    # into the wizard instead. See dfd.analytic.bulk.mixin for the trace.
    _name = 'account.move'
    _inherit = ['account.move', 'dfd.analytic.bulk.mixin']

    def _dfd_target_lines(self):
        """Product lines only.

        On ``account.move.line`` a product line carries ``display_type ==
        'product'``. Tax lines, the payable counterpart, rounding, early
        payment discounts, sections and notes are all excluded by that single
        test.
        """
        return self.line_ids.filtered(lambda line: line.display_type == 'product')

    def _dfd_supports_accounting_fields(self):
        """Allow a general account and taxes on draft invoices only.

        Two distinct reasons, not one. Odoo refuses outright to change the
        taxes of a posted journal item ("You cannot modify the taxes related
        to a posted journal item"). The account would go through -- but
        changing it on a reconciled line **unreconciles** the entry, undoing a
        bank reconciliation nobody asked to undo. A Peppol bill that has just
        arrived is in draft anyway.
        """
        self.ensure_one()
        return self.state == 'draft'

    def _dfd_check_writable(self):
        """Refuse a posted entry sitting in a locked accounting period.

        Odoo does **not** protect ``analytic_distribution`` with the lock
        dates: ``_get_lock_date_protected_fields()`` lists only ``balance``,
        ``tax_line_id``, ``tax_ids``, ``tax_tag_ids``, ``account_id``,
        ``journal_id``, ``amount_currency``, ``currency_id`` and
        ``partner_id``. Rewriting the analytic distribution of a posted entry
        in a closed period would therefore go through without a word, and
        ``_inverse_analytic_distribution`` would regenerate the analytic
        entries along the way.

        The guard is placed here for want of one on the other side. Note the
        consequence: this button is **stricter than Odoo's own list
        multi-edit**, which still lets it through. The two accounting fields
        above need no such guard -- the lock dates already protect them.
        """
        self.filtered(lambda move: move.state == 'posted')._check_fiscal_lock_dates()

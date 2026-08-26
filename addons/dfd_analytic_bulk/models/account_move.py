# Part of DorFAdoo. See LICENSE file for full copyright and licensing details.
from odoo import _, models
from odoo.exceptions import UserError


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

    # ------------------------------------------------------------------
    # Emptying the lines tab in one gesture
    # ------------------------------------------------------------------

    def action_dfd_clear_lines(self):
        """Delete every line of the Invoice Lines tab at once.

        A Peppol bill arrives with its hundred lines already read from the
        XML. Linking a purchase order afterwards -- with *Auto-Complete* --
        does not replace them: it **adds** the order's lines underneath. The
        document then carries the same goods twice, and the only native way
        out is the little bin, one line at a time, a hundred times.

        Everything the tab shows goes: product lines, sections, subsections
        and notes -- that is exactly the domain of ``invoice_line_ids``. Tax
        lines, the payable counterpart, rounding and early payment discounts
        are not touched; Odoo recomputes them from what is left.

        Draft only. The screen hides the button elsewhere, and this refuses it
        again: hiding a button closes nothing, the method is callable by
        anyone who can read the code.

        :return: a notification action
        :raise UserError: when the document is not a draft, or has no line
        """
        self.ensure_one()
        if self.state != 'draft':
            raise UserError(_("Only a draft document can have its lines emptied."))

        lines = self.invoice_line_ids
        if not lines:
            raise UserError(_("This document has no line to delete."))

        count = len(lines)
        lines.unlink()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'type': 'success',
                'message': _("%(count)s line(s) deleted.", count=count),
                'next': {'type': 'ir.actions.act_window_close'},
            },
        }

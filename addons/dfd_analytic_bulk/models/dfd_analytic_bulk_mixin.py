# Part of DorFAdoo. See LICENSE file for full copyright and licensing details.
from odoo import Command, _, models
from odoo.exceptions import UserError

# The only models allowed to carry the bulk allocation button. The wizard
# checks the incoming ``res_model`` against this list: hiding a button in a
# view is not a refusal, so the server refuses too. An omission closes the
# door, it never opens it.
ALLOWED_MODELS = ('account.move', 'purchase.order', 'sale.order')


class DfdAnalyticBulkMixin(models.AbstractModel):
    """Apply values to every product line of a document in one gesture.

    This mixin deliberately declares **no field at all**. On ``account.move``,
    an ``analytic_distribution`` field in the header breaks the form: the
    widget focuses itself when it renders, and the Enterprise invoice
    digitisation module (``account_invoice_extract``) intercepts that focus to
    highlight the matching box on the scanned document. It looks the field up
    in its own mapping table, does not find it, and raises::

        TypeError: Cannot read properties of undefined (reading 'fields')
            at InvoiceExtractFormRenderer.getBoxType

    Proven on 25 August 2026 against an Odoo 19 Enterprise staging database.
    The very same field in the header of a purchase order causes no trouble --
    purchases have no digitisation. The fault is in the interaction, not in
    the widget. Removing the header field also brought Odoo's own per-line
    analytic entry back to life: it was breaking too.

    Models that can safely carry the header field inherit
    ``dfd.analytic.bulk.header.mixin`` on top of this one. On an invoice, the
    distribution is typed into the wizard instead.

    Concrete models must override :meth:`_dfd_target_lines`. They may override
    :meth:`_dfd_check_writable`, :meth:`_dfd_header_distribution` and
    :meth:`_dfd_supports_accounting_fields`.
    """

    _name = 'dfd.analytic.bulk.mixin'
    _description = "Bulk Analytic Allocation"

    # ------------------------------------------------------------------
    # Hooks -- overridden per model
    # ------------------------------------------------------------------

    def _dfd_target_lines(self):
        """Return the lines the button is allowed to write on.

        Overridden model by model, because ``display_type`` does not read the
        same way from one to the next: on ``account.move.line`` a product line
        holds ``'product'``, whereas on order lines an ordinary line holds
        nothing at all and only sections and notes carry a value. Filtering on
        the absence of ``display_type`` everywhere would empty every invoice
        of all its lines.

        :return: a recordset of lines belonging to ``self``
        """
        raise NotImplementedError

    def _dfd_check_writable(self):
        """Raise if this document must not be written on at all.

        A no-op here. ``account.move`` uses it to refuse a posted entry that
        falls inside a locked accounting period.
        """
        return

    def _dfd_header_distribution(self):
        """Return the analytic distribution typed in the document header.

        Empty here: the wizard will ask for it. Models carrying
        ``dfd.analytic.bulk.header.mixin`` return their own field instead.

        :return: an analytic distribution dict, or ``False``
        """
        return False

    def _dfd_supports_accounting_fields(self):
        """Return whether a general account and taxes may be set on the lines.

        ``False`` here. Order lines have no general account -- it only appears
        at invoicing -- and forcing a tax on an order is pointless: it comes
        from the product and the vendor.
        """
        return False

    # ------------------------------------------------------------------
    # The button
    # ------------------------------------------------------------------

    def action_dfd_apply_analytic(self):
        """Entry point of the "Allocate lines" button.

        Writes straight away only when the header already carries a
        distribution, no line is allocated yet, and the document accepts
        nothing else. In every other case the wizard opens: either the
        distribution is missing, or manual work is at stake and must not be
        overwritten in silence.

        The button stays visible even when nothing is filled in yet. Hiding it
        until the header was set made the whole feature undiscoverable on
        orders -- nobody guesses that a field must be filled for a button to
        appear.

        :return: an ``ir.actions`` dict: the wizard, or a notification
        :raise UserError: when the document has no product line
        """
        self.ensure_one()
        self._dfd_check_writable()

        lines = self._dfd_target_lines()
        if not lines:
            raise UserError(_("This document has no product line to allocate."))

        distribution = self._dfd_header_distribution()
        already_allocated = lines.filtered(lambda line: line.analytic_distribution)

        if distribution and not already_allocated and not self._dfd_supports_accounting_fields():
            return self._dfd_apply(distribution, mode='overwrite')
        return self._dfd_open_apply_wizard(distribution, len(lines), len(already_allocated))

    def _dfd_apply(self, distribution=False, mode='empty', account=False, taxes=None):
        """Write the given values on the product lines. An empty value is left alone.

        That rule is what lets a user fix a tax without undoing the accounts,
        or an account without undoing a hand-made analytic allocation.

        ``mode`` governs the **analytic distribution only**. That is where a
        hand-made allocation deserves to be preserved. A general account is
        mandatory on every line -- none is ever empty, so "only fill in the
        empty lines" would mean nothing there. Once given, it applies to all
        of them.

        :param dict distribution: analytic distribution, or ``False`` to leave
            each line's own distribution untouched
        :param str mode: ``'empty'`` to fill only unallocated lines,
            ``'overwrite'`` to replace every one
        :param account: an ``account.account`` record, or ``False``
        :param taxes: an ``account.tax`` recordset, or ``None``
        :return: a notification action
        :raise UserError: when nothing was given, or when the document does
            not accept a general account and taxes
        """
        self.ensure_one()
        if not distribution and not account and not taxes:
            raise UserError(_("Fill in at least one value to apply."))
        self._dfd_check_writable()

        lines = self._dfd_target_lines()
        touched = lines.browse()

        if distribution:
            self._dfd_check_analytic_company(distribution)
            targets = lines if mode == 'overwrite' else lines.filtered(
                lambda line: not line.analytic_distribution
            )
            # A line already carrying exactly this distribution is not
            # rewritten: every write makes _inverse_analytic_distribution
            # unlink and recreate its analytic entries, which is wasted work
            # on a fifty-line Peppol bill.
            targets = targets.filtered(lambda line: line.analytic_distribution != distribution)
            if targets:
                targets.write({'analytic_distribution': distribution})
            touched |= targets

        if account or taxes:
            if not self._dfd_supports_accounting_fields():
                raise UserError(_("This document does not accept a general account or taxes."))
            values = {}
            if account:
                values['account_id'] = account.id
            if taxes:
                values['tax_ids'] = [Command.set(taxes.ids)]
            # Odoo's own write() skips the lines whose values would not
            # change, so there is nothing to filter here.
            lines.write(values)
            touched |= lines

        return self._dfd_applied_notification(len(touched))

    # ------------------------------------------------------------------
    # Guards
    # ------------------------------------------------------------------

    def _dfd_check_analytic_company(self, distribution):
        """Refuse an analytic account belonging to another company.

        Deliso runs six companies and nothing in the widget prevents picking
        the neighbour's account. Unlike ``account_id`` and ``tax_ids``, which
        Odoo guards natively with ``check_company=True``,
        ``analytic_distribution`` carries no such protection.

        :param dict distribution: the distribution about to be written
        :raise UserError: when at least one account belongs to another company
        """
        self.ensure_one()
        # A distribution key is one or more analytic account ids joined by
        # commas -- one per analytic plan. Odoo knows how to read them
        # (analytic.mixin._get_analytic_account_ids_from_distributions) but
        # that method lives on the mixin, which account.move no longer carries.
        account_ids = {
            int(fragment)
            for key in (distribution or {})
            for fragment in str(key).split(',')
            if fragment.isdigit()
        }
        accounts = self.env['account.analytic.account'].browse(sorted(account_ids)).exists()
        foreign = accounts.filtered(
            lambda account: account.company_id and account.company_id != self.company_id
        )
        if foreign:
            raise UserError(_(
                "These analytic accounts belong to another company than %(company)s: %(accounts)s",
                company=self.company_id.display_name,
                accounts=", ".join(foreign.mapped('display_name')),
            ))

    # ------------------------------------------------------------------
    # Screen returns
    # ------------------------------------------------------------------

    def _dfd_open_apply_wizard(self, distribution, line_count, conflict_count):
        """Open the confirmation wizard, prefilled with what is already known.

        :param dict distribution: the header distribution, or ``False``
        :param int line_count: how many product lines the document holds
        :param int conflict_count: how many of them are already allocated
        :return: an ``ir.actions.act_window`` dict opening the wizard
        """
        wizard = self.env['dfd.analytic.bulk.apply'].create({
            'res_model': self._name,
            'res_id': self.id,
            'line_count': line_count,
            'conflict_count': conflict_count,
            'analytic_distribution': distribution or False,
        })
        return {
            'type': 'ir.actions.act_window',
            'name': _("Apply to the lines"),
            'res_model': 'dfd.analytic.bulk.apply',
            'res_id': wizard.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def _dfd_applied_notification(self, count):
        """Report how many lines were actually written on.

        :param int count: number of lines changed
        :return: an ``ir.actions.client`` notification dict
        """
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'type': 'success',
                'message': _("Analytic distribution applied to %(count)s line(s).", count=count),
                'next': {'type': 'ir.actions.act_window_close'},
            },
        }

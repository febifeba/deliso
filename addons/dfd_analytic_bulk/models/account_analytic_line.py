# Part of DorFAdoo. See LICENSE file for full copyright and licensing details.
from odoo import fields, models


class AccountAnalyticLine(models.Model):
    """Carry the source journal entry on the analytic line, in a stored column.

    A pivot table cannot group on a dotted path: ``_read_group`` refuses
    ``move_line_id.move_id`` outright (*"Property name 'move_id' has to be
    used on a property field"*), and ``auto_account_id`` is computed without
    being stored, so it cannot be converted to SQL either. Both were run
    against the two Deliso databases on 26 August 2026, not deduced.

    Odoo carries no stored field designating the *entry*: ``move_line_id``
    points at the journal *item*. Grouping on it yields one row per invoice
    line -- precisely the flood this module causes, since allocating fifty
    lines to a site now produces fifty analytic lines where a single header
    allocation once produced one. ``ref`` cannot stand in either: it is the
    vendor reference, and in production 62 of its values are shared by
    several entries ("Solde" across ten bills, "Acompte" across thirteen).
    Grouping on it would merge ten invoices into one row.

    Hence a stored ``related``, built exactly like the ``journal_id`` that
    ``account`` itself adds two fields above ours. It generates no analytic
    line and modifies none: it copies a value that already exists.
    """

    _inherit = 'account.analytic.line'

    move_id = fields.Many2one(
        comodel_name='account.move',
        string="Journal Entry",
        related='move_line_id.move_id',
        store=True,
        readonly=True,
        index='btree_not_null',
    )

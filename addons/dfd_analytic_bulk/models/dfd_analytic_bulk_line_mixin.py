# Part of DorFAdoo. See LICENSE file for full copyright and licensing details.
from odoo import fields, models


class DfdAnalyticBulkLineMixin(models.AbstractModel):
    """Let a user point at the lines to allocate, from the document itself.

    A vendor bill often carries two sites, not one. Allocating half its lines
    to the first and half to the second needs a way to say *which* half --
    and Odoo gives none inside a form: the selection checkboxes of a list
    exist only in a full-screen list view, never in a list embedded in a
    form. ``ListRenderer`` reads them from ``allowSelectors``, which defaults
    to ``False`` and is passed as ``True`` by the list controller and the
    record-picker dialog alone, never by the x2many field. The same goes for
    ``multi_edit``: it comes from the list controller, which an embedded list
    does not have.

    Hence a real field, shown as one more column. It is **optional and
    hidden**: whoever needs it turns it on once from the column selector, for
    themselves, and it stays. Nobody else sees a checkbox appear in their
    invoices.

    Ticking nothing means every line -- the ordinary case stays a single
    click, and the selection is only paid for by those who use it.
    """

    _name = 'dfd.analytic.bulk.line.mixin'
    _description = "Line Selection for Bulk Allocation"

    dfd_selected = fields.Boolean(
        string="Select",
        default=False,
        # A duplicated document must not carry over a half-finished
        # selection: it would silently allocate the wrong half.
        copy=False,
        help="Tick the lines to work on, then press the button. "
             "Nothing ticked means every line of the document.",
    )

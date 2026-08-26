# Part of DorFAdoo. See LICENSE file for full copyright and licensing details.
from odoo import _, api, fields, models
from odoo.exceptions import AccessError

from ..models.dfd_analytic_bulk_mixin import ALLOWED_MODELS


class DfdAnalyticBulkApply(models.TransientModel):
    """Ask what to put on the lines, and confirm before overwriting.

    On an invoice this is where the analytic distribution is typed: the field
    cannot live in the header without breaking the digitisation screen. On an
    order it arrives already filled from the header, and the wizard only opens
    when there is manual work to preserve.

    **A field left empty is not written to the lines.** That is the rule which
    lets a user set a tax without touching anything else.
    """

    _name = 'dfd.analytic.bulk.apply'
    _inherit = ['analytic.mixin']
    _description = "Allocate Lines to Analytic Accounts"

    # --- the document being worked on -------------------------------------
    res_model = fields.Char(string="Document Model", required=True, readonly=True)
    res_id = fields.Integer(string="Document", required=True, readonly=True)
    line_count = fields.Integer(string="Product Lines", readonly=True)
    conflict_count = fields.Integer(string="Lines Already Allocated", readonly=True)
    message = fields.Char(compute='_compute_message')

    # --- derived from the document, used by the view ----------------------
    company_id = fields.Many2one('res.company', compute='_compute_document')
    show_accounting_fields = fields.Boolean(compute='_compute_document')
    tax_type = fields.Char(compute='_compute_document')

    # --- what the user chooses --------------------------------------------
    account_id = fields.Many2one(
        'account.account',
        string="General Account",
        help="Leave empty to keep the account already on each line.",
    )
    tax_ids = fields.Many2many(
        'account.tax',
        string="Taxes",
        help="Leave empty to keep the taxes already on each line.",
    )
    mode = fields.Selection(
        selection=[
            ('empty', "Only fill in the empty lines"),
            ('overwrite', "Overwrite every line"),
        ],
        string="Scope",
        default='empty',
        required=True,
        help="Applies to the analytic distribution only.",
    )

    # ------------------------------------------------------------------
    # Computes
    # ------------------------------------------------------------------

    def _dfd_document(self):
        """Return the document this wizard acts on, or ``None``.

        ``res_model`` is checked against :data:`ALLOWED_MODELS` here as well
        as in :meth:`action_apply`: a wizard record can be created with any
        value, so nothing downstream may assume it is safe.
        """
        self.ensure_one()
        if self.res_model in ALLOWED_MODELS and self.res_id:
            return self.env[self.res_model].browse(self.res_id).exists()
        return None

    def _compute_analytic_distribution(self):
        """Free entry: nothing to infer, but the compute must be defined."""
        for wizard in self:
            wizard.analytic_distribution = wizard.analytic_distribution

    @api.depends('res_model', 'res_id')
    def _compute_document(self):
        """Derive from the document what the view needs to filter and hide."""
        for wizard in self:
            document = wizard._dfd_document()
            wizard.company_id = document.company_id if document else False
            wizard.show_accounting_fields = (
                bool(document) and document._dfd_supports_accounting_fields()
            )
            # A vendor bill calls for purchase taxes, a customer invoice for
            # sale taxes. Offering both in one list would be an invitation to
            # pick the wrong one.
            if document and document._name == 'account.move':
                wizard.tax_type = 'purchase' if document.move_type in (
                    'in_invoice', 'in_refund', 'in_receipt'
                ) else 'sale'
            else:
                wizard.tax_type = False

    @api.depends('line_count', 'conflict_count')
    def _compute_message(self):
        """State plainly what is about to happen, and to how many lines."""
        for wizard in self:
            if wizard.conflict_count:
                wizard.message = _(
                    "%(conflicts)s of the %(total)s product lines are already allocated. "
                    "What should be done with them?",
                    conflicts=wizard.conflict_count,
                    total=wizard.line_count,
                )
            else:
                wizard.message = _(
                    "The analytic distribution will be applied to the %(total)s product lines.",
                    total=wizard.line_count,
                )

    # ------------------------------------------------------------------
    # Action
    # ------------------------------------------------------------------

    def action_apply(self):
        """Write the chosen values on the document's product lines.

        Every guard the screen relies on is re-checked here. Hiding a button
        or a field closes nothing: the code of a web client is readable by
        whoever opens it.

        :return: a notification action
        :raise AccessError: when the user lacks the analytic group, or when
            ``res_model`` is not one this module supports
        """
        self.ensure_one()
        if not self.env.user.has_group('analytic.group_analytic_accounting'):
            raise AccessError(_("You are not allowed to manage analytic accounting."))
        if self.res_model not in ALLOWED_MODELS:
            raise AccessError(_(
                "Model %s does not support bulk analytic allocation.", self.res_model
            ))
        document = self._dfd_document()
        document.check_access('write')
        return document._dfd_apply(
            distribution=self.analytic_distribution,
            mode=self.mode,
            account=self.account_id,
            taxes=self.tax_ids,
        )

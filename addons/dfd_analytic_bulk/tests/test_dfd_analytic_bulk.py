# Part of DorFAdoo. See LICENSE file for full copyright and licensing details.
from odoo import Command, fields
from odoo.exceptions import AccessError, UserError
from odoo.tests import tagged

from odoo.addons.account.tests.common import AccountTestInvoicingCommon


@tagged('post_install', '-at_install')
class TestDfdAnalyticBulk(AccountTestInvoicingCommon):
    """Cover the module against a real chart of accounts.

    Run them with::

        odoo-bin -d <db> -u dfd_analytic_bulk --test-enable \\
                 --test-tags /dfd_analytic_bulk --stop-after-init
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # The accounting test rig opens neither sales nor purchases. Without
        # these groups, creating an order raises AccessError long before any
        # useful assertion runs.
        cls.env.user.group_ids |= (
            cls.env.ref('analytic.group_analytic_accounting')
            | cls.env.ref('sales_team.group_sale_salesman')
            | cls.env.ref('purchase.group_purchase_user')
        )

        cls.plan = cls.env['account.analytic.plan'].create({'name': "Chantiers"})
        # account.analytic.account.company_id carries a default. Deliso shares
        # its sites across all six companies, so they are created with none.
        cls.site_a = cls.env['account.analytic.account'].create({
            'name': "BULLANGE - LOT 1", 'plan_id': cls.plan.id, 'company_id': False,
        })
        cls.site_b = cls.env['account.analytic.account'].create({
            'name': "BURG-REULAND LOT 16", 'plan_id': cls.plan.id, 'company_id': False,
        })
        cls.dist_a = {str(cls.site_a.id): 100}
        cls.dist_b = {str(cls.site_b.id): 100}
        # The percentage split the customer asked for: 60/40 across two sites,
        # which the native project_id cascade cannot express.
        cls.dist_split = {str(cls.site_a.id): 60, str(cls.site_b.id): 40}

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _new_bill(self, post=False):
        return self.init_invoice(
            'in_invoice', partner=self.partner_a,
            products=self.product_a + self.product_b,
            taxes=self.tax_purchase_a, post=post,
        )

    def _product_lines(self, move):
        return move.line_ids.filtered(lambda line: line.display_type == 'product')

    def _wizard_for(self, document):
        action = document.action_dfd_apply_analytic()
        self.assertEqual(action['res_model'], 'dfd.analytic.bulk.apply')
        return self.env['dfd.analytic.bulk.apply'].browse(action['res_id'])

    def _apply_via_wizard(self, document, distribution, mode='empty', **extra):
        wizard = self._wizard_for(document)
        wizard.analytic_distribution = distribution
        wizard.mode = mode
        for name, value in extra.items():
            wizard[name] = value
        return wizard.action_apply()

    # ------------------------------------------------------------------
    # Where the header field lives, and where it must not
    # ------------------------------------------------------------------

    def test_invoice_carries_no_header_field(self):
        # Regression guard. An analytic_distribution field in an account.move
        # header breaks the form whenever account_invoice_extract is
        # installed: the widget takes focus, the digitisation module looks the
        # field up in its box mapping and raises a TypeError. Proven against
        # Odoo 19 Enterprise on 25 August 2026.
        self.assertNotIn('analytic_distribution', self.env['account.move']._fields)

    def test_orders_carry_the_header_field(self):
        # No digitisation intercepts focus on an order, and the field means
        # something there: at ordering time you know which site you buy for.
        self.assertIn('analytic_distribution', self.env['purchase.order']._fields)
        self.assertIn('analytic_distribution', self.env['sale.order']._fields)

    # ------------------------------------------------------------------
    # Invoices: everything goes through the wizard
    # ------------------------------------------------------------------

    def test_invoice_apply_fills_every_product_line(self):
        bill = self._new_bill()
        wizard = self._wizard_for(bill)
        self.assertFalse(wizard.conflict_count)
        self.assertEqual(wizard.line_count, len(self._product_lines(bill)))

        wizard.analytic_distribution = self.dist_a
        wizard.action_apply()

        for line in self._product_lines(bill):
            self.assertEqual(line.analytic_distribution, self.dist_a)

    def test_invoice_accepts_a_percentage_split(self):
        bill = self._new_bill()
        self._apply_via_wizard(bill, self.dist_split)
        for line in self._product_lines(bill):
            self.assertEqual(line.analytic_distribution, self.dist_split)

    def test_apply_with_nothing_filled_is_refused(self):
        bill = self._new_bill()
        with self.assertRaises(UserError):
            bill._dfd_apply()

    # ------------------------------------------------------------------
    # General account and taxes: empty means untouched
    # ------------------------------------------------------------------

    def test_account_is_applied_to_every_product_line(self):
        bill = self._new_bill()
        other_account = self.company_data['default_account_expense']
        self.assertTrue(any(
            line.account_id != other_account for line in self._product_lines(bill)
        ))

        self._apply_via_wizard(bill, self.dist_a, account_id=other_account)

        for line in self._product_lines(bill):
            self.assertEqual(line.account_id, other_account)

    def test_taxes_are_applied_to_every_product_line(self):
        bill = self._new_bill()
        other_tax = self.tax_purchase_b

        self._apply_via_wizard(bill, self.dist_a, tax_ids=other_tax)

        for line in self._product_lines(bill):
            self.assertEqual(line.tax_ids, other_tax)

    def test_empty_account_and_taxes_change_nothing(self):
        bill = self._new_bill()
        before = {
            line.id: (line.account_id, line.tax_ids)
            for line in self._product_lines(bill)
        }

        self._apply_via_wizard(bill, self.dist_a)

        for line in self._product_lines(bill):
            account, taxes = before[line.id]
            self.assertEqual(line.account_id, account)
            self.assertEqual(line.tax_ids, taxes)

    def test_account_alone_leaves_the_analytic_alone(self):
        # The whole point of "empty means untouched": fixing an account
        # without undoing a hand-made allocation.
        bill = self._new_bill()
        lines = self._product_lines(bill)
        lines[0].analytic_distribution = self.dist_b
        expense = self.company_data['default_account_expense']

        wizard = self._wizard_for(bill)
        wizard.account_id = expense
        wizard.action_apply()

        self.assertEqual(lines[0].analytic_distribution, self.dist_b)
        self.assertFalse(lines[1].analytic_distribution)
        for line in lines:
            self.assertEqual(line.account_id, expense)

    def test_account_leaves_the_payable_counterpart_alone(self):
        bill = self._new_bill()
        counterparts = bill.line_ids.filtered(lambda line: line.display_type == 'payment_term')
        before = {line.id: line.account_id for line in counterparts}
        self.assertTrue(before)

        self._apply_via_wizard(
            bill, self.dist_a, account_id=self.company_data['default_account_expense'],
        )

        for line in bill.line_ids.filtered(lambda l: l.display_type == 'payment_term'):
            self.assertEqual(line.account_id, before[line.id])

    # ------------------------------------------------------------------
    # General account and taxes: draft only
    # ------------------------------------------------------------------

    def test_posted_invoice_refuses_account_and_taxes(self):
        # Odoo refuses to change the taxes of a posted journal item anyway,
        # and changing the account of a reconciled line unreconciles it.
        bill = self._new_bill(post=True)
        self.assertFalse(bill._dfd_supports_accounting_fields())
        with self.assertRaises(UserError):
            bill._dfd_apply(account=self.company_data['default_account_expense'])

    def test_draft_invoice_supports_accounting_fields(self):
        self.assertTrue(self._new_bill()._dfd_supports_accounting_fields())

    def test_orders_refuse_account_and_taxes(self):
        # An order line has no general account: it only appears at invoicing.
        order = self.env['purchase.order'].create({
            'partner_id': self.partner_a.id,
            'order_line': [Command.create({'product_id': self.product_a.id, 'product_qty': 1})],
        })
        self.assertFalse(order._dfd_supports_accounting_fields())
        with self.assertRaises(UserError):
            order._dfd_apply(account=self.company_data['default_account_expense'])

    def test_wizard_hides_accounting_fields_on_a_posted_invoice(self):
        bill = self._new_bill(post=True)
        wizard = self._wizard_for(bill)
        self.assertFalse(wizard.show_accounting_fields)
        self.assertEqual(wizard.company_id, bill.company_id)

    def test_wizard_offers_purchase_taxes_on_a_vendor_bill(self):
        wizard = self._wizard_for(self._new_bill())
        self.assertTrue(wizard.show_accounting_fields)
        self.assertEqual(wizard.tax_type, 'purchase')

    # ------------------------------------------------------------------
    # Scope: only fill the empty lines, or overwrite them all
    # ------------------------------------------------------------------

    def test_mode_empty_leaves_manual_allocations_alone(self):
        bill = self._new_bill()
        lines = self._product_lines(bill)
        lines[0].analytic_distribution = self.dist_b

        self._apply_via_wizard(bill, self.dist_a, mode='empty')

        self.assertEqual(lines[0].analytic_distribution, self.dist_b)
        self.assertEqual(lines[1].analytic_distribution, self.dist_a)

    def test_mode_empty_is_the_default_and_conflicts_are_counted(self):
        bill = self._new_bill()
        lines = self._product_lines(bill)
        lines[0].analytic_distribution = self.dist_b

        wizard = self._wizard_for(bill)

        self.assertEqual(wizard.mode, 'empty')
        self.assertEqual(wizard.conflict_count, 1)
        self.assertEqual(wizard.line_count, len(lines))

    def test_mode_overwrite_replaces_every_line(self):
        bill = self._new_bill()
        lines = self._product_lines(bill)
        lines[0].analytic_distribution = self.dist_b

        self._apply_via_wizard(bill, self.dist_a, mode='overwrite')

        for line in lines:
            self.assertEqual(line.analytic_distribution, self.dist_a)

    # ------------------------------------------------------------------
    # Lines the button must never touch
    # ------------------------------------------------------------------

    def test_tax_and_payable_lines_are_left_untouched(self):
        bill = self._new_bill()
        self._apply_via_wizard(bill, self.dist_a)

        others = bill.line_ids.filtered(lambda line: line.display_type != 'product')
        self.assertTrue(others, "the fixture must produce tax lines and a counterpart")
        for line in others:
            self.assertFalse(line.analytic_distribution)

    def test_sections_and_notes_are_left_untouched(self):
        bill = self._new_bill()
        bill.write({'invoice_line_ids': [
            Command.create({'display_type': 'line_section', 'name': "Gros oeuvre"}),
            Command.create({'display_type': 'line_note', 'name': "Checked with the site manager"}),
        ]})

        self._apply_via_wizard(bill, self.dist_a)

        decorative = bill.line_ids.filtered(
            lambda line: line.display_type in ('line_section', 'line_subsection', 'line_note')
        )
        self.assertEqual(len(decorative), 2)
        for line in decorative:
            self.assertFalse(line.analytic_distribution)

    # ------------------------------------------------------------------
    # Locked accounting periods
    # ------------------------------------------------------------------

    def test_locked_period_is_refused(self):
        bill = self._new_bill(post=True)
        bill.company_id.fiscalyear_lock_date = fields.Date.add(bill.date, days=1)
        # Refused by the button itself: the wizard does not even open.
        with self.assertRaises(UserError):
            bill.action_dfd_apply_analytic()

    def test_draft_move_in_locked_period_is_allowed(self):
        # A draft entry is not accounting yet: Odoo lets it through, and so
        # does the module.
        bill = self._new_bill()
        bill.company_id.fiscalyear_lock_date = fields.Date.add(bill.date, days=1)

        self._apply_via_wizard(bill, self.dist_a)

        for line in self._product_lines(bill):
            self.assertEqual(line.analytic_distribution, self.dist_a)

    # ------------------------------------------------------------------
    # Multi-company
    # ------------------------------------------------------------------

    def test_analytic_account_of_another_company_is_refused(self):
        other_company = self.env['res.company'].create({'name': "V. DELHEZ"})
        foreign_site = self.env['account.analytic.account'].create({
            'name': "SITE NEXT DOOR", 'plan_id': self.plan.id,
            'company_id': other_company.id,
        })
        bill = self._new_bill()
        with self.assertRaises(UserError):
            self._apply_via_wizard(bill, {str(foreign_site.id): 100})

    def test_analytic_account_without_company_is_allowed(self):
        # Deliso shares its 81 sites across companies: no company_id.
        self.assertFalse(self.site_a.company_id)
        bill = self._new_bill()

        self._apply_via_wizard(bill, self.dist_a)

        for line in self._product_lines(bill):
            self.assertEqual(line.analytic_distribution, self.dist_a)

    # ------------------------------------------------------------------
    # Orders: display_type reads the other way round
    # ------------------------------------------------------------------

    def test_purchase_order_applies_from_the_header_without_a_wizard(self):
        order = self.env['purchase.order'].create({
            'partner_id': self.partner_a.id,
            'order_line': [
                Command.create({'product_id': self.product_a.id, 'product_qty': 1}),
                Command.create({'display_type': 'line_section', 'name': "Roofing", 'product_qty': 0}),
                Command.create({'product_id': self.product_b.id, 'product_qty': 2}),
                Command.create({'display_type': 'line_note', 'name': "Delivery on Monday", 'product_qty': 0}),
            ],
        })
        order.analytic_distribution = self.dist_a

        action = order.action_dfd_apply_analytic()

        # Nothing was allocated: written straight away, no wizard.
        self.assertEqual(action['tag'], 'display_notification')
        for line in order.order_line:
            if line.display_type:
                self.assertFalse(line.analytic_distribution)
            else:
                self.assertEqual(line.analytic_distribution, self.dist_a)

    def test_purchase_order_opens_the_wizard_when_a_line_is_allocated(self):
        order = self.env['purchase.order'].create({
            'partner_id': self.partner_a.id,
            'order_line': [
                Command.create({'product_id': self.product_a.id, 'product_qty': 1}),
                Command.create({'product_id': self.product_b.id, 'product_qty': 2}),
            ],
        })
        order.order_line[0].analytic_distribution = self.dist_b
        order.analytic_distribution = self.dist_a

        wizard = self._wizard_for(order)

        # The header distribution reaches the wizard already filled in.
        self.assertEqual(wizard.analytic_distribution, self.dist_a)
        self.assertEqual(wizard.conflict_count, 1)
        wizard.action_apply()

        self.assertEqual(order.order_line[0].analytic_distribution, self.dist_b)
        self.assertEqual(order.order_line[1].analytic_distribution, self.dist_a)

    def test_purchase_order_without_header_opens_the_wizard(self):
        # The button shows even on an empty header: hiding it made the
        # feature undiscoverable to anyone who did not already know it.
        order = self.env['purchase.order'].create({
            'partner_id': self.partner_a.id,
            'order_line': [
                Command.create({'product_id': self.product_a.id, 'product_qty': 1}),
                Command.create({'product_id': self.product_b.id, 'product_qty': 2}),
            ],
        })
        self.assertFalse(order.analytic_distribution)

        wizard = self._wizard_for(order)

        self.assertFalse(wizard.analytic_distribution)
        self.assertFalse(wizard.conflict_count)
        wizard.analytic_distribution = self.dist_a
        wizard.action_apply()

        for line in order.order_line:
            self.assertEqual(line.analytic_distribution, self.dist_a)

    def test_sale_order_skips_sections_and_notes(self):
        order = self.env['sale.order'].create({
            'partner_id': self.partner_a.id,
            'order_line': [
                Command.create({'product_id': self.product_a.id, 'product_uom_qty': 1}),
                Command.create({'display_type': 'line_note', 'name': "Agreed by phone", 'product_uom_qty': 0}),
            ],
        })
        order.analytic_distribution = self.dist_a

        order.action_dfd_apply_analytic()

        for line in order.order_line:
            if line.display_type:
                self.assertFalse(line.analytic_distribution)
            else:
                self.assertEqual(line.analytic_distribution, self.dist_a)

    # ------------------------------------------------------------------
    # The wizard refuses what the screen hides
    # ------------------------------------------------------------------

    def test_wizard_refuses_an_unlisted_model(self):
        wizard = self.env['dfd.analytic.bulk.apply'].create({
            'res_model': 'res.partner', 'res_id': self.partner_a.id,
            'line_count': 0, 'conflict_count': 0,
            'analytic_distribution': self.dist_a,
        })
        with self.assertRaises(AccessError):
            wizard.action_apply()

    # ------------------------------------------------------------------
    # The stored move_id that lets a pivot group by entry
    # ------------------------------------------------------------------

    def test_analytic_lines_carry_the_entry(self):
        # Every analytic line born of a bill points back at that bill, so a
        # pivot can group on a stored column instead of a dotted path.
        bill = self._new_bill()
        self._apply_via_wizard(bill, self.dist_a)
        bill.action_post()

        analytic_lines = self._product_lines(bill).analytic_line_ids
        self.assertTrue(analytic_lines)
        self.assertEqual(analytic_lines.move_id, bill)

    def test_move_id_follows_the_journal_item(self):
        # The field is related and read-only: it must never be typed in, only
        # follow move_line_id.
        bill = self._new_bill()
        self._apply_via_wizard(bill, self.dist_a)
        bill.action_post()

        analytic_line = self._product_lines(bill).analytic_line_ids[0]
        self.assertEqual(analytic_line.move_id, analytic_line.move_line_id.move_id)
        self.assertTrue(self.env['account.analytic.line']._fields['move_id'].related)
        self.assertTrue(self.env['account.analytic.line']._fields['move_id'].store)
        self.assertTrue(self.env['account.analytic.line']._fields['move_id'].readonly)

    def test_a_split_bill_groups_into_two_rows_not_one(self):
        # The whole point of the field. A bill split 60/40 across two sites
        # must yield exactly two rows, one per site, and never one row per
        # invoice line -- the flood the site dashboard suffers from.
        bill = self._new_bill()
        self._apply_via_wizard(bill, self.dist_split)
        bill.action_post()

        # Which column carries the site depends on the plan: only the project
        # plan is stored in account_id, every other plan gets its own
        # x_plan<id>_id column. Deliso's Chantiers plan happens to be the
        # project plan, the test rig's is not, so the column is asked for
        # rather than assumed.
        plan_column = self.plan._column_name()
        rows = self.env['account.analytic.line'].read_group(
            [('move_id', '=', bill.id)],
            ['amount:sum'],
            [plan_column, 'move_id'],
            lazy=False,
        )

        self.assertEqual(len(rows), 2)
        self.assertEqual(
            {row[plan_column][0] for row in rows},
            {self.site_a.id, self.site_b.id},
        )
        # Two rows out of four analytic lines: two product lines times two
        # sites. Without the field there would be four.
        self.assertEqual(len(self._product_lines(bill).analytic_line_ids), 4)

    def test_grouping_by_entry_does_not_raise(self):
        # ``read_group`` is the path a pivot table takes over RPC, and it is
        # stricter than the internal ``_read_group``: it reads a dotted
        # groupby as a property field and refuses it outright. That refusal is
        # the whole reason this field exists, so it is pinned here alongside
        # the other dead end, a computed field that is not stored.
        AnalyticLine = self.env['account.analytic.line']

        AnalyticLine.read_group([], ['amount:sum'], ['account_id', 'move_id'], lazy=False)

        with self.assertRaises(ValueError):
            AnalyticLine.read_group([], ['amount:sum'], ['move_line_id.move_id'], lazy=False)
        with self.assertRaises(ValueError):
            AnalyticLine.read_group([], ['amount:sum'], ['auto_account_id'], lazy=False)

    # ------------------------------------------------------------------
    # Emptying the lines tab in one gesture
    # ------------------------------------------------------------------

    def test_clear_lines_empties_the_tab(self):
        bill = self._new_bill()
        self.assertTrue(bill.invoice_line_ids)

        bill.action_dfd_clear_lines()

        self.assertFalse(bill.invoice_line_ids)
        self.assertFalse(self._product_lines(bill))

    def test_clear_lines_takes_sections_and_notes_too(self):
        # invoice_line_ids is exactly what the tab shows: product lines,
        # sections, subsections and notes. All of it goes.
        bill = self._new_bill()
        bill.write({'invoice_line_ids': [
            Command.create({'display_type': 'line_section', 'name': "Materials"}),
            Command.create({'display_type': 'line_note', 'name': "Agreed on site"}),
        ]})
        self.assertEqual(len(bill.invoice_line_ids), 4)

        bill.action_dfd_clear_lines()

        self.assertFalse(bill.invoice_line_ids)

    def test_clear_lines_leaves_a_usable_draft(self):
        # Tax lines and the payable counterpart are not deleted by hand:
        # Odoo recomputes them from what is left, which is nothing.
        bill = self._new_bill()

        bill.action_dfd_clear_lines()

        self.assertEqual(bill.state, 'draft')
        self.assertFalse(bill.line_ids.filtered(lambda line: line.display_type == 'tax'))
        self.assertEqual(bill.amount_total, 0)

    def test_clear_lines_refuses_a_posted_document(self):
        # The screen hides the button on a posted document. The method
        # refuses it again: hiding a button closes nothing.
        bill = self._new_bill(post=True)

        with self.assertRaises(UserError):
            bill.action_dfd_clear_lines()

        self.assertTrue(bill.invoice_line_ids)

    def test_clear_lines_refuses_an_empty_document(self):
        bill = self._new_bill()
        bill.invoice_line_ids.unlink()

        with self.assertRaises(UserError):
            bill.action_dfd_clear_lines()

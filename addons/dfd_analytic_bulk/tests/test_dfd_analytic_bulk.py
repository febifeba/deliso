# Part of DorFAdoo. See LICENSE file for full copyright and licensing details.
from odoo import Command, fields
from odoo.exceptions import UserError
from odoo.tests import tagged

from odoo.addons.account.tests.common import AccountTestInvoicingCommon


@tagged('post_install', '-at_install')
class TestDfdAnalyticBulk(AccountTestInvoicingCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.user.group_ids |= cls.env.ref('analytic.group_analytic_accounting')

        cls.plan = cls.env['account.analytic.plan'].create({'name': "Chantiers"})
        cls.site_a = cls.env['account.analytic.account'].create({
            'name': "BULLANGE - LOT 1",
            'plan_id': cls.plan.id,
        })
        cls.site_b = cls.env['account.analytic.account'].create({
            'name': "BURG-REULAND LOT 16",
            'plan_id': cls.plan.id,
        })
        cls.dist_a = {str(cls.site_a.id): 100}
        cls.dist_b = {str(cls.site_b.id): 100}
        # La répartition en pourcentages que Jérôme évoque : 60/40 sur deux
        # chantiers, ce que la cascade native par project_id ne sait pas faire.
        cls.dist_split = {str(cls.site_a.id): 60, str(cls.site_b.id): 40}

    # ------------------------------------------------------------------
    # Aides
    # ------------------------------------------------------------------

    def _new_bill(self, post=False):
        return self.init_invoice(
            'in_invoice',
            partner=self.partner_a,
            products=self.product_a + self.product_b,
            taxes=self.tax_purchase_a,
            post=post,
        )

    def _product_lines(self, move):
        return move.line_ids.filtered(lambda line: line.display_type == 'product')

    def _apply(self, document, mode):
        """Passer par le wizard comme le ferait l'utilisateur."""
        action = document.action_dfd_apply_analytic()
        self.assertEqual(action['res_model'], 'dfd.analytic.bulk.apply')
        wizard = self.env['dfd.analytic.bulk.apply'].browse(action['res_id'])
        wizard.mode = mode
        return wizard.action_apply()

    # ------------------------------------------------------------------
    # Le bouton, sans conflit
    # ------------------------------------------------------------------

    def test_apply_without_conflict_writes_every_product_line(self):
        bill = self._new_bill()
        bill.analytic_distribution = self.dist_a

        action = bill.action_dfd_apply_analytic()

        # Aucune ligne n'était imputée : pas de wizard, on écrit directement.
        self.assertEqual(action['tag'], 'display_notification')
        for line in self._product_lines(bill):
            self.assertEqual(line.analytic_distribution, self.dist_a)

    def test_apply_accepts_a_percentage_split(self):
        bill = self._new_bill()
        bill.analytic_distribution = self.dist_split

        bill.action_dfd_apply_analytic()

        for line in self._product_lines(bill):
            self.assertEqual(line.analytic_distribution, self.dist_split)

    def test_apply_without_header_distribution_is_refused(self):
        bill = self._new_bill()
        with self.assertRaises(UserError):
            bill.action_dfd_apply_analytic()

    # ------------------------------------------------------------------
    # Le wizard : lignes vides seulement / écrasement total
    # ------------------------------------------------------------------

    def test_mode_empty_leaves_manual_allocations_alone(self):
        bill = self._new_bill()
        lines = self._product_lines(bill)
        lines[0].analytic_distribution = self.dist_b
        bill.analytic_distribution = self.dist_a

        self._apply(bill, 'empty')

        self.assertEqual(lines[0].analytic_distribution, self.dist_b)
        self.assertEqual(lines[1].analytic_distribution, self.dist_a)

    def test_mode_empty_is_the_default(self):
        bill = self._new_bill()
        lines = self._product_lines(bill)
        lines[0].analytic_distribution = self.dist_b
        bill.analytic_distribution = self.dist_a

        action = bill.action_dfd_apply_analytic()
        wizard = self.env['dfd.analytic.bulk.apply'].browse(action['res_id'])

        self.assertEqual(wizard.mode, 'empty')
        self.assertEqual(wizard.conflict_count, 1)
        self.assertEqual(wizard.line_count, len(lines))

    def test_mode_overwrite_replaces_every_line(self):
        bill = self._new_bill()
        lines = self._product_lines(bill)
        lines[0].analytic_distribution = self.dist_b
        bill.analytic_distribution = self.dist_a

        self._apply(bill, 'overwrite')

        for line in lines:
            self.assertEqual(line.analytic_distribution, self.dist_a)

    # ------------------------------------------------------------------
    # Ce que le bouton ne doit pas toucher
    # ------------------------------------------------------------------

    def test_tax_and_payable_lines_are_left_untouched(self):
        bill = self._new_bill()
        bill.analytic_distribution = self.dist_a

        bill.action_dfd_apply_analytic()

        others = bill.line_ids.filtered(lambda line: line.display_type != 'product')
        self.assertTrue(others, "le jeu d'essai doit produire des lignes de taxe et une contrepartie")
        for line in others:
            self.assertFalse(line.analytic_distribution)

    def test_sections_and_notes_are_left_untouched(self):
        bill = self._new_bill()
        bill.write({'invoice_line_ids': [
            Command.create({'display_type': 'line_section', 'name': "Gros oeuvre"}),
            Command.create({'display_type': 'line_note', 'name': "Vu avec le chef de chantier"}),
        ]})
        bill.analytic_distribution = self.dist_a

        bill.action_dfd_apply_analytic()

        decorative = bill.line_ids.filtered(
            lambda line: line.display_type in ('line_section', 'line_subsection', 'line_note')
        )
        self.assertEqual(len(decorative), 2)
        for line in decorative:
            self.assertFalse(line.analytic_distribution)

    # ------------------------------------------------------------------
    # Période verrouillée
    # ------------------------------------------------------------------

    def test_locked_period_is_refused(self):
        bill = self._new_bill(post=True)
        bill.company_id.fiscalyear_lock_date = fields.Date.add(bill.date, days=1)
        bill.analytic_distribution = self.dist_a

        with self.assertRaises(UserError):
            bill.action_dfd_apply_analytic()

    def test_draft_move_in_locked_period_is_allowed(self):
        # Une pièce non postée n'est pas encore de la comptabilité : Odoo la
        # laisse passer, le module aussi.
        bill = self._new_bill()
        bill.company_id.fiscalyear_lock_date = fields.Date.add(bill.date, days=1)
        bill.analytic_distribution = self.dist_a

        bill.action_dfd_apply_analytic()

        for line in self._product_lines(bill):
            self.assertEqual(line.analytic_distribution, self.dist_a)

    # ------------------------------------------------------------------
    # Multi-sociétés
    # ------------------------------------------------------------------

    def test_analytic_account_of_another_company_is_refused(self):
        other_company = self.env['res.company'].create({'name': "V. DELHEZ"})
        foreign_site = self.env['account.analytic.account'].create({
            'name': "CHANTIER D'EN FACE",
            'plan_id': self.plan.id,
            'company_id': other_company.id,
        })
        bill = self._new_bill()
        bill.analytic_distribution = {str(foreign_site.id): 100}

        with self.assertRaises(UserError):
            bill.action_dfd_apply_analytic()

    def test_analytic_account_without_company_is_allowed(self):
        # Chez Deliso les 81 chantiers sont partagés : pas de company_id.
        bill = self._new_bill()
        self.assertFalse(self.site_a.company_id)
        bill.analytic_distribution = self.dist_a

        bill.action_dfd_apply_analytic()

        for line in self._product_lines(bill):
            self.assertEqual(line.analytic_distribution, self.dist_a)

    # ------------------------------------------------------------------
    # Commandes : display_type s'y lit à l'envers
    # ------------------------------------------------------------------

    def test_purchase_order_skips_sections_and_notes(self):
        order = self.env['purchase.order'].create({
            'partner_id': self.partner_a.id,
            'order_line': [
                Command.create({'product_id': self.product_a.id, 'product_qty': 1}),
                Command.create({'display_type': 'line_section', 'name': "Toiture"}),
                Command.create({'product_id': self.product_b.id, 'product_qty': 2}),
                Command.create({'display_type': 'line_note', 'name': "Livraison lundi"}),
            ],
        })
        order.analytic_distribution = self.dist_a

        order.action_dfd_apply_analytic()

        for line in order.order_line:
            if line.display_type:
                self.assertFalse(line.analytic_distribution)
            else:
                self.assertEqual(line.analytic_distribution, self.dist_a)

    def test_sale_order_skips_sections_and_notes(self):
        order = self.env['sale.order'].create({
            'partner_id': self.partner_a.id,
            'order_line': [
                Command.create({'product_id': self.product_a.id, 'product_uom_qty': 1}),
                Command.create({'display_type': 'line_note', 'name': "Devis validé par téléphone"}),
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
    # Le wizard refuse ce que l'écran cache
    # ------------------------------------------------------------------

    def test_wizard_refuses_an_unlisted_model(self):
        from odoo.exceptions import AccessError

        wizard = self.env['dfd.analytic.bulk.apply'].create({
            'res_model': 'res.partner',
            'res_id': self.partner_a.id,
            'line_count': 0,
            'conflict_count': 0,
        })
        with self.assertRaises(AccessError):
            wizard.action_apply()

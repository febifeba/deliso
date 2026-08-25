# Part of DorFAdoo. See LICENSE file for full copyright and licensing details.
from odoo import Command, fields
from odoo.exceptions import AccessError, UserError
from odoo.tests import tagged

from odoo.addons.account.tests.common import AccountTestInvoicingCommon


@tagged('post_install', '-at_install')
class TestDfdAnalyticBulk(AccountTestInvoicingCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Le socle comptable n'ouvre ni la vente ni l'achat : sans ces groupes,
        # créer une commande lève une AccessError avant tout test utile.
        cls.env.user.group_ids |= (
            cls.env.ref('analytic.group_analytic_accounting')
            | cls.env.ref('sales_team.group_sale_salesman')
            | cls.env.ref('purchase.group_purchase_user')
        )

        cls.plan = cls.env['account.analytic.plan'].create({'name': "Chantiers"})
        # company_id porte une valeur par défaut ; les chantiers de Deliso sont
        # partagés entre les six sociétés, donc sans société.
        cls.site_a = cls.env['account.analytic.account'].create({
            'name': "BULLANGE - LOT 1", 'plan_id': cls.plan.id, 'company_id': False,
        })
        cls.site_b = cls.env['account.analytic.account'].create({
            'name': "BURG-REULAND LOT 16", 'plan_id': cls.plan.id, 'company_id': False,
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

    def _apply_via_wizard(self, document, distribution, mode='empty'):
        wizard = self._wizard_for(document)
        wizard.analytic_distribution = distribution
        wizard.mode = mode
        return wizard.action_apply()

    # ------------------------------------------------------------------
    # Le champ d'en-tête : présent sur les commandes, absent des factures
    # ------------------------------------------------------------------

    def test_invoice_carries_no_header_field(self):
        # Régression : un champ analytic_distribution en en-tête d'account.move
        # fait planter l'écran quand account_invoice_extract est installé — le
        # widget prend le focus, le module de numérisation cherche le champ
        # dans sa table et lève un TypeError. Éprouvé sur Odoo 19 Enterprise le
        # 25 août 2026.
        self.assertNotIn('analytic_distribution', self.env['account.move']._fields)

    def test_orders_carry_the_header_field(self):
        # Sur une commande, aucune numérisation n'intercepte le focus, et le
        # champ a un sens propre : on sait dès la commande pour quel chantier
        # on achète.
        self.assertIn('analytic_distribution', self.env['purchase.order']._fields)
        self.assertIn('analytic_distribution', self.env['sale.order']._fields)

    # ------------------------------------------------------------------
    # Facture : tout passe par l'assistant
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

    def test_apply_without_distribution_is_refused(self):
        bill = self._new_bill()
        with self.assertRaises(UserError):
            bill._dfd_apply_analytic(False)

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
    # Ce que le bouton ne doit pas toucher
    # ------------------------------------------------------------------

    def test_tax_and_payable_lines_are_left_untouched(self):
        bill = self._new_bill()
        self._apply_via_wizard(bill, self.dist_a)

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
        self._apply_via_wizard(bill, self.dist_a)

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
        # Refusé dès le bouton : l'assistant ne s'ouvre même pas.
        with self.assertRaises(UserError):
            bill.action_dfd_apply_analytic()

    def test_draft_move_in_locked_period_is_allowed(self):
        # Une pièce non postée n'est pas encore de la comptabilité : Odoo la
        # laisse passer, le module aussi.
        bill = self._new_bill()
        bill.company_id.fiscalyear_lock_date = fields.Date.add(bill.date, days=1)

        self._apply_via_wizard(bill, self.dist_a)

        for line in self._product_lines(bill):
            self.assertEqual(line.analytic_distribution, self.dist_a)

    # ------------------------------------------------------------------
    # Multi-sociétés
    # ------------------------------------------------------------------

    def test_analytic_account_of_another_company_is_refused(self):
        other_company = self.env['res.company'].create({'name': "V. DELHEZ"})
        foreign_site = self.env['account.analytic.account'].create({
            'name': "CHANTIER D'EN FACE", 'plan_id': self.plan.id,
            'company_id': other_company.id,
        })
        bill = self._new_bill()
        with self.assertRaises(UserError):
            self._apply_via_wizard(bill, {str(foreign_site.id): 100})

    def test_analytic_account_without_company_is_allowed(self):
        # Chez Deliso les 81 chantiers sont partagés : pas de company_id.
        self.assertFalse(self.site_a.company_id)
        bill = self._new_bill()
        self._apply_via_wizard(bill, self.dist_a)
        for line in self._product_lines(bill):
            self.assertEqual(line.analytic_distribution, self.dist_a)

    # ------------------------------------------------------------------
    # Commandes : l'en-tête suffit, display_type s'y lit à l'envers
    # ------------------------------------------------------------------

    def test_purchase_order_applies_from_the_header_without_a_wizard(self):
        order = self.env['purchase.order'].create({
            'partner_id': self.partner_a.id,
            'order_line': [
                Command.create({'product_id': self.product_a.id, 'product_qty': 1}),
                Command.create({'display_type': 'line_section', 'name': "Toiture", 'product_qty': 0}),
                Command.create({'product_id': self.product_b.id, 'product_qty': 2}),
                Command.create({'display_type': 'line_note', 'name': "Livraison lundi", 'product_qty': 0}),
            ],
        })
        order.analytic_distribution = self.dist_a

        action = order.action_dfd_apply_analytic()

        # Rien n'était imputé : on écrit directement, sans assistant.
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

        # La distribution de l'en-tête arrive déjà remplie dans l'assistant.
        self.assertEqual(wizard.analytic_distribution, self.dist_a)
        self.assertEqual(wizard.conflict_count, 1)
        wizard.action_apply()
        self.assertEqual(order.order_line[0].analytic_distribution, self.dist_b)
        self.assertEqual(order.order_line[1].analytic_distribution, self.dist_a)

    def test_sale_order_skips_sections_and_notes(self):
        order = self.env['sale.order'].create({
            'partner_id': self.partner_a.id,
            'order_line': [
                Command.create({'product_id': self.product_a.id, 'product_uom_qty': 1}),
                Command.create({'display_type': 'line_note', 'name': "Devis validé par téléphone", 'product_uom_qty': 0}),
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
    # L'assistant refuse ce que l'écran cache
    # ------------------------------------------------------------------

    def test_wizard_refuses_an_unlisted_model(self):
        wizard = self.env['dfd.analytic.bulk.apply'].create({
            'res_model': 'res.partner', 'res_id': self.partner_a.id,
            'line_count': 0, 'conflict_count': 0,
            'analytic_distribution': self.dist_a,
        })
        with self.assertRaises(AccessError):
            wizard.action_apply()

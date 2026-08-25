# Part of DorFAdoo. See LICENSE file for full copyright and licensing details.
from odoo import models


class AccountMove(models.Model):
    _name = 'account.move'
    _inherit = ['account.move', 'dfd.analytic.bulk.mixin']

    # Volontairement PAS dfd.analytic.bulk.header.mixin : un champ
    # analytic_distribution en en-tête de facture fait planter l'écran dès
    # qu'il prend le focus, quand account_invoice_extract est installé.
    # La distribution se saisit dans l'assistant.

    def _dfd_analytic_target_lines(self):
        # Sur account.move.line, une ligne de produit porte display_type
        # 'product'. Les lignes de taxe ('tax'), de contrepartie
        # ('payment_term'), d'arrondi, d'escompte, de section et de note sont
        # écartées par le même test.
        return self.line_ids.filtered(lambda line: line.display_type == 'product')

    def _dfd_check_writable(self):
        # Odoo ne protège PAS analytic_distribution par les dates de
        # verrouillage : _get_lock_date_protected_fields() ne liste que
        # balance, tax_*, account_id, journal_id, amount_currency,
        # currency_id et partner_id. Écrire l'analytique d'une pièce postée
        # dans une période close passerait donc sans un mot, et
        # _inverse_analytic_distribution régénérerait les account.analytic.line
        # au passage. Le garde-fou est posé ici, faute d'en trouver un en face.
        self.filtered(lambda move: move.state == 'posted')._check_fiscal_lock_dates()

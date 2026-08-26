# Part of DorFAdoo. See LICENSE file for full copyright and licensing details.
from odoo import _, models, Command
from odoo.exceptions import UserError

# Les seuls modèles autorisés à porter le bouton. Le wizard s'y réfère pour
# refuser tout autre res_model : un oubli ferme, il n'ouvre pas.
ALLOWED_MODELS = ('account.move', 'purchase.order', 'sale.order')


class DfdAnalyticBulkMixin(models.AbstractModel):
    """Appliquer une distribution analytique à toutes les lignes d'un document.

    Ce mixin ne porte AUCUN champ. C'est délibéré : sur ``account.move``, un
    champ ``analytic_distribution`` en en-tête fait planter l'écran. Le widget
    se donne le focus en se rendant, et le module Enterprise de numérisation
    des factures (``account_invoice_extract``) intercepte ce focus pour
    surligner la zone correspondante du document scanné — il cherche le champ
    dans sa table de correspondance, ne l'y trouve pas, et lève un
    « Cannot read properties of undefined (reading 'fields') ».

    Éprouvé le 25 août 2026 sur une staging Odoo 19 Enterprise : le même champ
    en en-tête d'une commande d'achat ne pose aucun problème — les achats
    n'ont pas de numérisation. C'est donc bien l'interaction avec
    ``account_invoice_extract``, pas le widget lui-même.

    Les modèles qui peuvent porter le champ sans risque héritent en plus de
    ``dfd.analytic.bulk.header.mixin``. Sur une facture, la distribution se
    saisit dans l'assistant.
    """

    _name = 'dfd.analytic.bulk.mixin'
    _description = "Bulk Analytic Allocation"

    # ------------------------------------------------------------------
    # À redéfinir par chaque modèle
    # ------------------------------------------------------------------

    def _dfd_analytic_target_lines(self):
        """Les lignes que le bouton a le droit de toucher.

        Redéfini modèle par modèle, parce que ``display_type`` ne se lit pas
        pareil de l'un à l'autre : sur ``account.move.line`` une ligne de
        produit vaut ``'product'``, sur les lignes de commande elle ne vaut
        rien du tout. Filtrer partout sur l'absence de ``display_type``
        viderait les factures de toutes leurs lignes.
        """
        raise NotImplementedError

    def _dfd_check_writable(self):
        """Garde-fou propre au modèle, appelé avant toute écriture."""
        return

    def _dfd_header_distribution(self):
        """La distribution posée en en-tête, quand le modèle en porte une.

        Vide ici : l'assistant la demandera.
        """
        return False

    def _dfd_supports_accounting_fields(self):
        """Le document accepte-t-il qu'on lui pose un compte et des taxes ?

        Non par défaut. Les lignes de commande n'ont pas de compte comptable —
        il n'apparaît qu'à la facturation — et forcer une taxe sur une commande
        n'a pas d'intérêt : elle vient du produit et du fournisseur.
        """
        return False

    # ------------------------------------------------------------------
    # Le bouton
    # ------------------------------------------------------------------

    def action_dfd_apply_analytic(self):
        """Appliquer une distribution analytique aux lignes de produit.

        Chemin direct — écrire sans rien demander — seulement quand l'en-tête
        porte déjà la distribution ET qu'aucune ligne n'est imputée. Dans tous
        les autres cas l'assistant s'ouvre : soit il manque la distribution,
        soit du travail manuel est en jeu et ne s'écrase pas en silence.
        """
        self.ensure_one()
        self._dfd_check_writable()

        lines = self._dfd_analytic_target_lines()
        if not lines:
            raise UserError(_("This document has no product line to allocate."))

        distribution = self._dfd_header_distribution()
        already_filled = lines.filtered(lambda line: line.analytic_distribution)

        if distribution and not already_filled and not self._dfd_supports_accounting_fields():
            return self._dfd_apply(distribution, mode='overwrite')
        return self._dfd_open_apply_wizard(distribution, len(lines), len(already_filled))

    def _dfd_apply(self, distribution=False, mode='empty', account=False, taxes=None):
        """Écrire sur les lignes de produit. Un champ vide n'est pas touché.

        La portée (lignes vides seulement / tout écraser) ne gouverne que
        l'analytique : c'est là qu'une ventilation posée à la main mérite
        d'être préservée. Un compte comptable, lui, est obligatoire sur toute
        ligne — aucune n'est jamais vide, « n'affecter que les lignes vides »
        n'y voudrait rien dire. Renseigné, il s'applique partout.
        """
        self.ensure_one()
        if not distribution and not account and not taxes:
            raise UserError(_("Fill in at least one value to apply."))
        self._dfd_check_writable()

        lines = self._dfd_analytic_target_lines()
        touchees = self.env[lines._name] if lines else lines

        if distribution:
            self._dfd_check_analytic_company(distribution)
            cibles = lines if mode == 'overwrite' else lines.filtered(
                lambda line: not line.analytic_distribution
            )
            # Une ligne qui porte déjà exactement la même distribution n'est pas
            # réécrite : chaque écriture fait retirer puis recréer ses écritures
            # analytiques par _inverse_analytic_distribution.
            cibles = cibles.filtered(lambda line: line.analytic_distribution != distribution)
            if cibles:
                cibles.write({'analytic_distribution': distribution})
            touchees |= cibles

        if account or taxes:
            if not self._dfd_supports_accounting_fields():
                raise UserError(_(
                    "This document does not accept a general account or taxes."
                ))
            valeurs = {}
            if account:
                valeurs['account_id'] = account.id
            if taxes:
                valeurs['tax_ids'] = [Command.set(taxes.ids)]
            if lines:
                lines.write(valeurs)
            touchees |= lines

        return self._dfd_applied_notification(len(touchees))

    # ------------------------------------------------------------------
    # Contrôles
    # ------------------------------------------------------------------

    def _dfd_check_analytic_company(self, distribution):
        """Un compte analytique d'une autre société n'a rien à faire ici.

        La base de Deliso compte six sociétés ; rien dans le widget n'empêche
        de choisir le compte de la voisine.
        """
        self.ensure_one()
        # Une clé de distribution est un ou plusieurs identifiants de compte
        # joints par des virgules — un par plan analytique. Odoo sait les lire
        # (analytic.mixin._get_analytic_account_ids_from_distributions), mais
        # cette méthode vit sur le mixin, qu'account.move ne porte plus.
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
    # Retours d'écran
    # ------------------------------------------------------------------

    def _dfd_open_apply_wizard(self, distribution, line_count, conflict_count):
        wizard = self.env['dfd.analytic.bulk.apply'].create({
            'res_model': self._name,
            'res_id': self.id,
            'line_count': line_count,
            'conflict_count': conflict_count,
            'analytic_distribution': distribution or False,
        })
        return {
            'type': 'ir.actions.act_window',
            'name': _("Allocate lines to analytic accounts"),
            'res_model': 'dfd.analytic.bulk.apply',
            'res_id': wizard.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def _dfd_applied_notification(self, count):
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'type': 'success',
                'message': _("Analytic distribution applied to %(count)s line(s).", count=count),
                'next': {'type': 'ir.actions.act_window_close'},
            },
        }

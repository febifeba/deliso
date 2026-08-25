# Part of DorFAdoo. See LICENSE file for full copyright and licensing details.
{
    'name': "Analytique : distribution en en-tête et application en masse",
    'version': '19.0.1.0.0',
    'category': 'Accounting/Accounting',
    'summary': "Poser une distribution analytique sur un document et l'appliquer à toutes ses lignes",
    'author': "DorFAdoo",
    'website': "https://www.dorfadoo.be",
    'license': 'LGPL-3',
    'depends': [
        'account',
        'purchase',
        'sale_management',
        'analytic',
    ],
    'data': [
        'security/ir.model.access.csv',
        'wizard/dfd_analytic_bulk_apply_views.xml',
        'views/account_move_views.xml',
        'views/purchase_order_views.xml',
        'views/sale_order_views.xml',
    ],
    'installable': True,
    'application': False,
}

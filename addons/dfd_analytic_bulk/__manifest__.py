# Part of DorFAdoo. See LICENSE file for full copyright and licensing details.
{
    "name": "dFd Analytic Bulk",
    "summary": "Set the analytic distribution, general account and taxes on every product line at once",
    "version": "19.0.1.4.0",
    "category": "Accounting",
    "author": "dFd",
    "license": "LGPL-3",
    "depends": [
        "account",
        "purchase",
        "sale_management",
        "analytic",
    ],
    "data": [
        "security/ir.model.access.csv",
        "wizard/dfd_analytic_bulk_apply_views.xml",
        "views/account_analytic_line_views.xml",
        "views/account_move_views.xml",
        "views/purchase_order_views.xml",
        "views/sale_order_views.xml",
    ],
    "installable": True,
    "application": False,
}

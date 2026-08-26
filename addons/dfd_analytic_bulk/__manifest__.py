# Part of DorFAdoo. See LICENSE file for full copyright and licensing details.
{
    "name": "dFd Analytic Bulk",
    "summary": "Act on every line of a document at once: analytic distribution, general account, taxes, or emptying the lines",
    "version": "19.0.1.5.1",
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

# Part of DorFAdoo. See LICENSE file for full copyright and licensing details.
{
    "name": "dFd Analytic Bulk",
    "summary": "Allocate every product line of a document to analytic accounts at once",
    "version": "19.0.1.2.0",
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
        "views/account_move_views.xml",
        "views/purchase_order_views.xml",
        "views/sale_order_views.xml",
    ],
    "installable": True,
    "application": False,
}

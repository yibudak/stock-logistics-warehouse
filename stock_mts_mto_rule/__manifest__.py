# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

{
    'name': 'Stock MTS+MTO Rule',
    'summary': 'Add a MTS+MTO route',
    'version': '12.0.1.0.2',
    'development_status': 'Mature',
    'category': 'Warehouse',
    'website': 'https://github.com/OCA/stock-logistics-warehouse',
    'author': 'Akretion,Odoo Community Association (OCA)',
    'license': 'AGPL-3',
    'application': False,
    'installable': True,
    'depends': [
        'stock',
        'stock_available_unreserved',
    ],
    'data': [
        'data/stock_data.xml',
        'view/pull_rule.xml',
        'view/warehouse.xml',
    ],
}

# -*- coding: utf-8 -*-
{
    'name': 'Ks Sales Forecast Inherit',

    'summary': """
        Add the Week option and add one selection field for choose the Sales & Quantity.
        """,

    'description': """
Add the week option inside the ks_forecast_period field and manage to display the data in the bases of weeks.
Add the one selection field which name is Sales/Quantity and if we choose the Sales then report will be display in the bases of Sales
and if we choose the Quantity option then data will be display in the bases of quantity.
""",

    'author': 'Ksolves India Ltd.',

    'maintainer': 'Ksolves India Ltd.',

    'website': 'https://store.ksolves.com/',

    'category': 'Tools',

    'support': 'sales@ksolves.com',

    'version': '16.0.1.0.0',

    'depends': ['base', 'mail', 'sale_management', 'sale', 'ks_sales_forecast'],

    'external_dependencies': {'python': ['numpy', 'scipy', 'setuptools', 'pmdarima']},

    'data': [
        'views/ks_forecast_data_inherit.xml',
    ],

}

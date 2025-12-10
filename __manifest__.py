{
    'name': 'Gestión de Reservas de Canchas Deportivas',
    'version': '17.0.1.0.0',
    'category': 'Services/Bookings',
    'summary': 'Sistema completo de reservas para canchas deportivas',
    'description': """
        Módulo completo para gestión de reservas de canchas deportivas
        =================================================================
        * Sistema de reservas con calendario interactivo
        * Gestión de múltiples canchas y deportes
        * Portal web para usuarios externos
        * Control de disponibilidad en tiempo real
        * Roles y permisos configurados
        * Reportes y estadísticas
    """,
    'author': 'Tu Empresa',
    'website': 'https://www.tuempresa.com',
    'depends': ['base', 'web', 'portal', 'mail'],
    'data': [
        # Seguridad
        'security/security.xml',
        'security/ir.model.access.csv',
        # Datos base
        'data/sports_types_data.xml',
        # Vistas backend (orden importante: primero booking, luego field)
        'views/booking_views.xml',
        'views/sports_field_views.xml',
        'views/menu_views.xml',
        # Portal
        'views/portal_templates.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'sports_booking/static/src/css/portal.css',
            'sports_booking/static/src/js/booking_calendar.js',
        ],
    },
    'demo': [],
    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'LGPL-3',
}
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class SportsField(models.Model):
    _name = 'sports.field'
    _description = 'Cancha Deportiva'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name'

    name = fields.Char(string='Nombre de la Cancha', required=True, tracking=True)
    code = fields.Char(string='Código', required=True, copy=False, tracking=True)
    sport_type = fields.Selection([
        ('futbol', 'Fútbol'),
        ('futbol_5', 'Fútbol 5'),
        ('futbol_7', 'Fútbol 7'),
        ('futbol_11', 'Fútbol 11'),
        ('volleyball', 'Volleyball'),
        ('basquet', 'Básquet'),
        ('tenis', 'Tenis'),
        ('padel', 'Pádel'),
        ('other', 'Otro'),
    ], string='Tipo de Deporte', required=True, tracking=True)
    
    description = fields.Text(string='Descripción')
    active = fields.Boolean(string='Activo', default=True, tracking=True)
    
    # Precios
    price_per_hour = fields.Float(string='Precio por Hora', required=True, default=0.0, tracking=True)
    price_weekend = fields.Float(string='Precio Fin de Semana', tracking=True)
    price_night = fields.Float(string='Precio Nocturno (después 18:00)', tracking=True)
    
    # Horarios
    opening_time = fields.Float(string='Hora Apertura', default=6.0, help='Hora en formato 24h (ej: 6.0 = 6:00 AM)')
    closing_time = fields.Float(string='Hora Cierre', default=23.0, help='Hora en formato 24h (ej: 23.0 = 11:00 PM)')
    time_slot_duration = fields.Float(string='Duración de Bloque (horas)', default=1.0, help='Duración mínima de reserva')
    
    # Características
    surface_type = fields.Selection([
        ('grass', 'Césped Natural'),
        ('synthetic', 'Césped Sintético'),
        ('concrete', 'Concreto'),
        ('parquet', 'Parquet'),
        ('clay', 'Arcilla'),
    ], string='Tipo de Superficie')
    
    has_lighting = fields.Boolean(string='Iluminación', default=True)
    has_roof = fields.Boolean(string='Techado')
    max_players = fields.Integer(string='Capacidad Máxima de Jugadores')
    
    # Imagen
    image = fields.Image(string='Imagen de la Cancha', max_width=1024, max_height=1024)
    
    # Relaciones
    booking_ids = fields.One2many('sports.booking', 'field_id', string='Reservas')
    booking_count = fields.Integer(string='Total Reservas', compute='_compute_booking_count')
    
    # Días disponibles
    available_monday = fields.Boolean(string='Lunes', default=True)
    available_tuesday = fields.Boolean(string='Martes', default=True)
    available_wednesday = fields.Boolean(string='Miércoles', default=True)
    available_thursday = fields.Boolean(string='Jueves', default=True)
    available_friday = fields.Boolean(string='Viernes', default=True)
    available_saturday = fields.Boolean(string='Sábado', default=True)
    available_sunday = fields.Boolean(string='Domingo', default=True)
    
    _sql_constraints = [
        ('code_unique', 'UNIQUE(code)', 'El código de la cancha debe ser único!'),
    ]
    
    @api.depends('booking_ids')
    def _compute_booking_count(self):
        for field in self:
            field.booking_count = len(field.booking_ids)
    
    @api.constrains('opening_time', 'closing_time')
    def _check_opening_hours(self):
        for field in self:
            if field.opening_time >= field.closing_time:
                raise ValidationError(_('La hora de cierre debe ser posterior a la hora de apertura.'))
            if field.opening_time < 0 or field.opening_time > 24:
                raise ValidationError(_('La hora de apertura debe estar entre 0 y 24.'))
            if field.closing_time < 0 or field.closing_time > 24:
                raise ValidationError(_('La hora de cierre debe estar entre 0 y 24.'))
    
    @api.constrains('time_slot_duration')
    def _check_time_slot(self):
        for field in self:
            if field.time_slot_duration <= 0 or field.time_slot_duration > 8:
                raise ValidationError(_('La duración del bloque debe estar entre 0.5 y 8 horas.'))
    
    def get_available_slots(self, date):
        """Retorna los slots disponibles para una fecha específica"""
        self.ensure_one()
        
        # Verificar día de la semana
        weekday = date.weekday()  # 0=Monday, 6=Sunday
        availability_map = {
            0: self.available_monday,
            1: self.available_tuesday,
            2: self.available_wednesday,
            3: self.available_thursday,
            4: self.available_friday,
            5: self.available_saturday,
            6: self.available_sunday,
        }
        
        if not availability_map.get(weekday, False):
            return []
        
        # Generar slots
        slots = []
        current_time = self.opening_time
        
        while current_time + self.time_slot_duration <= self.closing_time:
            slots.append({
                'start_time': current_time,
                'end_time': current_time + self.time_slot_duration,
                'available': True,
            })
            current_time += self.time_slot_duration
        
        # Verificar reservas existentes
        bookings = self.env['sports.booking'].search([
            ('field_id', '=', self.id),
            ('booking_date', '=', date),
            ('state', 'in', ['confirmed', 'pending']),
        ])
        
        for booking in bookings:
            for slot in slots:
                if (booking.start_time < slot['end_time'] and 
                    booking.end_time > slot['start_time']):
                    slot['available'] = False
        
        return slots
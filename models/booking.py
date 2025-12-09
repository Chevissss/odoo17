from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
from datetime import datetime, timedelta

class SportsBooking(models.Model):
    _name = 'sports.booking'
    _description = 'Reserva de Cancha'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'portal.mixin']
    _order = 'booking_date desc, start_time desc'
    
    name = fields.Char(string='Número de Reserva', required=True, copy=False, readonly=True, 
                       default=lambda self: _('Nuevo'))
    
    # Cliente
    partner_id = fields.Many2one('res.partner', string='Cliente', required=True, tracking=True,
                                 default=lambda self: self.env.user.partner_id)
    phone = fields.Char(string='Teléfono', related='partner_id.phone', readonly=False)
    email = fields.Char(string='Email', related='partner_id.email', readonly=False)
    
    # Cancha y fecha
    field_id = fields.Many2one('sports.field', string='Cancha', required=True, tracking=True)
    sport_type = fields.Selection(related='field_id.sport_type', string='Deporte', store=True, readonly=True)
    booking_date = fields.Date(string='Fecha de Reserva', required=True, tracking=True, 
                               default=fields.Date.today)
    
    # Horarios
    start_time = fields.Float(string='Hora Inicio', required=True, tracking=True)
    end_time = fields.Float(string='Hora Fin', required=True, tracking=True)
    duration = fields.Float(string='Duración (horas)', compute='_compute_duration', store=True)
    
    # Precio
    price_per_hour = fields.Float(string='Precio por Hora', related='field_id.price_per_hour', readonly=True)
    total_price = fields.Float(string='Precio Total', compute='_compute_total_price', store=True, tracking=True)
    
    # Estado
    state = fields.Selection([
        ('draft', 'Borrador'),
        ('pending', 'Pendiente'),
        ('confirmed', 'Confirmada'),
        ('in_progress', 'En Curso'),
        ('completed', 'Completada'),
        ('cancelled', 'Cancelada'),
    ], string='Estado', default='draft', required=True, tracking=True)
    
    # Información adicional
    notes = fields.Text(string='Notas')
    players_count = fields.Integer(string='Número de Jugadores')
    
    # Fechas de control
    create_date = fields.Datetime(string='Fecha de Creación', readonly=True)
    confirmation_date = fields.Datetime(string='Fecha de Confirmación', readonly=True, tracking=True)
    user_id = fields.Many2one('res.users', string='Responsable', default=lambda self: self.env.user, tracking=True)
    
    _sql_constraints = [
        ('check_times', 'CHECK(end_time > start_time)', 'La hora de fin debe ser posterior a la hora de inicio!'),
    ]
    
    @api.model
    def create(self, vals):
        if vals.get('name', _('Nuevo')) == _('Nuevo'):
            vals['name'] = self.env['ir.sequence'].next_by_code('sports.booking') or _('Nuevo')
        return super(SportsBooking, self).create(vals)
    
    @api.depends('start_time', 'end_time')
    def _compute_duration(self):
        for booking in self:
            booking.duration = booking.end_time - booking.start_time
    
    @api.depends('duration', 'field_id', 'booking_date', 'start_time')
    def _compute_total_price(self):
        for booking in self:
            if not booking.field_id or not booking.duration:
                booking.total_price = 0.0
                continue
            
            price = booking.field_id.price_per_hour
            
            # Aplicar precio de fin de semana
            if booking.booking_date and booking.booking_date.weekday() in [5, 6]:  # Sábado, Domingo
                if booking.field_id.price_weekend:
                    price = booking.field_id.price_weekend
            
            # Aplicar precio nocturno
            if booking.start_time >= 18.0 and booking.field_id.price_night:
                price = booking.field_id.price_night
            
            booking.total_price = price * booking.duration
    
    @api.constrains('field_id', 'booking_date', 'start_time', 'end_time', 'state')
    def _check_booking_overlap(self):
        """Valida que no haya conflictos de reservas"""
        for booking in self:
            if booking.state in ['cancelled', 'draft']:
                continue
            
            # Verificar horarios de la cancha
            if booking.start_time < booking.field_id.opening_time:
                raise ValidationError(_('La hora de inicio es anterior a la hora de apertura de la cancha.'))
            if booking.end_time > booking.field_id.closing_time:
                raise ValidationError(_('La hora de fin es posterior a la hora de cierre de la cancha.'))
            
            # Verificar disponibilidad del día
            weekday = booking.booking_date.weekday()
            availability_map = {
                0: booking.field_id.available_monday,
                1: booking.field_id.available_tuesday,
                2: booking.field_id.available_wednesday,
                3: booking.field_id.available_thursday,
                4: booking.field_id.available_friday,
                5: booking.field_id.available_saturday,
                6: booking.field_id.available_sunday,
            }
            
            if not availability_map.get(weekday, False):
                raise ValidationError(_('La cancha no está disponible en este día de la semana.'))
            
            # Buscar conflictos con otras reservas
            overlapping = self.search([
                ('id', '!=', booking.id),
                ('field_id', '=', booking.field_id.id),
                ('booking_date', '=', booking.booking_date),
                ('state', 'in', ['pending', 'confirmed', 'in_progress']),
                '|',
                '&', ('start_time', '<', booking.end_time), ('end_time', '>', booking.start_time),
                '&', ('start_time', '>=', booking.start_time), ('start_time', '<', booking.end_time),
            ])
            
            if overlapping:
                raise ValidationError(_(
                    'Ya existe una reserva para esta cancha en el horario seleccionado.\n'
                    'Reserva conflictiva: %s'
                ) % overlapping[0].name)
    
    @api.constrains('booking_date')
    def _check_booking_date(self):
        """No permitir reservas en el pasado"""
        for booking in self:
            if booking.booking_date < fields.Date.today() and booking.state == 'draft':
                raise ValidationError(_('No se pueden crear reservas para fechas pasadas.'))
    
    def action_confirm(self):
        """Confirmar la reserva"""
        for booking in self:
            if booking.state != 'draft' and booking.state != 'pending':
                raise UserError(_('Solo se pueden confirmar reservas en estado Borrador o Pendiente.'))
            booking.write({
                'state': 'confirmed',
                'confirmation_date': fields.Datetime.now(),
            })
            booking.message_post(body=_('Reserva confirmada'))
        return True
    
    def action_set_pending(self):
        """Poner en estado pendiente"""
        self.write({'state': 'pending'})
        return True
    
    def action_start(self):
        """Iniciar la reserva"""
        for booking in self:
            if booking.state != 'confirmed':
                raise UserError(_('Solo se pueden iniciar reservas confirmadas.'))
            booking.write({'state': 'in_progress'})
            booking.message_post(body=_('Reserva iniciada'))
        return True
    
    def action_complete(self):
        """Completar la reserva"""
        for booking in self:
            if booking.state != 'in_progress':
                raise UserError(_('Solo se pueden completar reservas en curso.'))
            booking.write({'state': 'completed'})
            booking.message_post(body=_('Reserva completada'))
        return True
    
    def action_cancel(self):
        """Cancelar la reserva"""
        for booking in self:
            if booking.state in ['completed', 'cancelled']:
                raise UserError(_('No se pueden cancelar reservas completadas o ya canceladas.'))
            booking.write({'state': 'cancelled'})
            booking.message_post(body=_('Reserva cancelada'))
        return True
    
    def action_reset_draft(self):
        """Volver a borrador"""
        self.write({'state': 'draft'})
        return True
    
    def _compute_access_url(self):
        """URL para portal"""
        super(SportsBooking, self)._compute_access_url()
        for booking in self:
            booking.access_url = '/my/bookings/%s' % booking.id
    
    def _get_report_base_filename(self):
        self.ensure_one()
        return 'Reserva_%s' % (self.name)

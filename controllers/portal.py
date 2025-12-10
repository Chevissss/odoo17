# -*- coding: utf-8 -*-
from odoo import http, _, fields
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal, pager as portal_pager
from odoo.exceptions import AccessError, MissingError
from datetime import datetime, timedelta
import json

class SportsBookingPortal(CustomerPortal):
    
    def _prepare_home_portal_values(self, counters):
        """Sobrescribir para agregar contador de reservas"""
        values = super()._prepare_home_portal_values(counters)
        
        # Agregar contador de reservas
        if 'booking_count' in counters:
            partner = request.env.user.partner_id
            booking_count = request.env['sports.booking'].search_count([
                ('partner_id', '=', partner.id)
            ]) if partner else 0
            values['booking_count'] = booking_count
        
        return values
    
    def _prepare_portal_layout_values(self):
        """Preparar valores base para el layout del portal"""
        values = super()._prepare_portal_layout_values()
        partner = request.env.user.partner_id
        
        # Agregar contador de reservas al layout
        booking_count = request.env['sports.booking'].search_count([
            ('partner_id', '=', partner.id)
        ]) if partner else 0
        values['booking_count'] = booking_count
        
        return values
    
    @http.route(['/my/bookings', '/my/bookings/page/<int:page>'], type='http', auth='user', website=True)
    def portal_my_bookings(self, page=1, date_begin=None, date_end=None, sortby=None, filterby=None, **kw):
        """Lista de reservas del usuario"""
        values = self._prepare_portal_layout_values()
        SportsBooking = request.env['sports.booking']
        partner = request.env.user.partner_id
        
        domain = [('partner_id', '=', partner.id)]
        
        # Filtros
        if filterby == 'upcoming':
            domain += [('booking_date', '>=', fields.Date.today()), ('state', 'in', ['confirmed', 'pending'])]
        elif filterby == 'past':
            domain += [('booking_date', '<', fields.Date.today())]
        elif filterby == 'cancelled':
            domain += [('state', '=', 'cancelled')]
        
        searchbar_sortings = {
            'date': {'label': _('Fecha'), 'order': 'booking_date desc'},
            'name': {'label': _('Referencia'), 'order': 'name desc'},
            'state': {'label': _('Estado'), 'order': 'state'},
        }
        
        searchbar_filters = {
            'all': {'label': _('Todas'), 'domain': []},
            'upcoming': {'label': _('Próximas'), 'domain': []},
            'past': {'label': _('Pasadas'), 'domain': []},
            'cancelled': {'label': _('Canceladas'), 'domain': []},
        }
        
        if not sortby:
            sortby = 'date'
        if not filterby:
            filterby = 'all'
        
        order = searchbar_sortings[sortby]['order']
        
        # Paginación
        booking_count = SportsBooking.search_count(domain)
        pager = portal_pager(
            url="/my/bookings",
            url_args={'sortby': sortby, 'filterby': filterby},
            total=booking_count,
            page=page,
            step=self._items_per_page
        )
        
        bookings = SportsBooking.search(domain, order=order, limit=self._items_per_page, offset=pager['offset'])
        
        values.update({
            'bookings': bookings,
            'page_name': 'booking',
            'default_url': '/my/bookings',
            'pager': pager,
            'searchbar_sortings': searchbar_sortings,
            'searchbar_filters': searchbar_filters,
            'sortby': sortby,
            'filterby': filterby,
        })
        
        return request.render("sports_booking.portal_my_bookings", values)
    
    @http.route(['/my/bookings/<int:booking_id>'], type='http', auth='user', website=True)
    def portal_booking_detail(self, booking_id, access_token=None, **kw):
        """Detalle de una reserva"""
        try:
            booking_sudo = self._document_check_access('sports.booking', booking_id, access_token)
        except (AccessError, MissingError):
            return request.redirect('/my')
        
        values = self._prepare_portal_layout_values()
        values.update({
            'booking': booking_sudo,
            'page_name': 'booking',
        })
        
        return request.render("sports_booking.portal_booking_detail", values)
    
    @http.route(['/bookings/new'], type='http', auth='public', website=True)
    def booking_new(self, **kw):
        """Página para crear nueva reserva"""
        if not request.env.user or request.env.user._is_public():
            return request.redirect('/web/login?redirect=/bookings/new')
        
        fields_active = request.env['sports.field'].sudo().search([('active', '=', True)], order='name')
        
        values = {
            'fields': fields_active,
            'page_name': 'new_booking',
            'today': fields.Date.today().strftime('%Y-%m-%d'),
        }
        
        return request.render("sports_booking.portal_booking_new", values)
    
    @http.route(['/bookings/available-slots'], type='json', auth='public', website=True)
    def get_available_slots(self, field_id, date, **kw):
        """API para obtener slots disponibles"""
        try:
            field = request.env['sports.field'].sudo().browse(int(field_id))
            booking_date = datetime.strptime(date, '%Y-%m-%d').date()
            
            if booking_date < fields.Date.today():
                return {'error': 'No se pueden hacer reservas para fechas pasadas'}
            
            slots = field.get_available_slots(booking_date)
            
            return {
                'success': True,
                'slots': slots,
                'field_name': field.name,
                'price_per_hour': field.price_per_hour,
            }
        except Exception as e:
            return {'error': str(e)}
    
    @http.route(['/bookings/create'], type='http', auth='user', website=True, methods=['POST'], csrf=True)
    def booking_create(self, **post):
        """Crear nueva reserva"""
        try:
            # Validar datos
            field_id = int(post.get('field_id'))
            booking_date = datetime.strptime(post.get('booking_date'), '%Y-%m-%d').date()
            start_time = float(post.get('start_time'))
            end_time = float(post.get('end_time'))
            
            # Crear reserva
            booking = request.env['sports.booking'].sudo().create({
                'partner_id': request.env.user.partner_id.id,
                'field_id': field_id,
                'booking_date': booking_date,
                'start_time': start_time,
                'end_time': end_time,
                'notes': post.get('notes', ''),
                'players_count': int(post.get('players_count', 0)) if post.get('players_count') else 0,
                'state': 'pending',
            })
            
            # Confirmar automáticamente
            booking.action_confirm()
            
            return request.redirect('/my/bookings/%s?message=success' % booking.id)
            
        except Exception as e:
            return request.redirect('/bookings/new?error=%s' % str(e))
    
    @http.route(['/bookings/cancel/<int:booking_id>'], type='http', auth='user', website=True, methods=['POST'], csrf=True)
    def booking_cancel(self, booking_id, **kw):
        """Cancelar reserva"""
        try:
            booking = request.env['sports.booking'].browse(booking_id)
            
            # Verificar permisos
            if booking.partner_id.id != request.env.user.partner_id.id:
                return request.redirect('/my/bookings?error=access_denied')
            
            # No permitir cancelar reservas pasadas o ya completadas
            if booking.state in ['completed', 'cancelled']:
                return request.redirect('/my/bookings/%s?error=cannot_cancel' % booking_id)
            
            booking.sudo().action_cancel()
            
            return request.redirect('/my/bookings/%s?message=cancelled' % booking_id)
            
        except Exception as e:
            return request.redirect('/my/bookings?error=%s' % str(e))
    
    @http.route(['/bookings/fields'], type='http', auth='public', website=True)
    def booking_fields_list(self, **kw):
        """Catálogo público de canchas"""
        sport_type = kw.get('sport_type', False)
        
        domain = [('active', '=', True)]
        if sport_type:
            domain.append(('sport_type', '=', sport_type))
        
        fields_active = request.env['sports.field'].sudo().search(domain, order='name')
        
        # Obtener tipos de deporte únicos
        sport_types = request.env['sports.field'].sudo().search([('active', '=', True)]).mapped('sport_type')
        sport_types = list(set(sport_types))
        
        values = {
            'fields': fields_active,
            'sport_types': sport_types,
            'selected_sport': sport_type,
            'page_name': 'fields_catalog',
        }
        
        return request.render("sports_booking.portal_fields_catalog", values)
from odoo import models, fields

class ResPartner(models.Model):
    _inherit = 'res.partner'
    
    booking_ids = fields.One2many('sports.booking', 'partner_id', string='Reservas')
    booking_count = fields.Integer(string='Total Reservas', compute='_compute_booking_count')
    
    def _compute_booking_count(self):
        for partner in self:
            partner.booking_count = len(partner.booking_ids)
    
    def action_view_bookings(self):
        self.ensure_one()
        return {
            'name': _('Reservas del Cliente'),
            'type': 'ir.actions.act_window',
            'view_mode': 'tree,form,calendar',
            'res_model': 'sports.booking',
            'domain': [('partner_id', '=', self.id)],
            'context': {'default_partner_id': self.id},
        }
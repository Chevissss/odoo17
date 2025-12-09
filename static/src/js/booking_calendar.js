odoo.define('sports_booking.booking_calendar', function (require) {
    'use strict';

    var publicWidget = require('web.public.widget');
    var ajax = require('web.ajax');

    publicWidget.registry.BookingCalendar = publicWidget.Widget.extend({
        selector: '#booking_form',
        events: {
            'change #field_id': '_onFieldChange',
            'change #booking_date': '_onDateChange',
            'click .time-slot': '_onSlotClick',
        },

        /**
         * Inicialización
         */
        start: function () {
            this._super.apply(this, arguments);
            this.selectedField = null;
            this.selectedDate = null;
            this.selectedSlot = null;
        },

        /**
         * Cuando cambia la cancha seleccionada
         */
        _onFieldChange: function (ev) {
            var fieldId = $(ev.currentTarget).val();
            var $option = $(ev.currentTarget).find('option:selected');
            
            if (!fieldId) {
                $('#field_info').hide();
                $('#available_slots').empty();
                $('#booking_summary').hide();
                $('#submit_button').prop('disabled', true);
                return;
            }

            this.selectedField = {
                id: fieldId,
                name: $option.text().split(' - ')[0],
                price: parseFloat($option.data('price')),
                opening: parseFloat($option.data('opening')),
                closing: parseFloat($option.data('closing'))
            };

            // Mostrar información de la cancha
            var fieldInfo = 'Precio: S/. ' + this.selectedField.price.toFixed(2) + '/hora<br/>' +
                          'Horario: ' + this._formatTime(this.selectedField.opening) + 
                          ' - ' + this._formatTime(this.selectedField.closing);
            $('#field_details').html(fieldInfo);
            $('#field_info').show();

            // Si ya hay fecha seleccionada, cargar slots
            if (this.selectedDate) {
                this._loadAvailableSlots();
            }

            this._updateSummary();
        },

        /**
         * Cuando cambia la fecha seleccionada
         */
        _onDateChange: function (ev) {
            var date = $(ev.currentTarget).val();
            
            if (!date) {
                $('#available_slots').empty();
                this.selectedDate = null;
                return;
            }

            this.selectedDate = date;

            // Validar que haya cancha seleccionada
            if (!this.selectedField) {
                alert('Por favor selecciona primero una cancha');
                $(ev.currentTarget).val('');
                return;
            }

            // Cargar slots disponibles
            this._loadAvailableSlots();
        },

        /**
         * Cargar slots disponibles mediante llamada AJAX
         */
        _loadAvailableSlots: function () {
            var self = this;
            
            if (!this.selectedField || !this.selectedDate) {
                return;
            }

            // Mostrar loading
            $('#loading_slots').show();
            $('#available_slots').empty();
            this.selectedSlot = null;
            $('#selected_slot_info').hide();
            $('#submit_button').prop('disabled', true);

            // Llamada JSON-RPC a Odoo
            ajax.jsonRpc('/bookings/available-slots', 'call', {
                field_id: this.selectedField.id,
                date: this.selectedDate
            }).then(function (result) {
                $('#loading_slots').hide();
                
                if (result.error) {
                    alert('Error: ' + result.error);
                    return;
                }

                self._renderSlots(result.slots);
            }).catch(function (error) {
                $('#loading_slots').hide();
                console.error('Error cargando slots:', error);
                alert('Error al cargar los horarios disponibles. Por favor intenta nuevamente.');
            });
        },

        /**
         * Renderizar los slots disponibles
         */
        _renderSlots: function (slots) {
            var $container = $('#available_slots');
            $container.empty();

            if (!slots || slots.length === 0) {
                $container.append(
                    '<div class="col-12">' +
                    '<div class="alert alert-warning">No hay horarios disponibles para esta fecha.</div>' +
                    '</div>'
                );
                return;
            }

            slots.forEach(function (slot) {
                var slotClass = slot.available ? 'btn-outline-success time-slot' : 'btn-secondary disabled';
                var startTime = this._formatTime(slot.start_time);
                var endTime = this._formatTime(slot.end_time);
                var duration = slot.end_time - slot.start_time;

                var $slotBtn = $('<div class="col-md-3 col-sm-4 col-6 mb-2">' +
                    '<button type="button" class="btn ' + slotClass + ' btn-block" ' +
                    (slot.available ? '' : 'disabled') + ' ' +
                    'data-start="' + slot.start_time + '" ' +
                    'data-end="' + slot.end_time + '">' +
                    '<i class="fa fa-clock-o"></i><br/>' +
                    startTime + ' - ' + endTime + '<br/>' +
                    '<small>(' + duration.toFixed(1) + ' hrs)</small>' +
                    '</button>' +
                    '</div>');

                $container.append($slotBtn);
            }.bind(this));
        },

        /**
         * Cuando se hace clic en un slot de tiempo
         */
        _onSlotClick: function (ev) {
            ev.preventDefault();
            
            var $btn = $(ev.currentTarget);
            var startTime = parseFloat($btn.data('start'));
            var endTime = parseFloat($btn.data('end'));

            // Remover selección anterior
            $('.time-slot').removeClass('btn-success').addClass('btn-outline-success');
            
            // Marcar como seleccionado
            $btn.removeClass('btn-outline-success').addClass('btn-success');

            // Guardar selección
            this.selectedSlot = {
                start: startTime,
                end: endTime,
                duration: endTime - startTime
            };

            // Actualizar campos hidden
            $('#start_time').val(startTime);
            $('#end_time').val(endTime);

            // Mostrar información del slot seleccionado
            var slotInfo = 'Horario: ' + this._formatTime(startTime) + ' - ' + this._formatTime(endTime) + '<br/>' +
                          'Duración: ' + this.selectedSlot.duration.toFixed(1) + ' horas';
            $('#slot_details').html(slotInfo);
            $('#selected_slot_info').show();

            // Actualizar resumen y habilitar botón
            this._updateSummary();
            $('#submit_button').prop('disabled', false);
        },

        /**
         * Actualizar el resumen de la reserva
         */
        _updateSummary: function () {
            if (!this.selectedField || !this.selectedDate || !this.selectedSlot) {
                $('#booking_summary').hide();
                return;
            }

            var total = this.selectedField.price * this.selectedSlot.duration;

            $('#summary_field').text(this.selectedField.name);
            $('#summary_date').text(this._formatDate(this.selectedDate));
            $('#summary_time').text(
                this._formatTime(this.selectedSlot.start) + ' - ' + 
                this._formatTime(this.selectedSlot.end)
            );
            $('#summary_duration').text(this.selectedSlot.duration.toFixed(1) + ' horas');
            $('#summary_price_hour').text('S/. ' + this.selectedField.price.toFixed(2));
            $('#summary_total').text('S/. ' + total.toFixed(2));

            $('#booking_summary').show();
        },

        /**
         * Formatear hora de decimal a HH:MM
         */
        _formatTime: function (timeDecimal) {
            var hours = Math.floor(timeDecimal);
            var minutes = Math.round((timeDecimal - hours) * 60);
            return ('0' + hours).slice(-2) + ':' + ('0' + minutes).slice(-2);
        },

        /**
         * Formatear fecha
         */
        _formatDate: function (dateStr) {
            var date = new Date(dateStr + 'T00:00:00');
            var options = { year: 'numeric', month: 'long', day: 'numeric', weekday: 'long' };
            return date.toLocaleDateString('es-ES', options);
        }
    });

    return publicWidget.registry.BookingCalendar;
});
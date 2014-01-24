# -*- coding: utf-8 -*-
from DateTime import DateTime
from Products.Five.browser import BrowserView
from Products.statusmessages.interfaces import IStatusMessage
from datetime import date
from five.formlib.formbase import PageForm
from plone import api
from plone.memoize.view import memoize
from rg.prenotazioni import (prenotazioniMessageFactory as _,
                             prenotazioniLogger as logger, time2timedelta)
from rg.prenotazioni.adapters.booker import IBooker
from rg.prenotazioni.adapters.slot import BaseSlot
from urllib import urlencode
from zope.formlib.form import FormFields, action
from zope.formlib.interfaces import WidgetInputError
from zope.interface import Interface
from zope.interface.declarations import implements
from zope.schema import Choice, TextLine, ValidationError


class InvalidDate(ValidationError):
    __doc__ = _('invalid_date')


class InvalidTime(ValidationError):
    __doc__ = _('invalid_time')


def check_date(value):
    '''
    If value exist it should match TELEPHONE_PATTERN
    '''
    if not value:
        return True
    if isinstance(value, basestring):
        value = value.strip()
    try:
        date(*map(int, value.split('/')))
        return True
    except:
        msg = 'Invalid date: %r' % value
        logger.exception(msg)
    raise InvalidDate(value)


def check_time(value):
    '''
    If value exist it should match TELEPHONE_PATTERN
    '''
    if not value:
        return True
    if isinstance(value, basestring):
        value = value.strip()
    try:
        hh, mm = map(int, value.split(':'))
        assert 0 <= hh <= 23
        assert 0 <= mm <= 59
        return True
    except:
        msg = 'Invalid time: %r' % value
        logger.exception(msg)
    raise InvalidTime(value)


class IVacationBooking(Interface):
    title = TextLine(
        title=_('label_title', u'Title'),
        description=_('description_title',
                      u'This text will appear in the calendar cells'),
        default=u'',
    )
    gate = Choice(
        title=_('label_gate', u'Gate'),
        description=_('description_gate',
                      u'The gate that will be unavailable'),
        default=u'',
        vocabulary='rg.prenotazioni.gates',
    )
    start_date = TextLine(
        title=_('label_start_date', u'Start date'),
        description=_('invalid_date'),
        constraint=check_date,
        default=u''
    )
    start_time = TextLine(
        title=_('label_start_time', u'Start time'),
        description=_('invalid_time'),
        constraint=check_time,
        default=u'00:00',
    )
    end_time = TextLine(
        title=_('label_end_time', u'End time'),
        description=_('invalid_time'),
        constraint=check_time,
        default=u'23:59'
    )


class VacationBooking(PageForm):

    '''
    This is a view that allows to book a gate for a certain period
    '''
    implements(IVacationBooking)

    def get_parsed_data(self, data):
        '''
        Return the data already parsed for our convenience
        '''
        parsed_data = data.copy()
        parsed_data['start_date'] = DateTime(data['start_date'])
        parsed_data['start_time'] = time2timedelta(data['start_time'])
        parsed_data['end_time'] = time2timedelta(data['end_time'])
        return parsed_data

    @property
    @memoize
    def prenotazioni(self):
        '''
        The prenotazioni_context_state view in the context
        '''
        return api.content.get_view('prenotazioni_context_state',
                                    self.context,
                                    self.request)

    @property
    @memoize
    def form_fields(self):
        '''
        The fields for this form
        '''
        ff = FormFields(IVacationBooking)
        today = unicode(date.today().strftime('%Y/%m/%d'))
        ff['start_date'].field.default = today
        if not self.context.getGates():
            ff = ff.omit('gate')
        return ff

    def get_start_date(self, data, asdatetime=True):
        ''' The start date we passed in the request

        By the default returns a Datetime, if asdatetime is set to True it will
        return a datetime instance
        '''
        start_date = data['start_date']
        if isinstance(start_date, basestring):
            start_date = DateTime(start_date)
        if asdatetime:
            start_date = start_date.asdatetime()
        return start_date

    def get_start_time(self, data):
        ''' The requested start time

        :returns: a datetime
        '''
        return self.get_start_date(data) + data['start_time']

    def get_end_time(self, data):
        ''' The requested end time

        :returns: a datetime
        '''
        return self.get_start_date(data) + data['end_time']

    def get_vacation_slot(self, data):
        ''' The requested vacation slot
        '''
        start_time = self.get_start_time(data)
        end_time = self.get_end_time(data)
        return BaseSlot(start_time, end_time)

    def get_slots(self, data):
        '''
        Get the slots we want to book!
        '''
        start_date = self.get_start_date(data)
        vacation_slot = self.get_vacation_slot(data)
        free_slots = self.prenotazioni.get_free_slots(start_date)
        gate = data.get('gate', '')
        gate_free_slots = free_slots.get(gate, [])
        slots = [vacation_slot.intersect(slot) for slot in gate_free_slots]
        return slots

    def set_invariant_error(self, errors, fields, msg):
        '''
        Set an error with invariant validation to highlights the involved
        fields
        '''
        for field in fields:
            label = self.widgets[field].label
            error = WidgetInputError(field, label, msg)
            errors.append(error)
            self.widgets[field].error = msg

    def has_slot_conflicts(self, data):
        ''' We want the operator to handle conflicts:
        no other booking can be created if we already have stuff
        '''
        start_date = self.get_start_date(data)
        busy_slots = self.prenotazioni.get_busy_slots(start_date)
        if not busy_slots:
            return False
        gate_busy_slots = busy_slots.get(data.get('gate', ''), [])
        if not gate_busy_slots:
            return False
        vacation_slot = self.get_vacation_slot(data)
        for slot in gate_busy_slots:
            if vacation_slot.intersect(slot):
                return True
        return False

    def is_valid_day(self, data):
        ''' Check if the day is valid
        '''
        start_date = self.get_start_date(data).date()
        return self.prenotazioni.conflict_manager.is_valid_day(start_date)

    def validate_invariants(self, data, errors):
        ''' Validate invariants errors
        '''
        parsed_data = self.get_parsed_data(data)
        if self.has_slot_conflicts(parsed_data):
            msg = _('slot_conflict_error',
                    u'This gate has some booking schedule in this time '
                    u'period.')
        elif not self.is_valid_day(data):
            msg = _('day_error',
                    u'This day is not valid.')
        else:
            msg = ''
        if not msg:
            return
        fields_to_notify = ['start_date', 'start_time', 'end_time']
        self.set_invariant_error(errors, fields_to_notify, msg)

    def validate(self, action, data):
        '''
        Checks if we can book those data
        '''
        errors = super(VacationBooking, self).validate(action, data)
        self.validate_invariants(data, errors)
        return errors

    def do_book(self, data):
        '''
        Execute the multiple booking
        '''
        booker = IBooker(self.context.aq_inner)
        slots = self.get_slots(data)
        for slot in slots:
            start_date = data['start_date']
            booking_date = start_date + (float(slot.lower_value) / 86400)
            slot.__class__ = BaseSlot
            duration = float(len(slot)) / 86400
            slot_data = {'fullname': data['title'],
                         'subject': u'',
                         'agency': u'',
                         'booking_date': booking_date,
                         'telefono': u'',
                         'mobile': u'',
                         'email': u'',
                         'tipologia_prenotazione': u'',
                         }
            booker.create(slot_data,
                          duration=duration,
                          force_gate=data.get('gate'))

        msg = _('booking_created')
        IStatusMessage(self.request).add(msg, 'info')

    @action(_('action_book', u'Book'), name=u'book')
    def action_book(self, action, data):
        '''
        Book this resource
        '''
        parsed_data = self.get_parsed_data(data)
        self.do_book(parsed_data)
        qs = {'data': self.get_start_date(data).strftime('%d/%m/%Y')}
        target = '%s?%s' % (self.context.absolute_url(), urlencode(qs))
        return self.request.response.redirect(target)

    @action(_('action_cancel', u'Cancel'), name=u'cancel')
    def action_cancel(self, action, data):
        '''
        Cancel
        '''
        target = self.context.absolute_url()
        return self.request.response.redirect(target)


class VacationBookingShow(BrowserView):

    '''
    Should this functionality be published?
    '''

    def __call__(self):
        ''' Return True for the time being
        '''
        return True

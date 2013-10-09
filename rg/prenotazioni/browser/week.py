# -*- coding: utf-8 -*-
from Products.CMFCore.utils import getToolByName
from Products.Archetypes.utils import OrderedDict
from datetime import date, timedelta
from plone.memoize.view import memoize
from rg.prenotazioni.browser.base import BaseView
from urllib import urlencode
from rg.prenotazioni.browser.prenotazioni_context_state import hm2DT


class View(BaseView):
    ''' Display appointments this week
    '''
    add_view = 'creaPrenotazione'

    @property
    @memoize
    def translation_service(self):
        ''' The translation_service tool
        '''
        return getToolByName(self.context, 'translation_service')

    @property
    @memoize
    def actual_date(self):
        """ restituisce il nome del mese e l'anno della data in request
        """
        day = self.request.get('data', '')
        if day:
            day_list = day.split('/')
            data = date(int(day_list[2]), int(day_list[1]), int(day_list[0]))
        else:
            data = self.prenotazioni.today
        return data

    @property
    @memoize
    def actual_week_days(self):
        """ The days in this week
        """
        actual_date = self.actual_date
        weekday = actual_date.weekday()
        monday = actual_date - timedelta(weekday)
        return [monday + timedelta(x) for x in range(0, 7)]

    @property
    @memoize
    def actual_translated_month(self):
        ''' The translated Full name of this month
        '''
        return self.translation_service.month(self.actual_date.month)

    @property
    @memoize
    def prev_week(self):
        """ The actual date - 7 days
        """
        return (self.actual_date - timedelta(days=7)).strftime('%d/%m/%Y')

    @property
    @memoize
    def next_week(self):
        """ The actual date + 7 days
        """
        return (self.actual_date + timedelta(days=7)).strftime('%d/%m/%Y')

    @memoize
    def isValidDay(self, day):
        """ restituisce true se il giorno è valido
        """
        if day <= self.prenotazioni.today:
            return False
        if self.conflict_manager.is_vacation_day(day):
            return False
        da_data = self.context.getDaData().strftime('%Y/%m/%d').split('/')
        a_data = self.context.getAData() and self.context.getAData().strftime('%Y/%m/%d').split('/')
        date_dadata = date(int(da_data[0]), int(da_data[1]), int(da_data[2]))
        date_adata = None
        if a_data:
            date_adata = date(int(a_data[0]), int(a_data[1]), int(a_data[2]))

        if day < date_dadata:
            return False
        if date_adata and day > date_adata:
            return False

        return True

    def get_booking_urls(self, day, period):
        ''' Returns, if possible, the booking URL
        '''
        # we have some conditions to check
        if not self.isValidDay(day):
            return []
        if not self.prenotazioni.get_day_intervals(day)[period]:
            return []
        base_url = ('%s/%s' % (self.context.absolute_url(),
                               self.add_view))
        urls = []

        for tipologia in self.context.getTipologia():
            first_slot = self.prenotazioni.get_first_slot(tipologia,
                                                          day,
                                                          period)
            if first_slot:
                booking_date = str(hm2DT(day,
                                         first_slot.start().replace(':', '')))
                options = {'form.booking_date': booking_date,
                           'form.tipology': tipologia['name'],
                           }
                urls.append({'text': '%s (%s)' % (tipologia['name'],
                                                  first_slot.start()),
                             'href': ('%s?%s' % (base_url, urlencode(options)))
                             })
        return urls

    def __call__(self):
        ''' Hide the portlets before serving the template
        '''
        self.request.set('disable_plone.leftcolumn', 1)
        self.request.set('disable_plone.rightcolumn', 1)
        return super(View, self).__call__()

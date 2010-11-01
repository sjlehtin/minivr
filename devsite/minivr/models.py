# coding=utf-8

from django.core.exceptions import ValidationError
from django.db import models

class Ticket(models.Model):
    service = models.ForeignKey('Service')
    price   = models.DecimalField(max_digits = 4, decimal_places = 2)

    def __unicode__(self):
        return unicode(self.service) + " " + unicode(self.price)

class Service(models.Model):
    train      = models.ForeignKey('Train')
    stations   = models.ManyToManyField('Station', through = 'Stop')
    free_seats = models.PositiveIntegerField()

    def departure(self):
        return self.schedule.exclude(departure_time = None).\
                             order_by('departure_time')[0]

    def arrival(self):
        return self.schedule.exclude(arrival_time = None).\
                             order_by('-arrival_time')[0]

    def clean(self):
        if self.free_seats > self.train.seats:
            raise ValidationError('A service may not have more free seats '+\
                                  'than the train can hold.')

        i = 0
        n = self.schedule.count()
        for stop in self.schedule.order_by('departure_time').iterator():
            if i == 0:
                if stop.arrival_time:
                    raise ValidationError('The first stop should lack an '+\
                                          'arrival time')
            else:
                if not stop.arrival_time:
                    raise ValidationError('Only the first stop should lack '+\
                                          'an arrival time')
            if i == n-1:
                if stop.departure_time:
                    raise ValidationError('The last stop should lack a '+\
                                          'departure time')
            else:
                if not stop.departure_time:
                    raise ValidationError('Only the last stop should lack a '+\
                                          'departure time')
            i += 1

    def __unicode__(self):
        return ' '.join([unicode(self.train), unicode(self.id)])

class Stop(models.Model):
    MONTHS = zip(xrange(1,13), ('January', 'February', 'March', 'April', 'May',
                                'June', 'July', 'August', 'September',
                                'October', 'November', 'December'))

    DAYS = zip(xrange(1,8), ('Monday', 'Tuesday', 'Wednesday', 'Thursday',
                             'Friday', 'Saturday', 'Sunday'))

    service        = models.ForeignKey('Service', related_name = 'schedule')
    station        = models.ForeignKey('Station')
    arrival_time   = models.TimeField(null = True)
    departure_time = models.TimeField(null = True)

    # The dates during which this stop is used by the service.
    year_min    = models.PositiveIntegerField(null = True)
    year_max    = models.PositiveIntegerField(null = True)
    month_min   = models.PositiveIntegerField(choices = MONTHS)
    month_max   = models.PositiveIntegerField(choices = MONTHS)
    weekday_min = models.PositiveIntegerField(choices = DAYS)
    weekday_max = models.PositiveIntegerField(choices = DAYS)

class Train(models.Model):
    name  = models.CharField(max_length = 255)
    seats = models.PositiveIntegerField()

    def __unicode__(self):
        return self.name

class Station(models.Model):
    name        = models.CharField(max_length = 255)
    connections = models.ManyToManyField('self')

    def __unicode__(self):
        return self.name

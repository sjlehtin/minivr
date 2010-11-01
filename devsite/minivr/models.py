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
        return self.schedule.all().order_by('time')[0]

    def arrival(self):
        return self.schedule.all().order_by('-time')[0]

    def clean(self):
        if self.free_seats > self.train.seats:
            raise ValidationError('A service may not have more free seats '+\
                                  'than the train can hold.')

    def __unicode__(self):
        departure = self.departure()
        return ' '.join((unicode(self.train),
                         unicode(departure.station),
                         unicode(departure.time)))

class Stop(models.Model):
    service = models.ForeignKey('Service', related_name = 'schedule')
    station = models.ForeignKey('Station')
    time    = models.TimeField()

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

# coding=utf-8

from django.core.exceptions import ValidationError
from django.db import models

class Lippu(models.Model):
    vuoro = models.ForeignKey('Vuoro')
    hinta = models.DecimalField(max_digits = 4, decimal_places = 2)

    def __unicode__(self):
        return unicode(self.vuoro) + " " + unicode(self.hinta)

class Vuoro(models.Model):
    juna = models.ForeignKey('Juna')

    # Jokaisella asemalla ei välttämättä pysähdytä, joten kaikki tulee listata.
    asemat = models.ManyToManyField('Asema')

    aika             = models.TimeField()
    paikkoja_vapaana = models.PositiveIntegerField()

    def clean(self):
        if self.paikkoja_vapaana > self.juna.paikkoja:
            raise ValidationError('Vuorossa ei voi olla enemmän vapaita '+\
                                  'paikkoja kuin junassa on tilaa.')

    def __unicode__(self):
        return unicode(self.juna) + " " + unicode(self.aika)

class Juna(models.Model):
    tyyppi   = models.CharField(max_length = 255)
    paikkoja = models.PositiveIntegerField()

    def __unicode__(self):
        return self.tyyppi

class Asema(models.Model):
    nimi     = models.CharField(max_length = 255)
    yhteydet = models.ManyToManyField('self')

    def __unicode__(self):
        return self.nimi

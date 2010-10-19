from django.db import models

# Tehty Djangon tutoriaalin ohjeen mukaan
# http://docs.djangoproject.com/en/dev/intro/tutorial01/

class Poikkeustiedote(models.Model):
    eff_date = models.DateTimeField('poikkeuksen vaikutusaika')
    message = models.CharField(max_length=1000)

from datetime import datetime,timedelta

from django import template

register = template.Library()

@register.filter
def addminutes(time, minutes):
    return (datetime(year = 2000, month = 1, day = 1,
                     hour = time.hour, minute = time.minute)
            + timedelta(minutes = minutes)).time()

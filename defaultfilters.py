#This file is part galatea app for Flask.
#The COPYRIGHT file at the top level of this repository contains
#the full copyright notices and license terms.
from flask import current_app
from flask.ext.babel import format_datetime, format_date, gettext as _
from jinja2 import evalcontextfilter, Markup, escape
from trytond.config import CONFIG as tryton_config
from wikimarkup import parse as wikiparse
from decimal import Decimal

import re
import os
try:
    from PIL import Image, ImageOps
except ImportError:
    raise RuntimeError('Image module of PIL needs to be installed')

_paragraph_re = re.compile(r'(?:\r\n|\r|\n){2,}')

@current_app.template_filter()
@evalcontextfilter
def nl2br(eval_ctx, value):
    result = u'\n\n'.join(u'<p>%s</p>' % p.replace('\n', Markup('<br/>\n')) \
        for p in _paragraph_re.split(escape(value)))
    if eval_ctx.autoescape:
        result = Markup(result)
    return result

@current_app.template_filter()
def thumbnail(filename, thumbname, size, crop=None, bg=None, quality=85):
    '''Create thumbnail image

    :param filename: image digest - '2566a0e6538be8e094431ff46ae58950'
    :param thumbname: file name image - 'test.jpg'
    :param size: size return thumb - '100x100'
    :param crop: crop return thumb - 'fit' or None
    :param bg: tuple color or None - (255, 255, 255, 0)
    :param quality: JPEG quality 1-100
    :return: :thumb_url:
    '''

    def _bg_square(img, color=0xff):
        size = (max(img.size),) * 2
        layer = Image.new('L', size, color)
        layer.paste(img, tuple(map(lambda x: (x[0] - x[1]) / 2, zip(size, img.size))))
        return layer

    def _get_name(name, fm, *args):
        for v in args:
            if v:
                name += '_%s' % v
        name += fm
        return name

    width, height = [int(x) for x in size.split('x')]
    name, fm = os.path.splitext(thumbname)

    miniature = _get_name(name, fm, size, crop, bg, quality)
    
    original_filename = os.path.join(tryton_config['data_path'], current_app.config['TRYTON_DATABASE'], filename[0:2], filename[2:4], filename)
    thumb_filename = os.path.join(current_app.config['MEDIA_CACHE_FOLDER'], miniature)

    thumb_url = os.path.join(current_app.config['MEDIA_CACHE_URL'], miniature)

    if os.path.exists(thumb_filename):
        return thumb_url
    else:
        thumb_size = (width, height)

        try:
            image = Image.open(original_filename)  
        except IOError:
            return current_app.config['BASE_IMAGE']

        if crop == 'fit':
            img = ImageOps.fit(image, thumb_size, Image.ANTIALIAS)
        else:
            img = image.copy()
            img.thumbnail((width, height), Image.ANTIALIAS)

        if bg:
            img = _bg_square(img, bg)

        img.save(thumb_filename, image.format, quality=quality)

        return thumb_url

@current_app.template_filter()
def price(price):
    '''Return price value CSS formated'''
    if not price:
        return ''
    price = Decimal("%0.2f" % (price))
    p = str(price)
    p = p.split('.')
    
    if not len(p) > 1:
        decimals = '00'
    else:
        decimals = p[1][:2]

    return '%s<span class="price-decimals">.%s</span>' % (p[0], decimals)

@current_app.template_filter()
def wikimarkup(text, show_toc=False):
    '''Return html text from wiki format'''
    return wikiparse(text, show_toc)

@current_app.template_filter()
def dateformat(value, format='medium'):
    '''Return date time to format

    date|dateformat
    date|dateformat('full')
    date|dateformat('short')
    date|dateformat('dd mm yyyy')
    '''
    return format_date(value, format)

@current_app.template_filter()
def datetimeformat(value, format='medium'):
    '''Return date time to format

    datetime|datetimeformat
    datetime|datetimeformat('full')
    datetime|datetimeformat('short')
    datetime|datetimeformat('dd mm yyyy')
    '''
    return format_datetime(value, format)

@current_app.template_filter()
def state(state):
    '''Return state value from key'''
    states = {
        'draft': _('Draft'),
        'quotation': _('Quotation'),
        'confirmed': _('Confirmed'),
        'processing': _('Processing'),
        'done': _('Done'),
        'cancel': _('Canceled'),
        'validated': _('Validated'),
        'posted': _('Posted'),
        'paid': _('Paid'),
        'received': _('Received'),
        'assigned': _('Assigned'),
        'pending': _('Pending'),
        }
    return states[state] if states.get(state) else state

@current_app.template_filter()
def quantity(qty):
    '''Return qty and decimals'''
    return Decimal("%0.0f" % (qty))

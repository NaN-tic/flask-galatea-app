#This file is part galatea app for Flask.
#The COPYRIGHT file at the top level of this repository contains
#the full copyright notices and license terms.
import os
import ConfigParser
import time
import datetime
import pytz
import logging

from flask import Flask, render_template, request, g, send_from_directory, \
    url_for, session
from flask.ext.babel import Babel, gettext as _
from werkzeug.contrib.cache import FileSystemCache
from werkzeug.contrib.fixers import ProxyFix
from werkzeug.debug import DebuggedApplication
from logging.handlers import SMTPHandler

path = os.path.dirname(os.path.realpath(__file__))

os.environ['TZ'] = 'UTC'
if hasattr(time, 'tzset'):
    time.tzset()

def get_config():
    '''Get configuration from cfg file'''
    conf_file = '%s/config.ini' % os.path.dirname(os.path.realpath(__file__))
    config = ConfigParser.ConfigParser()
    config.read(conf_file)

    results = {}
    for section in config.sections():
        results[section] = {}
        for option in config.options(section):
            results[section][option] = config.get(section, option)
    return results

def create_app(config=None):
    '''Create Flask APP'''
    cfg = get_config()
    app_name = cfg['flask']['app_name']
    app = Flask(app_name)
    app.config.from_pyfile(config)

    return app

def parse_setup(filename):
    globalsdict = {}  # put predefined things herec
    localsdict = {}  # will be populated by executed script
    execfile(filename, globalsdict, localsdict)
    return localsdict

def get_default_lang():
    return app.config.get('LANGUAGE')

def get_languages():
    languages = app.config.get('ACCEPT_LANGUAGES')
    if not languages:
        return None
    return [k.split('_')[0] for k, v in languages.iteritems()]

conf_file = '%s/config.cfg' % path

app = create_app(conf_file)
app.config['BABEL_DEFAULT_LOCALE'] = get_default_lang()
app.root_path = os.path.dirname(os.path.abspath(__file__))

TIMEZONE = None
if app.config.get('TIMEZONE'):
    TIMEZONE = pytz.timezone(app.config.get('TIMEZONE'))

babel = Babel(app)
app.cache = FileSystemCache(cache_dir=app.config['CACHE_DIR'], default_timeout=app.config['CACHE_TIMEOUT'])

if app.config.get('DEBUG'):
    app.wsgi_app = DebuggedApplication(app.wsgi_app, True)

# tryton transaction
ctx = app.app_context()
ctx.push()
from galatea.tryton import tryton

from galatea.sessions import GalateaSessionInterface
app.session_interface = GalateaSessionInterface()

from galatea.helpers import cached, login_required
from galatea.utils import get_tryton_language, get_tryton_locale

# register Blueprints - modules
from galatea import galatea
app.register_blueprint(galatea, url_prefix='/<lang>')
from galatea_file import galatea_file
app.register_blueprint(galatea_file)

# context procesors and filters
import context_processors
import defaultfilters

@babel.localeselector
def get_locale():
    lang = request.path[1:].split('/', 1)[0]
    if lang in get_languages():
        return lang
    else:
        return get_default_lang()

@app.before_request
def func():
    g.babel = babel
    g.language = get_locale()
    g.today = datetime.datetime.now(TIMEZONE).date()
    g.now = datetime.datetime.now(TIMEZONE)

@app.errorhandler(404)
@tryton.transaction()
def page_not_found(e):
    return render_template('404.html'), 404

@app.errorhandler(500)
def server_error(e):
    return render_template('500.html'), 500

@tryton.default_context
def default_context():
    context = {}
    context['language'] = get_tryton_language(g.language)
    context['locale'] = get_tryton_locale(g.language)
    context['company'] = app.config.get('TRYTON_COMPANY')
    context['shop'] = app.config.get('TRYTON_SALE_SHOP')
    context['shops'] = app.config.get('TRYTON_SALE_SHOPS')
    context['locations'] = app.config.get('TRYTON_LOCATIONS')
    context['customer'] = session.get('customer', None)
    return context

@app.route('/')
@app.route("/en/", endpoint="en")
@app.route("/es/", endpoint="es")
@app.route("/ca/", endpoint="ca")
@tryton.transaction()
def index():
    '''Home'''
    return render_template('index.html')

@app.route('/sitemap.xml')
@tryton.transaction()
@cached(3500, 'sitemap')
def sitemap():
    '''Sitemap: Generate Sitemap XML'''
    galatea_website = app.config.get('TRYTON_GALATEA_SITE')
    shops = app.config.get('TRYTON_SALE_SHOPS')

    Article = tryton.pool.get('galatea.cms.article')
    Template = tryton.pool.get('product.template')

    locs = []
    # Articles
    articles = Article.search_read([
        ('active', '=', True),
        ('galatea_website', '=', galatea_website),
        ], fields_names = ['slug_langs'])
    for article in articles:
        for k, v in article['slug_langs'].items():
            locale = k[:2]
            locs.append(url_for('cms.article', lang=locale, slug=v))

    # Products
    products = Template.search_read([
        ('esale_active', '=', True),
        ('esale_saleshops', 'in', shops),
        ], fields_names = ['esale_slug_langs'])
    for product in products:
        for k, v in product['esale_slug_langs'].items():
            locale = k[:2]
            locs.append(url_for('catalog.product_'+locale, lang=locale, slug=v))

    return render_template('sitemap.xml', locs=locs)

@app.route('/media/cache/<filename>')
def media_file(filename):
    return send_from_directory(app.config['MEDIA_CACHE_FOLDER'], filename)

app.wsgi_app = ProxyFix(app.wsgi_app)

if not app.debug:
    mail_handler = SMTPHandler(mailhost=app.config.get('MAIL_SERVER'),
                            fromaddr=app.config.get('DEFAULT_MAIL_SENDER'),
                            toaddrs=app.config.get('ADMINS'),
                            subject='Flask %s Failed' % app.config.get('TITLE'),
                            credentials=app.config.get('MAIL_CREDENTIALS', None),
                            secure=app.config.get('MAIL_SECURE', None))
    mail_handler.setLevel(logging.ERROR)
    app.logger.addHandler(mail_handler)

if __name__ == "__main__":
    app.run()

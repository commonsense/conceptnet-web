"""
This file sets up Flask to serve the ConceptNet 5 API in JSON-LD format.
"""
from conceptnet_web import responses
from conceptnet_web.filters import FILTERS
from conceptnet_web.relations import REL_HEADINGS
from conceptnet_web.responses import VALID_KEYS
import flask
from flask_limiter import Limiter
import os


# Configuration

WORKING_DIR = os.getcwd()
STATIC_PATH = os.environ.get('CONCEPTNET_WEB_STATIC', os.path.join(WORKING_DIR, 'static'))
TEMPLATE_PATH = os.environ.get('CONCEPTNET_WEB_TEMPLATES', os.path.join(WORKING_DIR, 'templates'))

app = flask.Flask(
    'conceptnet5_web',
    template_folder=TEMPLATE_PATH,
    static_folder=STATIC_PATH
)
for filter_name, filter_func in FILTERS.items():
    app.jinja_env.filters[filter_name] = filter_func
limiter = Limiter(app, global_limits=["600 per minute", "6000 per hour"])


def get_int(args, key, default, minimum, maximum):
    strvalue = args.get(key, default)
    try:
        value = int(strvalue)
    except ValueError:
        value = default
    return max(minimum, min(maximum, value))


# Lookup: match any path starting with /a/, /c/, /d/, /r/, or /s/
# @app.route('/<any(a, c, d, r, s):top>/<path:query>')


@app.route('/c/<path:uri>')
def browse_concept(uri):
    req_args = flask.request.args
    concept = '/c/%s' % uri
    limit = get_int(req_args, 'limit', 20, 0, 1000)
    filters = {}
    for key in VALID_KEYS:
        if key != 'node' and key in req_args:
            filters[key] = req_args[key]
    results = responses.lookup_grouped_by_feature(concept, filters, group_limit=limit)
    sources = []
    for feature in results['features']:
        rel = feature['feature']['rel']
        if rel in REL_HEADINGS['en']:
            label_choices = REL_HEADINGS['en'][rel]
        else:
            label_choices = ['%s {0}' % rel, '{0} %s' % rel]

        if feature['symmetric'] or 'end' in feature['feature']:
            feat_label = label_choices[0]
        else:
            feat_label = label_choices[1]
        feature['label'] = feat_label.format(results['label'])
        for edge in feature['edges']:
            sources.extend(edge['sources'])

    return flask.render_template(
        'node_by_feature.html', term=results, features=results['features'], sources=sources
    )


# Lookup: match any path starting with /a/, /c/, /d/, /r/, or /s/
@app.route('/<any(a, d, r, s):top>/<path:query>')
def browse_node(top, query):
    req_args = flask.request.args
    path = '/%s/%s' % (top, query.strip('/'))
    offset = get_int(req_args, 'offset', 0, 0, 100000)
    limit = get_int(req_args, 'limit', 50, 0, 1000)
    results = responses.lookup_paginated(path, offset=offset, limit=limit)
    sources = []
    for edge in results['edges']:
        sources.extend(edge['sources'])
    return flask.render_template(
        'edge_list.html', results=results, sources=sources
    )


@app.route('/query')
def query():
    req_args = flask.request.args
    criteria = {}
    offset = get_int(req_args, 'offset', 0, 0, 100000)
    limit = get_int(req_args, 'limit', 50, 0, 1000)
    for key in flask.request.args:
        if key in VALID_KEYS:
            criteria[key] = flask.request.args[key]
    results = responses.query_paginated(criteria, offset=offset, limit=limit)
    sources = []
    for edge in results['edges']:
        sources.extend(edge['sources'])
    return flask.render_template(
        'edge_list.html', results=results, sources=sources
    )


if __name__ == '__main__':
    app.debug = True
    app.run('127.0.0.1', debug=True, port=8084)

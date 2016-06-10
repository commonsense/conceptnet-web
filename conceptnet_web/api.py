"""
This file sets up Flask to serve the ConceptNet 5 API in JSON-LD format.
"""
from conceptnet_web.json_rendering import jsonify, highlight_and_link_json
from conceptnet_web import responses
from conceptnet_web.responses import FINDER, VALID_KEYS
import flask
from flask_cors import CORS
from flask_limiter import Limiter
import os
# TODO: vector wrapper


# Configuration

WORKING_DIR = os.getcwd()
STATIC_PATH = os.environ.get('CONCEPTNET_WEB_STATIC', os.path.join(WORKING_DIR, 'static'))
TEMPLATE_PATH = os.environ.get('CONCEPTNET_WEB_TEMPLATES', os.path.join(WORKING_DIR, 'templates'))

app = flask.Flask(
    'conceptnet5',
    template_folder=TEMPLATE_PATH,
    static_folder=STATIC_PATH
)
app.config['JSON_AS_ASCII'] = False
app.jinja_env.filters['highlight_json'] = highlight_and_link_json
app.jinja_env.add_extension('jinja2_highlight.HighlightExtension')
limiter = Limiter(app, global_limits=["600 per minute", "6000 per hour"])
CORS(app)


# Lookup: match any path starting with /a/, /c/, /d/, /r/, or /s/
@app.route('/<any(a, c, d, r, s):top>/<path:query>')
def query_node(top, query):
    req_args = flask.request.args
    path = '/%s/%s' % (top, query.strip('/'))
    offset = int(req_args.get('offset', 0))
    offset = max(0, offset)
    limit = int(req_args.get('limit', 50))
    limit = max(0, min(limit, 1000))
    grouped = req_args.get('grouped', 'false').lower() == 'true'
    if grouped:
        limit = min(limit, 100)
        results = responses.lookup_grouped_by_feature(FINDER, path, group_limit=limit)
    else:
        results = responses.lookup_paginated(FINDER, path, offset=offset, limit=limit)
    return jsonify(results)


@app.route('/search')
@app.route('/query')
def query():
    criteria = {}
    offset = int(flask.request.args.get('offset', 0))
    offset = max(0, offset)
    limit = int(flask.request.args.get('limit', 50))
    limit = max(0, min(limit, 1000))
    for key in flask.request.args:
        if key in VALID_KEYS:
            criteria[key] = flask.request.args[key]
    results = query_paginated(FINDER, criteria, offset=offset, limit=limit)
    return jsonify(results)


@app.route('/uri')
@app.route('/normalize')
@app.route('/standardize')
def standardize_uri():
    """
    Look up the URI for a given piece of text. 'text' and 'language' should be
    given as parameters.
    """
    language = flask.request.args.get('language')
    text = flask.request.args.get('text') or flask.request.args.get('term')
    return jsonify(standardize_uri(language, text))


@app.route('/')
def see_documentation():
    """
    This function redirects to the api documentation
    """
    return jsonify({
        '@context': responses.CONTEXT
    })


@app.route('/assoc/list/<lang>/<path:termlist>')
@limiter.limit("60 per minute")
def list_assoc(lang, termlist):
    if isinstance(termlist, bytes):
        termlist = termlist.decode('utf-8')

    terms = []
    term_pieces = termlist.split(',')
    for piece in term_pieces:
        piece = piece.strip()
        if '@' in piece:
            term, weight = piece.split('@')
            weight = float(weight)
        else:
            term = piece
            weight = 1.
        terms.append(('/c/%s/%s' % (lang, term), weight))

    return assoc_for_termlist(terms)


def assoc_for_termlist(terms):
    limit = flask.request.args.get('limit', '20')
    limit = max(0, min(int(limit), 1000))
    filter = flask.request.args.get('filter')

    similar = ASSOC_WRAPPER.associations(terms, filter=filter, limit=limit)
    return flask.jsonify({'terms': terms, 'similar': similar})


@app.route('/assoc/<path:uri>')
@limiter.limit("60 per minute")
def concept_assoc(uri):
    uri = '/' + uri.rstrip('/')
    return assoc_for_termlist([(uri, 1.0)])


if __name__ == '__main__':
    app.debug = True
    app.run('127.0.0.1', debug=True, port=8084)

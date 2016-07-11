"""
This file sets up Flask to serve the ConceptNet 5 API in JSON-LD format.
"""
from conceptnet_web import responses
from conceptnet_web.filters import FILTERS
from conceptnet_web.relations import REL_HEADINGS
from conceptnet5.edges import ld_node
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
def query_node(uri):
    req_args = flask.request.args
    path = '/c/%s' % uri
    limit = get_int(req_args, 'limit', 50, 0, 100)
    results = responses.lookup_grouped_by_feature(path, group_limit=limit)

    term = ld_node(results['@id'])
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
        feature['label'] = feat_label.format(term['label'])

    return flask.render_template(
        'node_by_feature.html', term=term, features=results['features']
    )


if __name__ == '__main__':
    app.debug = True
    app.run('127.0.0.1', debug=True, port=8084)

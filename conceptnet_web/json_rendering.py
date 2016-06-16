from pygments.formatters import HtmlFormatter
from pygments.lexers import get_lexer_by_name
from pygments import highlight
from jinja2.ext import Markup
import flask
import re
import json


def request_wants_json():
    best = flask.request.accept_mimetypes \
        .best_match(['application/ld+json', 'application/json', 'text/html'])
    return 'json' in best


def regex_replacement_stack(replacements):
    compiled_replacers = [(re.compile(match), replace) for (match, replace) in replacements]
    def _replace(text):
        for compiled_re, replacement in compiled_replacers:
            text = compiled_re.sub(replacement, text)
        return text
    return _replace


linker = regex_replacement_stack([
    (r'/l/CC/By-SA', r'cc:by-sa/4.0'),
    (r'/l/CC/By', r'cc:by/4.0'),
    (r'&quot;((https?://|/[acdrs]/)([^& ]|&amp;)*)&quot;', r'&quot;<a href="\1">\1</a>&quot;'),
    (r'&quot;cc:([^& ]+)&quot;', r'&quot;<a href="http://creativecommons.org/licenses/\1">cc:\1</a>&quot;')
])


def highlight_and_link_json(content):
    formatter = HtmlFormatter()
    lexer = get_lexer_by_name('json')
    html = highlight(content, lexer, formatter)
    urlized_html = linker(html)
    return Markup(urlized_html)


def jsonify(obj):
    if flask.request is None or request_wants_json():
        return flask.Response(
            json.dumps(obj, ensure_ascii=False, sort_keys=True),
            mimetype='application/json'
        )
    else:
        pretty_json = json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=2)
        ugly_json = json.dumps(obj, ensure_ascii=False, sort_keys=True)
        return flask.render_template(
            'json.html',
            json=pretty_json,
            json_raw=ugly_json
        )


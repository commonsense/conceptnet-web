from jinja2.ext import Markup
from conceptnet5.nodes import get_language_name
from .json_rendering import highlight_and_link_json


def describe_term_language(lang, description_language='en'):
    if description_language != 'en':
        raise NotImplementedError(
            "We don't support non-English interface text yet."
        )

    language_name = get_language_name(lang, description_language)
    if language_name[0] in 'AEIOU' and not language_name.startswith('Uk'):
        article = 'An'
    else:
        article = 'A'

    content = '{article} <a href="/c/{lang}">{language_name}</a> term'
    return Markup(content)


FILTERS = {
    'highlight_json': highlight_and_link_json,
    'describe_term_language': describe_term_language
}
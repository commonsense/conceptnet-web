from conceptnet5.vectors.query import VectorSpaceWrapper
from conceptnet5.query import field_match, VALID_KEYS
from conceptnet5.db.query import MAX_GROUP_SIZE
from conceptnet5.nodes import standardized_concept_uri
from conceptnet5.nodes import ld_node
import itertools

VECTORS = VectorSpaceWrapper()
FINDER = VECTORS.finder
VALID_KEYS = VALID_KEYS   # re-export
CONTEXT = [
    "http://api.conceptnet.io/ld/conceptnet5.5/context.ld.json",
    "http://api.conceptnet.io/ld/conceptnet5.5/pagination.ld.json"
]


def success(response):
    response['@context'] = CONTEXT
    return response


def error(response, status, details):
    response['@context'] = CONTEXT
    response['error'] = {
        'status': status,
        'details': details
    }
    return response


def make_query_url(url, items):
    str_items = ['{}={}'.format(*item) for item in items]
    if not str_items:
        return url
    else:
        return url + '?' + ('&'.join(str_items))


def groupkey_to_pairs(groupkey, term):
    direction, rel = groupkey
    if direction == 1:
        return [('rel', rel), ('start', term)]
    elif direction == -1:
        return [('rel', rel), ('end', term)]
    else:
        return [('rel', rel), ('node', term)]


def paginated_url(url, params, offset, limit):
    new_params = [
        (key, val) for (key, val) in params
        if key != 'offset' and key != 'limit'
    ] + [('offset', offset), ('limit', limit)]
    return make_query_url(url, new_params)


def make_paginated_view(url, params, offset, limit, more):
    prev_offset = max(0, offset - limit)
    next_offset = offset + limit
    pager = {
        '@id': paginated_url(url, params, offset, limit),
        'firstPage': paginated_url(url, params, 0, limit),
        'paginatedProperty': 'edges'
    }
    if offset > 0:
        pager['previousPage'] = paginated_url(url, params, prev_offset, limit)
    if more:
        pager['nextPage'] = paginated_url(url, params, next_offset, limit)
    return pager


def transform_directed_edge(edge, node):
    if field_match(edge['start']['@id'], node):
        edge['node'] = edge['start']
        edge['other'] = edge['end']
    elif field_match(edge['end']['@id'], node):
        edge['node'] = edge['end']
        edge['other'] = edge['start']
    else:
        raise ValueError(
            "Neither the start nor end of this edge matches "
            "the node %r: %r" % (node, edge)
        )
    return edge


def lookup_grouped_by_feature(term, filters=None, scan_limit=1000, group_limit=10):
    """
    Given a query for a concept, return assertions about that concept grouped by
    their features (for example, "A dog wants to ..." could be a group).

    It will scan up to `scan_limit` assertions to find out which features exist,
    then retrieve `group_limit` assertions for each feature if possible.
    """
    if not term.startswith('/c/'):
        return error(
            {}, 400,
            'Only concept nodes (starting with /c/) can be grouped by feature.'
        )

    found = FINDER.lookup_grouped_by_feature(term)
    grouped = []
    for groupkey, assertions in found.items():
        direction, rel = groupkey
        base_url = '/query'
        feature_pairs = groupkey_to_pairs(groupkey, term)
        url = make_query_url(base_url, feature_pairs)
        symmetric = direction == 0
        group = {
            '@id': url,
            'weight': sum(assertion['weight'] for assertion in assertions),
            'feature': dict(feature_pairs),
            'edges': assertions[:MAX_GROUP_SIZE],
            'symmetric': symmetric
        }
        if len(assertions) > MAX_GROUP_SIZE:
            view = make_paginated_view(base_url, feature_pairs, 0, group_limit, more=True)
            group['view'] = view

        grouped.append(group)

    grouped.sort(key=lambda g: -g['weight'])
    for group in grouped:
        del group['weight']

    response = ld_node(term)
    if not grouped and filters is None:
        return error(response, 404, '%r is not a node in ConceptNet.' % term)
    else:
        response['features'] = grouped
        return success(response)


def lookup_paginated(term, offset=0, limit=50):
    # Query one more edge than asked for, so we know if there are more
    found = list(itertools.islice(FINDER.lookup(term), offset, offset + limit + 1))
    edges = found[:limit]
    response = {
        '@id': term,
        'edges': edges
    }
    more = len(found) > len(edges)
    if len(found) > len(edges) or offset != 0:
        response['view'] = make_paginated_view(
            term, (), offset, limit, more=more
        )
    if not found:
        return error(response, 404, '%r is not a node in ConceptNet.' % term)
    else:
        return success(response)


def query_related(uri, filter=None, limit=20):
    if uri.startswith('/c/'):
        query = uri
    elif uri.startswith('/list/') and uri.count('/') >= 3:
        try:
            _, _list, language, termlist = uri.split('/', 3)
            query = []
            term_pieces = termlist.split(',')
            for piece in term_pieces:
                if '@' in piece:
                    term, weight = piece.split('@')
                    weight = float(weight)
                else:
                    term = piece
                    weight = 1.
                query.append(('/c/{}/{}'.format(language, term), weight))
        except ValueError:
            return error(
                {'@id': uri}, 400,
                "Couldn't parse this term list: %r" % uri
            )
    else:
        return error(
            {'@id': uri}, 404,
            '%r is not something that I can find related terms to.' % uri
        )

    found = VECTORS.similar_terms(query, filter=filter, limit=limit)
    related = [
        {'@id': key, 'weight': round(float(weight), 3)}
        for (key, weight) in found.items()
    ]
    response = {
        '@id': uri,
        'related': related
    }
    return response


def query_paginated(query, offset=0, limit=50):
    found = FINDER.query(query, limit=limit + 1, offset=offset, scan_limit=limit * 4)
    edges = found[:limit]
    response = {
        '@id': make_query_url('/query', query.items()),
        'edges': edges
    }
    more = len(found) > len(edges)
    if len(found) > len(edges) or offset != 0:
        response['view'] = make_paginated_view(
            '/query', sorted(query.items()), offset, limit, more=more
        )
    return success(response)


def standardize_uri(language, text):
    """
    Look up the URI for a given piece of text. 'text' and 'language' should be
    given as parameters.
    """
    if text is None or language is None:
        return error({}, 400, "You should include the 'text' and 'language' parameters.")

    text = text.replace('_', ' ')
    uri = standardized_concept_uri(language, text)
    response = {
        '@id': uri
    }
    return success(response)

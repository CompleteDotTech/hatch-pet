"""Declarative visual styles: strict metadata, discovery and frozen run specifications.

Only JSON data is loaded. Catalog edits affect new preparations, never existing runs.
The standard library is sufficient; profile geometry and generation backends live elsewhere.
"""
from __future__ import annotations

import copy
import difflib
from functools import lru_cache
import hashlib
import json
from pathlib import Path
import re
import unicodedata

CATALOG_PATH = Path(__file__).resolve().parents[1] / 'styles' / 'catalog.json'
SCHEMA_VERSION = 1
INSTRUCTION_FIELDS = ('materials', 'forms', 'linework', 'shading', 'palette', 'texture', 'rendering')
APPLICABILITY = ('character', 'sequence', 'icon', 'print', 'grid')
RESAMPLING = ('nearest', 'bilinear', 'bicubic', 'lanczos')
ORIGINAL_PRESETS = ('auto', 'pixel', 'plush', 'clay', 'sticker', 'flat-vector', '3d-toy', 'painterly', 'brand-inspired')
MAX_FILE_BYTES = 2 * 1024 * 1024
MAX_STYLES = 4096
MAX_MODIFIERS = 4
MAX_CONTRACT_CHARS = 16000
_SLUG = re.compile(r'[a-z0-9]+(?:-[a-z0-9]+)*\Z')
_UNSAFE_TEXT = re.compile(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f\u202a-\u202e\u2066-\u2069]')


def digest(value):
    """Hash canonical UTF-8 JSON independently of file indentation/key ordering."""
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                    ensure_ascii=False, allow_nan=False).encode('utf-8')).hexdigest()


def _keys(value, required, optional=(), label='style'):
    if not isinstance(value, dict):
        raise ValueError(label + ' must be an object')
    missing, extra = set(required) - set(value), set(value) - set(required) - set(optional)
    if missing or extra:
        raise ValueError(f'{label}: missing fields {sorted(missing)}; unknown fields {sorted(map(str, extra))}')


def _text(value, label, minimum=1, maximum=1000):
    if (not isinstance(value, str) or not minimum <= len(value.strip()) <= maximum
            or _UNSAFE_TEXT.search(value)):
        raise ValueError(f'{label} needs {minimum}..{maximum} characters of safe text')
    return value


def _slug(value, label):
    if not isinstance(value, str) or len(value) > 64 or not _SLUG.fullmatch(value):
        raise ValueError(label + ' must be a stable lowercase kebab-case ID (maximum 64 characters)')
    return value


def _strings(value, label, minimum=0, maximum=32, slugs=False):
    if not isinstance(value, list) or not minimum <= len(value) <= maximum:
        raise ValueError(f'{label} must contain {minimum}..{maximum} strings')
    for item in value:
        (_slug if slugs else _text)(item, label)
    if len(set(s.casefold() for s in value)) != len(value):
        raise ValueError(label + ' has duplicate values')
    return value


def _enum(value, allowed, label):
    if not isinstance(value, str) or value not in allowed:
        raise ValueError(label + ' must be one of ' + ', '.join(allowed))


def _version(value, label='schema_version'):
    if type(value) is not int or value != SCHEMA_VERSION:
        raise ValueError(label + ' must be 1')


def _catalog_version(value):
    if not isinstance(value, str) or not re.fullmatch(r'[0-9]+\.[0-9]+\.[0-9]+', value) or len(value) > 32:
        raise ValueError('catalog_version must be a semantic version such as 1.0.0')


def validate_style(value):
    required = ('id', 'name', 'category', 'kind', 'description', 'tags', 'aliases', 'instructions',
                'negative_constraints', 'use_cases', 'limitations', 'applicability', 'compatibility')
    _keys(value, required, ('recommended_modifiers',), 'style')
    label = 'style ' + _slug(value['id'], 'style.id')
    _slug(value['category'], label + '.category')
    _enum(value['kind'], ('technique', 'treatment', 'adaptive'), label + '.kind')
    _text(value['name'], label + '.name', maximum=120)
    _text(value['description'], label + '.description', minimum=20)
    _strings(value['tags'], label + '.tags', minimum=2)
    _strings(value['aliases'], label + '.aliases', slugs=True)
    _keys(value['instructions'], INSTRUCTION_FIELDS, label=label + '.instructions')
    for key, text in value['instructions'].items():
        _text(text, label + '.instructions.' + key, minimum=20, maximum=800)
    if len(set(value['instructions'].values())) != len(INSTRUCTION_FIELDS):
        raise ValueError(label + ': incomplete instructions; each artistic dimension needs its own direction')
    for key, minimum in (('negative_constraints', 2), ('use_cases', 1), ('limitations', 1)):
        _strings(value[key], label + '.' + key, minimum=minimum)
    positive = {_search_text(x) for x in value['instructions'].values()}
    if positive & {_search_text(x) for x in value['negative_constraints']}:
        raise ValueError(label + ': contradictory positive and negative instructions')
    _keys(value['applicability'], APPLICABILITY, label=label + '.applicability')
    for key, setting in value['applicability'].items():
        _enum(setting, ('recommended', 'adapted', 'unsuitable'), label + '.applicability.' + key)
    c = value['compatibility']
    _keys(c, ('alpha', 'chroma', 'edge_mode', 'resampling', 'scaling', 'notes'), label=label + '.compatibility')
    for key, allowed in (('alpha', ('supported', 'preferred', 'required')),
                         ('chroma', ('supported', 'caution', 'unsupported')),
                         ('edge_mode', ('hard', 'antialiased')), ('resampling', RESAMPLING)):
        _enum(c[key], allowed, label + '.compatibility.' + key)
    _text(c['scaling'], label + '.compatibility.scaling', minimum=20)
    _strings(c['notes'], label + '.compatibility.notes', minimum=1)
    if c['alpha'] == 'required' and c['chroma'] != 'unsupported':
        raise ValueError(label + ': conflicting restrictions: required alpha cannot support chroma')
    if c['chroma'] == 'unsupported' and c['alpha'] != 'required':
        raise ValueError(label + ': unsupported chroma requires explicit alpha requirement')
    if c['edge_mode'] == 'hard' and c['resampling'] != 'nearest':
        raise ValueError(label + ': conflicting hard-edge and smoothing resampling restrictions')
    _strings(value.get('recommended_modifiers', []), label + '.recommended_modifiers', slugs=True)
    return copy.deepcopy(value)


def validate_modifier(value):
    _keys(value, ('id', 'name', 'description', 'instructions', 'negative_constraints', 'aliases', 'conflicts'), label='modifier')
    label = 'modifier ' + _slug(value['id'], 'modifier.id')
    _text(value['name'], label + '.name', maximum=120)
    _text(value['description'], label + '.description', minimum=20)
    _text(value['instructions'], label + '.instructions', minimum=20, maximum=800)
    _strings(value['negative_constraints'], label + '.negative_constraints', minimum=1)
    _strings(value['aliases'], label + '.aliases', slugs=True)
    _strings(value['conflicts'], label + '.conflicts', slugs=True)
    if value['id'] in value['conflicts']:
        raise ValueError(label + ' cannot conflict with itself')
    return copy.deepcopy(value)


def _names(entries, label):
    ids = [e['id'] for e in entries]
    if len(set(ids)) != len(ids):
        raise ValueError('duplicate ' + label + ' IDs')
    names = set(ids)
    for entry in entries:
        for alias in entry['aliases']:
            if alias in names:
                raise ValueError('invalid alias collision in ' + label + ': ' + alias)
            names.add(alias)
    return names


def _categories(values):
    if not isinstance(values, list) or not 1 <= len(values) <= 128:
        raise ValueError('categories must contain 1..128 category records')
    for value in values:
        _keys(value, ('id', 'name'), label='category')
        _slug(value['id'], 'category.id')
        if value['id'] in ('catalog', 'modifiers', 'con', 'prn', 'aux', 'nul') or re.fullmatch(r'(?:com|lpt)[1-9]', value['id']):
            raise ValueError('reserved category filename: ' + value['id'])
        _text(value['name'], 'category.name', maximum=120)
    ids = [c['id'] for c in values]
    if len(set(ids)) != len(ids):
        raise ValueError('duplicate category IDs')
    return set(ids)


def validate_catalog(value):
    _keys(value, ('schema_version', 'catalog_version', 'categories', 'styles', 'modifiers'), label='catalog')
    _version(value['schema_version'])
    _catalog_version(value['catalog_version'])
    categories = _categories(value['categories'])
    if not isinstance(value['styles'], list) or not 1 <= len(value['styles']) <= MAX_STYLES:
        raise ValueError(f'catalog.styles must contain 1..{MAX_STYLES} styles')
    if not isinstance(value['modifiers'], list) or len(value['modifiers']) > 128:
        raise ValueError('catalog.modifiers must contain at most 128 modifiers')
    styles = [validate_style(v) for v in value['styles']]
    modifiers = [validate_modifier(v) for v in value['modifiers']]
    _names(styles, 'style')
    _names(modifiers, 'modifier')
    if {v['category'] for v in styles} != categories:
        raise ValueError('unknown or empty style category')
    modifier_ids = {v['id'] for v in modifiers}
    for style in styles:
        if set(style.get('recommended_modifiers', [])) - modifier_ids:
            raise ValueError('style references unknown modifiers: ' + style['id'])
    by_modifier = {v['id']: v for v in modifiers}
    for modifier in modifiers:
        if set(modifier['conflicts']) - modifier_ids:
            raise ValueError('unknown modifier conflict: ' + modifier['id'])
        if any(modifier['id'] not in by_modifier[m]['conflicts'] for m in modifier['conflicts']):
            raise ValueError('modifier conflicts must be symmetric')
    return copy.deepcopy(value)


def _json_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate JSON field: ' + key)
        result[key] = value
    return result


def _read_json(path):
    path = Path(path)
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_FILE_BYTES:
        raise ValueError('catalog data must be a regular JSON file no larger than 2 MiB: ' + str(path))
    return json.loads(path.read_text(encoding='utf-8'), object_pairs_hook=_json_pairs,
                      parse_constant=lambda x: (_ for _ in ()).throw(ValueError('nonfinite JSON value: ' + x)))


def load_catalog(path=None):
    """Load a bounded explicit category index, with no directory/plugin discovery."""
    path = Path(path or CATALOG_PATH)
    index = _read_json(path)
    _keys(index, ('schema_version', 'catalog_version', 'categories'), label='catalog index')
    _version(index['schema_version'])
    _catalog_version(index['catalog_version'])
    _categories(index['categories'])
    entries = []
    for category in index['categories']:
        group = _read_json(path.parent / (category['id'] + '.json'))
        _keys(group, ('schema_version', 'category', 'styles'), label='category file')
        _version(group['schema_version'])
        if group['category'] != category['id'] or not isinstance(group['styles'], list):
            raise ValueError('category file does not match catalog index: ' + category['id'])
        if any(not isinstance(s, dict) or s.get('category') != category['id'] for s in group['styles']):
            raise ValueError('style category does not match its file: ' + category['id'])
        entries.extend(group['styles'])
    modifiers = _read_json(path.parent / 'modifiers.json')
    _keys(modifiers, ('schema_version', 'modifiers'), label='modifiers file')
    _version(modifiers['schema_version'])
    return validate_catalog({**index, 'styles': entries, 'modifiers': modifiers['modifiers']})


@lru_cache(maxsize=1)
def _installed_catalog():
    return load_catalog()


def _catalog(value=None):
    return validate_catalog(value) if value is not None else _installed_catalog()


def _find(entries, requested, kind):
    name = requested.strip().lower() if isinstance(requested, str) else ''
    for entry in entries:
        if name == entry['id'] or name in entry['aliases']:
            return entry
    names = [key for entry in entries for key in [entry['id'], *entry['aliases']]]
    close = difflib.get_close_matches(name, names, n=3)
    hint = ' Did you mean ' + ', '.join(close) + '?' if close else ''
    raise ValueError(f'unknown {kind} {requested!r}.{hint} Use hatch.py styles --search KEYWORD or hatch.py style-modifiers.')


def _search_text(text):
    return ' '.join(''.join(c for c in unicodedata.normalize('NFKD', text.casefold())
                           if not unicodedata.combining(c)).replace('-', ' ').split())


def _automatic(catalog, context, has_references, has_brand, avoided=()):
    text = _search_text(context)
    candidates = []
    for style in catalog['styles']:
        if style['kind'] == 'adaptive' or style['id'] in avoided:
            continue
        for spelling in (style['id'], style['name'], *style['aliases']):
            needle = _search_text(spelling)
            match = re.search(r'(?<!\w)' + re.escape(needle) + r'(?!\w)', text)
            if match and not re.search(r'\b(?:no|not|avoid|without)\b[^,;.]{0,48}$', text[max(0, match.start()-56):match.start()]):
                candidates.append((-len(needle), match.start(), style['id']))
    if candidates:
        chosen = min(candidates)[2]
        return _find(catalog['styles'], chosen, 'style'), {'method': 'auto-keyword', 'reason': 'Matched an explicit artistic term in the user concept or style notes.'}
    if has_references and 'auto' not in avoided:
        return _find(catalog['styles'], 'auto', 'style'), {'method': 'reference-guided', 'reason': 'Preserve the approved reference technique; the canonical base and visual review lock the exact rendering. No pixel analysis is claimed.'}
    if has_brand and 'brand-inspired' not in avoided:
        return _find(catalog['styles'], 'brand-inspired', 'style'), {'method': 'brand-guided', 'reason': 'Use attributed approved brand cues under explicit user constraints.'}
    fallbacks = [s for name in ('flat-vector', 'sticker', 'plush', 'pixel')
                 for s in catalog['styles'] if s['id'] == name and name not in avoided]
    if not fallbacks:
        fallbacks = [s for s in catalog['styles'] if s['kind'] == 'technique' and s['id'] not in avoided
                     and s['applicability']['character'] == 'recommended']
    if not fallbacks:
        raise ValueError('automatic style selection has no supported direction after explicit avoidances; choose an allowed --style-preset or revise --avoid')
    selected = fallbacks[0]
    return selected, {'method': 'auto-default', 'reason': 'No usable artistic cue or reference supplied; use the compact ' + selected['id'] + ' direction while respecting explicit style avoidances.'}


def _contract(style, modifiers, notes):
    lines = ['Preset guidance is subordinate to explicit user requirements and avoidances, the approved identity and references, and the selected profile contract. '
             'Apply the medium to the requested subject; do not add mascot anatomy to a non-character asset.',
             f"Style `{style['id']}` — {style['name']}: {style['description']}"]
    lines += [key.title() + ': ' + style['instructions'][key] for key in INSTRUCTION_FIELDS]
    lines += ['Avoid for this style: ' + '; '.join(style['negative_constraints']),
              'Keep the approved silhouette, proportions, palette, materials, surface markings, facial features and props stable across all states. '
              'Anchor texture to the same surfaces; do not re-randomize it per frame. Keep the entire subject inside each slot with clear gutters. '
              'Restrict fine detail at actual cell size. Keep external scenery, floor shadows, trails and detached decorative effects out of the sprite. '
              'Represent glow, reflections and texture within the body silhouette; do not draw a background or checkerboard.']
    for modifier in modifiers:
        lines += [f"Theme modifier `{modifier['id']}`: {modifier['instructions']}",
                  'Modifier avoidances: ' + '; '.join(modifier['negative_constraints'])]
    if modifiers:
        lines.append('Modifiers affect only approved character cues; they do not change the rendering technique, authorize new props, recolor required markings or override the profile.')
    if notes:
        lines.append('User style notes (take precedence over preset and modifier guidance): ' + notes)
    contract = '\n'.join(lines)
    if len(contract) > MAX_CONTRACT_CHARS:
        raise ValueError('resolved style prompt exceeds 16000 characters; shorten notes/modifiers')
    return contract


def resolve_style(style_id='auto', notes='', modifiers=(), context='', has_references=False, has_brand=False, catalog=None, avoidances=()):
    catalog = _catalog(catalog)
    if not isinstance(notes, str) or len(notes) > 4000 or _UNSAFE_TEXT.search(notes):
        raise ValueError('style notes must be safe text of at most 4000 characters')
    requested = _find(catalog['styles'], style_id, 'style')
    if not isinstance(avoidances, (list, tuple)) or any(not isinstance(v, str) for v in avoidances):
        raise ValueError('style avoidances must be a list or tuple of user constraint strings')
    avoided_terms = {_search_text(v) for v in avoidances}
    avoided = {s['id'] for s in catalog['styles'] if avoided_terms &
               {_search_text(n) for n in (s['id'], s['name'], *s['aliases'])}}
    if requested['id'] in avoided:
        raise ValueError('selected style ' + requested['id'] + ' conflicts with an explicit avoidance; choose another --style-preset or revise --avoid')
    selected, selection = (requested, {'method': 'explicit', 'reason': 'Selected by stable ID or its declared alias.'})
    if requested['id'] == 'auto':
        selected, selection = _automatic(catalog, notes + ' ' + context, has_references, has_brand, avoided)
    if isinstance(modifiers, str) or not isinstance(modifiers, (list, tuple)) or len(modifiers) > MAX_MODIFIERS:
        raise ValueError('select at most four separate --style-modifier values')
    resolved_modifiers = [_find(catalog['modifiers'], value, 'modifier') for value in modifiers]
    ids = [m['id'] for m in resolved_modifiers]
    if len(ids) != len(set(ids)):
        raise ValueError('duplicate modifier selection (including aliases)')
    for modifier in resolved_modifiers:
        conflicts = set(modifier['conflicts']) & set(ids)
        if conflicts:
            raise ValueError('conflicting modifiers: ' + modifier['id'] + ' and ' + ', '.join(sorted(conflicts)))
    snapshot = {'schema_version': SCHEMA_VERSION, 'catalog_version': catalog['catalog_version'],
                'catalog_sha256': digest(catalog), 'requested_id': style_id.strip().lower(),
                'resolved_id': selected['id'], 'selection': selection, 'style': copy.deepcopy(selected),
                'modifiers': copy.deepcopy(resolved_modifiers), 'style_notes': notes.strip(),
                'contract': _contract(selected, resolved_modifiers, notes.strip())}
    snapshot['sha256'] = digest(snapshot)
    return snapshot


def validate_snapshot(value):
    """Validate recorded data without consulting the currently installed catalog."""
    _keys(value, ('schema_version', 'catalog_version', 'catalog_sha256', 'requested_id', 'resolved_id',
                  'selection', 'style', 'modifiers', 'style_notes', 'contract', 'sha256'), label='resolved style')
    _version(value['schema_version'], 'resolved style schema_version')
    _catalog_version(value['catalog_version'])
    _slug(value['requested_id'], 'requested style ID')
    _slug(value['resolved_id'], 'resolved style ID')
    validate_style(value['style'])
    _names([value['style']], 'saved style')
    if value['resolved_id'] != value['style']['id']:
        raise ValueError('resolved style ID differs from saved specification')
    _keys(value['selection'], ('method', 'reason'), label='style selection')
    _enum(value['selection']['method'], ('explicit', 'auto-keyword', 'reference-guided', 'brand-guided', 'auto-default'), 'selection.method')
    _text(value['selection']['reason'], 'selection.reason')
    if not isinstance(value['modifiers'], list) or len(value['modifiers']) > MAX_MODIFIERS:
        raise ValueError('resolved style needs at most four modifiers')
    for modifier in value['modifiers']:
        validate_modifier(modifier)
    _names(value['modifiers'], 'selected modifier')
    selected = {m['id'] for m in value['modifiers']}
    if any(selected & set(m['conflicts']) for m in value['modifiers']):
        raise ValueError('resolved style has conflicting modifiers')
    notes = value['style_notes']
    if not isinstance(notes, str) or len(notes) > 4000 or _UNSAFE_TEXT.search(notes):
        raise ValueError('invalid resolved style notes')
    _text(value['contract'], 'resolved style contract', maximum=MAX_CONTRACT_CHARS)
    for key in ('catalog_sha256', 'sha256'):
        if not isinstance(value[key], str) or not re.fullmatch(r'[0-9a-f]{64}', value[key]):
            raise ValueError('invalid resolved style ' + key)
    if value['sha256'] != digest({k: v for k, v in value.items() if k != 'sha256'}):
        raise ValueError('resolved style snapshot hash mismatch')
    required_text = [*value['style']['instructions'].values(), *value['style']['negative_constraints']]
    required_text += [m['instructions'] for m in value['modifiers']]
    required_text += [n for m in value['modifiers'] for n in m['negative_constraints']]
    if any(text not in value['contract'] for text in required_text) or notes not in value['contract']:
        raise ValueError('resolved style contract omits saved instructions or notes')
    return copy.deepcopy(value)


def compatibility_warnings(snapshot, profile, background='auto', resampling=None):
    """Advisory risks only; no geometry/palette/review settings are changed."""
    if snapshot is None:
        return []
    validate_snapshot(snapshot)
    style, warnings = snapshot['style'], []
    c = style['compatibility']
    name = style['id']
    if background == 'chroma' and c['chroma'] != 'supported':
        warnings.append(f"{name}: chroma is {c['chroma']}. Use --background alpha for soft/translucent edges; inspect the original alpha and key collisions before rows. " + ' '.join(c['notes']))
    fallback = resampling or c['resampling']
    different = [s['id'] for s in profile['states'] if s['alignment'].get('resampling', fallback) != c['resampling']]
    if different:
        warnings.append(f"{name}: profile/extraction resampling differs from recommended {c['resampling']} for {', '.join(different)}. "
                        'Explicit per-state alignment.resampling wins; revise the profile deliberately and inspect edges at actual size. ' + c['scaling'])
    dimensions = min(profile['layout']['cell_width'], profile['layout']['cell_height'])
    if dimensions < 64:
        warnings.append(f'{name}: cells below 64 pixels require fewer, broader marks. Inspect facial features, line spacing and material recognition at actual size.')
    formats = set(profile['export']['formats'])
    if 'gif' in formats and c['edge_mode'] == 'antialiased':
        warnings.append(f'{name}: GIF has binary transparency and a limited palette. Inspect fringes; use PNG, WebP or browser output for soft alpha edges.')
    kinds = ['character' if profile['schema_version'] == 1 else 'sequence']
    if 'craft' in formats:
        kinds.append('grid')
    if 'cursor' in formats:
        kinds.append('icon')
    if formats & {'cards', 'flipbook', 'board'}:
        kinds.append('print')
    for kind in kinds:
        suitability = style['applicability'][kind]
        if suitability != 'recommended':
            warnings.append(f'{name}: {kind} use is {suitability}; ' + ' '.join(style['limitations']) + ' Respect the selected profile and review the adaptation before generation.')
    if 'craft' in formats and c['resampling'] != 'nearest':
        warnings.append(f'{name}: craft export quantizes to a fixed grid/palette; gradients and material texture may be lost. Choose a grid-native technique or review a deliberate simplified adaptation.')
    return list(dict.fromkeys(warnings))


def preset_mapping():
    return {s['id']: '\n'.join(s['instructions'][k] for k in INSTRUCTION_FIELDS) for s in _installed_catalog()['styles']}


def discover(command='styles', search='', category=None, style_id=None, profile=None, background='auto'):
    catalog = _installed_catalog()
    result = {'catalog_version': catalog['catalog_version'], 'catalog_sha256': digest(catalog)}
    if command == 'style-modifiers':
        result['modifiers'] = copy.deepcopy(catalog['modifiers'])
        return result
    if command == 'style':
        if not style_id:
            raise ValueError('style requires --style-preset ID')
        style = _find(catalog['styles'], style_id, 'style')
        result['style'] = copy.deepcopy(style)
        # Inspection describes the requested record. In particular, inspect auto's
        # reference-guided metadata instead of silently previewing flat-vector.
        preview = resolve_style(style_id, has_references=style['id'] == 'auto') if profile else None
        result['warnings'] = compatibility_warnings(preview, profile, background) if profile else []
        return result
    categories = {c['id']: c for c in catalog['categories']}
    if category is not None and category not in categories:
        raise ValueError('unknown style category; choose ' + ', '.join(categories))
    terms = _search_text(search).split()
    styles = [s for s in catalog['styles'] if (category is None or s['category'] == category)
              and all(term in _search_text(' '.join([s['id'], s['name'], s['category'], categories[s['category']]['name'],
                                                    s['description'], *s['tags'], *s['aliases']])) for term in terms)]
    result['counts'] = {'selectable': len(catalog['styles']), **{plural: sum(s['kind'] == kind for s in catalog['styles'])
        for kind, plural in (('technique', 'techniques'), ('treatment', 'treatments'), ('adaptive', 'adaptive'))}}
    result['categories'] = [{**c, 'count': sum(s['category'] == c['id'] for s in catalog['styles']),
                              'technique_count': sum(s['category'] == c['id'] and s['kind'] == 'technique' for s in catalog['styles'])}
                             for c in catalog['categories']]
    result.update(matched=len(styles), styles=copy.deepcopy(styles))
    return result


def format_discovery(command, value):
    if command == 'style':
        s = value['style']
        lines = [f"{s['id']} — {s['name']} ({s['category']}, {s['kind']})", s['description'],
                 'Aliases: ' + (', '.join(s['aliases']) or 'none'), 'Tags: ' + ', '.join(s['tags']), '']
        lines += [key.title() + ': ' + s['instructions'][key] for key in INSTRUCTION_FIELDS]
        for key in ('negative_constraints', 'use_cases', 'limitations'):
            lines += ['', key.replace('_', ' ').title() + ':', *['  - ' + x for x in s[key]]]
        lines += ['', 'Applicability: ' + ', '.join(k + '=' + v for k, v in s['applicability'].items()),
                  'Compatibility: ' + json.dumps(s['compatibility'], ensure_ascii=False),
                  'Suggested modifiers: ' + (', '.join(s.get('recommended_modifiers', [])) or 'any compatible thematic modifier')]
        lines += ['Warning: ' + w for w in value.get('warnings', [])]
        return '\n'.join(lines)
    if command == 'style-modifiers':
        return '\n'.join(['Thematic modifiers (separate from styles; repeat --style-modifier, maximum four):',
                          *[f"{m['id']:<16} {m['description']}" for m in value['modifiers']]])
    counts = value['counts']
    lines = [f"Style catalog {value['catalog_version']}: {counts['selectable']} selectable entries; "
             f"{counts['techniques']} techniques, {counts['treatments']} treatments, {counts['adaptive']} adaptive selectors.",
             f"Showing {value['matched']} matches. Use hatch.py style --style-preset ID for details, or --json for full metadata."]
    for category in value['categories']:
        selected = [s for s in value['styles'] if s['category'] == category['id']]
        if selected:
            lines += ['', category['name'] + ' [' + category['id'] + ']']
            lines += [f"  {s['id']:<32} {s['description']}" for s in selected]
    return '\n'.join(lines)


def catalog_schema():
    """Structural schema; runtime additionally checks uniqueness, references and hashes."""
    def obj(properties, required=None):
        return {'type': 'object', 'additionalProperties': False, 'properties': properties,
                'required': list(properties if required is None else required)}

    def text(minimum=1, maximum=1000):
        return {'type': 'string', 'minLength': minimum, 'maxLength': maximum,
                'pattern': r'^[^\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f\u202a-\u202e\u2066-\u2069]*$'}

    slug = {'type': 'string', 'maxLength': 64, 'pattern': '^[a-z0-9]+(?:-[a-z0-9]+)*$'}
    version = {'type': 'integer', 'const': 1}
    catalog_version = {'type': 'string', 'maxLength': 32, 'pattern': r'^[0-9]+\.[0-9]+\.[0-9]+$'}
    sha = {'type': 'string', 'pattern': '^[0-9a-f]{64}$'}

    def strings(minimum=0, slugs=False):
        return {'type': 'array', 'minItems': minimum, 'maxItems': 32, 'uniqueItems': True,
                'items': slug if slugs else text()}

    category = obj({'id': slug, 'name': text(maximum=120)})
    categories = {'type': 'array', 'minItems': 1, 'maxItems': 128, 'items': category}
    compatibility = obj({'alpha': {'enum': ['supported', 'preferred', 'required']},
                         'chroma': {'enum': ['supported', 'caution', 'unsupported']},
                         'edge_mode': {'enum': ['hard', 'antialiased']},
                         'resampling': {'enum': list(RESAMPLING)}, 'scaling': text(20), 'notes': strings(1)})
    compatibility['allOf'] = [
        {'if': {'properties': {'alpha': {'const': 'required'}}}, 'then': {'properties': {'chroma': {'const': 'unsupported'}}}},
        {'if': {'properties': {'chroma': {'const': 'unsupported'}}}, 'then': {'properties': {'alpha': {'const': 'required'}}}},
        {'if': {'properties': {'edge_mode': {'const': 'hard'}}}, 'then': {'properties': {'resampling': {'const': 'nearest'}}}}]
    style = obj({'id': slug, 'name': text(maximum=120), 'category': slug,
                 'kind': {'enum': ['technique', 'treatment', 'adaptive']}, 'description': text(20),
                 'tags': strings(2), 'aliases': strings(slugs=True),
                 'instructions': obj({k: text(20, 800) for k in INSTRUCTION_FIELDS}),
                 'negative_constraints': strings(2), 'use_cases': strings(1), 'limitations': strings(1),
                 'applicability': obj({k: {'enum': ['recommended', 'adapted', 'unsuitable']} for k in APPLICABILITY}),
                 'compatibility': compatibility, 'recommended_modifiers': strings(slugs=True)})
    style['required'].remove('recommended_modifiers')
    modifier = obj({'id': slug, 'name': text(maximum=120), 'description': text(20),
                    'instructions': text(20, 800), 'negative_constraints': strings(1),
                    'aliases': strings(slugs=True), 'conflicts': strings(slugs=True)})
    styles = {'type': 'array', 'minItems': 1, 'maxItems': MAX_STYLES, 'items': {'$ref': '#/$defs/style'}}
    modifiers = {'type': 'array', 'maxItems': 128, 'items': {'$ref': '#/$defs/modifier'}}
    index = obj({'schema_version': version, 'catalog_version': catalog_version, 'categories': categories})
    combined = obj({**index['properties'], 'styles': styles, 'modifiers': modifiers})
    group = obj({'schema_version': version, 'category': slug, 'styles': styles})
    modifier_file = obj({'schema_version': version, 'modifiers': modifiers})
    snapshot = obj({'schema_version': version, 'catalog_version': catalog_version, 'catalog_sha256': sha,
                    'requested_id': slug, 'resolved_id': slug,
                    'selection': obj({'method': {'enum': ['explicit', 'auto-keyword', 'reference-guided', 'brand-guided', 'auto-default']}, 'reason': text()}),
                    'style': {'$ref': '#/$defs/style'}, 'modifiers': {**modifiers, 'maxItems': MAX_MODIFIERS},
                    'style_notes': text(0, 4000), 'contract': text(1, MAX_CONTRACT_CHARS), 'sha256': sha})
    return {'$schema': 'https://json-schema.org/draft/2020-12/schema',
            'title': 'Hatch visual style catalog and frozen specification v1',
            'description': 'Structural validation. style_registry also validates ID/alias uniqueness, category and modifier references, contradictory restrictions, instruction completeness and snapshot hashes.',
            '$defs': {'style': style, 'modifier': modifier, 'index': index, 'catalog': combined,
                      'category': group, 'modifier_file': modifier_file, 'resolved_style': snapshot},
            'oneOf': [{'$ref': '#/$defs/' + name} for name in ('index', 'catalog', 'category', 'modifier_file', 'resolved_style')]}

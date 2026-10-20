#!/usr/bin/env python3
"""Discover character definitions and compile bounded, ordinary Hatch Pet profiles.

Catalog metadata is an authoring contract, never an alternate runtime schema or
evidence of finished artwork. Every compilation passes profile_spec.load_profile
and the existing asset resource limits before any file is written.
"""
from __future__ import annotations

import argparse
import copy
import json
import sys
import re
from pathlib import Path

from asset_contracts import MAX_SOURCE_PIXELS, check_resources, hash_object, sha, strict_keys
from profile_spec import RESERVED_STATES, indexed_frames, load_profile, profile_hash

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LIBRARY = ROOT / 'state-library'
DEFAULT_STATE_LIMIT = 32
LIBRARY_FILES = ('catalog.json', 'packs.json', 'archetypes.json', 'recipes.json', 'animation-recipes.json')
SLUG = re.compile(r'[a-z0-9][a-z0-9-]*\Z')
HASH = re.compile(r'[0-9a-f]{64}\Z')

IDENTITY_REQUIREMENTS = [
    'Use the installed imagegen workflow for every production model call; attach the approved canonical identity, required original references, and the claimed layout guide.',
    'Preserve the approved silhouette, proportions, facial structure, markings, palette, texture, materials, lighting, artistic style, clothing, accessories, and character scale in every frame.',
    'Animate only anatomy visible in the approved character. Never invent hands, legs, wings, tails, eyes, mouths, or other unsupported anatomy.',
    'Keep one shared viewport and character scale across all selected states; preserve intentional body displacement within the slot without per-frame fitting.',
    'Use only explicitly approved props already reconciled with the canonical character identity. No floating text, symbols, unapproved props, shadows, scenery, trails, backgrounds, or detached decorations.',
    'Keep environmental effects separate from the character artwork; represent environmental reactions through the character pose only.',
    'Do not mirror an asymmetric character or reverse markings, accessories, handedness, or directional identity. Generate directional states independently.',
    'Use distinct, intentional key poses and intervening action changes; never duplicate frames merely to meet the requested count.',
    'Generation definitions and synthetic fixtures are not reviewed production artwork. Retain source provenance and require the existing deterministic and visual-review gates.',
]

STATE_KEYS = {
    'id', 'name', 'category', 'family', 'tags', 'aliases', 'description', 'archetypes',
    'anatomy', 'animation', 'animation_recipe', 'poses', 'expression', 'direction',
    'events', 'priority', 'interrupt', 'repeat', 'legal_transitions', 'completion',
    'recovery', 'reduced_motion', 'props', 'negative_constraints', 'semantic_review',
    'compatibility', 'examples',
}
SELECTION_KEYS = {
    'schema_version', 'profile_id', 'states', 'packs', 'recipe', 'archetype',
    'capabilities', 'approved_props', 'anatomy_policy', 'layout', 'max_states',
    'allow_large', 'limit', 'queue_limit', 'animation_recipes', 'reduced_motion',
}
MANIFEST_KEYS = {
    'schema_version', 'kind', 'catalog_version', 'catalog_sha256', 'profile_sha256',
    'manifest_sha256', 'selected_states', 'selection', 'required_props',
    'state_requirements', 'selection_reasons', 'substitutions', 'omitted',
    'adaptations', 'estimates', 'source_files', 'artwork_status', 'production_review',
}


def _require(condition, message):
    if not condition:
        raise ValueError('invalid state library: ' + message)


def _text(value, context):
    _require(isinstance(value, str) and bool(value.strip()), context + ' must be nonempty text')
    return value


def _slug(value, context):
    _require(isinstance(value, str) and bool(SLUG.fullmatch(value)) and value not in RESERVED_STATES,
             context + ' must be a portable lowercase identifier')
    return value


def _integer(value, lower, upper, context):
    _require(type(value) is int and lower <= value <= upper, f'{context} must be {lower}..{upper}')
    return value


def _strings(value, context, *, nonempty=False, slugs=False, unique=True):
    _require(isinstance(value, list) and (bool(value) or not nonempty), context + ' must be a list')
    for item in value:
        (_slug if slugs else _text)(item, context)
    _require(not unique or len(set(value)) == len(value), context + ' contains duplicates')
    return value


def _keys(value, allowed, context, required=()):
    strict_keys(value, allowed, context)
    _require(not set(required) - set(value), context + ' is missing: ' + ', '.join(sorted(set(required) - set(value))))


def _read_json(path):
    path = Path(path)
    # Catalog extensions are local data files, never executable plugin modules.
    _require(path.is_file() and path.stat().st_size <= 16 * 1024 * 1024,
             str(path) + ' must be a JSON file no larger than 16 MiB')
    def unique_pairs(pairs):
        result = {}
        for key, value in pairs:
            _require(key not in result, 'duplicate JSON object key: ' + key)
            result[key] = value
        return result
    return json.loads(path.read_text(encoding='utf-8'), object_pairs_hook=unique_pairs,
                      parse_constant=lambda value: (_ for _ in ()).throw(ValueError('nonfinite JSON number: ' + value)))


def _root(value, key, extras=()):
    _keys(value, {'schema_version', key, *extras}, key + ' file', {'schema_version', key})
    _require(type(value['schema_version']) is int and value['schema_version'] == 1,
             key + ' schema_version must be 1')
    _require(isinstance(value[key], list), key + ' must be a list')


def _records(records, context):
    result = {}
    for record in records:
        _require(isinstance(record, dict), context + ' record must be an object')
        name = _slug(record.get('id'), context + '.id')
        _require(name not in result, context + ' contains duplicate id: ' + name)
        result[name] = copy.deepcopy(record)
    return result


def _no_cycles(graph, context):
    active, done = set(), set()
    def visit(node):
        _require(node not in active, context + ' cycle involving ' + node)
        if node in done:
            return
        active.add(node)
        for target in graph.get(node, []):
            visit(target)
        active.remove(node)
        done.add(node)
    for node in graph:
        visit(node)


def _reachable(graph, start):
    visited, todo = set(), [start]
    while todo:
        node = todo.pop()
        if node not in visited:
            visited.add(node)
            todo.extend(set(graph.get(node, ())) - visited)
    return visited


class StateLibrary:
    """Validated immutable-by-convention authoring data and deterministic queries."""

    def __init__(self, catalog, packs, archetypes, recipes, animation_recipes, *, source_files=()):
        _root(catalog, 'states', {'catalog_version', 'categories'})
        _require(isinstance(catalog.get('catalog_version'), str) and
                 re.fullmatch(r'\d+\.\d+\.\d+', catalog['catalog_version']), 'catalog_version must be semantic x.y.z')
        _require(isinstance(catalog.get('categories'), list) and catalog['categories'], 'categories must be nonempty')
        _require(bool(catalog['states']), 'catalog states must be nonempty')
        _root(packs, 'packs')
        _root(archetypes, 'archetypes', {'capabilities'})
        _root(recipes, 'recipes')
        _root(animation_recipes, 'recipes')
        _require(isinstance(archetypes.get('capabilities'), list), 'archetype capabilities must be a list')
        self.version = catalog['catalog_version']
        self.categories = _records(catalog['categories'], 'category')
        self.states = _records(catalog['states'], 'state')
        self.packs = _records(packs['packs'], 'pack')
        self.capabilities = _records(archetypes['capabilities'], 'capability')
        self.archetypes = _records(archetypes['archetypes'], 'archetype')
        self.recipes = _records(recipes['recipes'], 'transition recipe')
        self.animation_recipes = _records(animation_recipes['recipes'], 'animation recipe')
        self.source_files = copy.deepcopy(list(source_files))
        self.aliases = {}
        self._validate_named_records()
        self._validate_animation_recipes()
        self._validate_states()
        self._validate_references()
        self._validate_packs()
        self._validate_recipes()
        self.sha256 = hash_object({'catalog_version': self.version, 'categories': self.categories,
                                  'states': self.states, 'packs': self.packs,
                                  'capabilities': self.capabilities, 'archetypes': self.archetypes,
                                  'recipes': self.recipes, 'animation_recipes': self.animation_recipes})

    def _validate_named_records(self):
        for kind, records in (('category', self.categories), ('capability', self.capabilities)):
            for record in records.values():
                _keys(record, {'id', 'name', 'description'}, kind, {'id', 'name', 'description'})
                _text(record['name'], kind + '.name'); _text(record['description'], kind + '.description')
        for record in self.archetypes.values():
            _keys(record, {'id', 'name', 'description', 'capabilities'}, 'archetype',
                  {'id', 'name', 'description', 'capabilities'})
            _text(record['name'], 'archetype.name'); _text(record['description'], 'archetype.description')
            _strings(record['capabilities'], 'archetype.capabilities', slugs=True)
            _require(not set(record['capabilities']) - set(self.capabilities), 'archetype names unknown capabilities')
        _require('generic' in self.archetypes, 'a conservative generic archetype is required')

    def _validate_animation_recipes(self):
        for record in self.animation_recipes.values():
            _keys(record, {'id', 'name', 'description', 'frames', 'durations', 'key_phases', 'loop_seam'},
                  'animation recipe', {'id', 'name', 'description', 'frames', 'durations', 'key_phases', 'loop_seam'})
            for field in ('name', 'description', 'loop_seam'):
                _text(record[field], 'animation recipe.' + field)
            _integer(record['frames'], 1, 64, 'animation recipe.frames')
            _require(isinstance(record['durations'], list) and len(record['durations']) == record['frames'],
                     'animation recipe needs one duration per frame')
            for duration in record['durations']:
                _integer(duration, 10, 60000, 'animation recipe duration')
            _strings(record['key_phases'], 'animation recipe.key_phases', nonempty=True, unique=False)

    def _validate_states(self):
        for name, state in self.states.items():
            _keys(state, STATE_KEYS, name, STATE_KEYS)
            for field in ('name', 'description', 'expression'):
                _text(state[field], name + '.' + field)
            _slug(state['family'], name + '.family')
            _slug(state['category'], name + '.category')
            _require(state['category'] in self.categories, name + ': unknown category')
            for field in ('tags', 'aliases', 'archetypes', 'legal_transitions'):
                _strings(state[field], name + '.' + field, nonempty=field in {'tags', 'archetypes'}, slugs=True)
            _require(set(state['archetypes']) <= set(self.archetypes) | {'any'}, name + ': unknown archetype')
            _require('any' not in state['archetypes'] or state['archetypes'] == ['any'],
                     name + ': any archetype cannot be mixed with specific archetypes')
            for alias in state['aliases']:
                _require(alias not in self.states and alias not in self.aliases, 'conflicting alias: ' + alias)
                self.aliases[alias] = name
            anatomy = state['anatomy']
            _keys(anatomy, {'requires_all', 'requires_any', 'excludes', 'fallback'}, name + '.anatomy',
                  {'requires_all', 'requires_any', 'excludes', 'fallback'})
            for field in ('requires_all', 'requires_any', 'excludes'):
                _strings(anatomy[field], name + '.anatomy.' + field, slugs=True)
                _require(set(anatomy[field]) <= set(self.capabilities), name + ': unknown anatomy capability')
            _require(not set(anatomy['requires_all']) & set(anatomy['excludes']), name + ': impossible anatomy requirements')
            _require(not anatomy['requires_any'] or bool(set(anatomy['requires_any']) - set(anatomy['excludes'])),
                     name + ': all alternative anatomy capabilities are excluded')
            _slug(anatomy['fallback'], name + '.anatomy.fallback')
            _strings(state['poses'], name + '.poses', nonempty=True, unique=False)
            for field in ('negative_constraints', 'semantic_review', 'examples'):
                _strings(state[field], name + '.' + field, nonempty=True)
            direction = state['direction']
            _keys(direction, {'facing', 'travel', 'mirror_policy', 'dependencies'}, name + '.direction',
                  {'facing', 'travel', 'mirror_policy', 'dependencies'})
            _require(direction['facing'] in ('front', 'left', 'right', 'back', 'any'), name + ': unsupported facing')
            _require(direction['travel'] in ('none', 'left', 'right', 'up', 'down', 'forward', 'backward'),
                     name + ': unsupported travel direction')
            _require(direction['mirror_policy'] == 'explicit-approval-only', name + ': unsafe mirror policy')
            _strings(direction['dependencies'], name + '.direction.dependencies', slugs=True)
            _strings(state['events'], name + '.events', nonempty=True)
            _require(all(len(event) <= 128 and not any(c in event for c in '\n\r\0') for event in state['events']),
                     name + ': invalid event name')
            _integer(state['priority'], 0, 100, name + '.priority')
            _require(state['interrupt'] in ('always', 'higher', 'never'), name + ': unsupported interruption policy')
            _require(state['repeat'] in ('coalesce', 'restart'), name + ': unsupported repeat policy')
            _require(state['completion'] is None or isinstance(state['completion'], str), name + ': invalid completion')
            if state['completion'] is not None:
                _slug(state['completion'], name + '.completion')
            _slug(state['recovery'], name + '.recovery')
            reduced = state['reduced_motion']
            _keys(reduced, {'mode', 'frame', 'description'}, name + '.reduced_motion', {'mode', 'frame', 'description'})
            _require(reduced['mode'] == 'static', name + ': reduced motion must provide a static alternative')
            _text(reduced['description'], name + '.reduced_motion.description')
            _keys(state['props'], {'required', 'optional'}, name + '.props', {'required', 'optional'})
            for field in ('required', 'optional'):
                _strings(state['props'][field], name + '.props.' + field)
            _require(not set(state['props']['required']) & set(state['props']['optional']), name + ': prop cannot be required and optional')
            _keys(state['compatibility'], {'codex', 'custom_profile'}, name + '.compatibility', {'codex', 'custom_profile'})
            _require(all(type(value) is bool for value in state['compatibility'].values()) and
                     state['compatibility'] == {'codex': False, 'custom_profile': True},
                     name + ': catalog definitions target custom profiles, never the fixed Codex consumer')
            animation = state['animation']
            _require(isinstance(animation, dict) and animation.get('id') == name, name + ': animation id must match canonical id')
            _require(animation.get('allowed_derivations', []) == [], name + ': catalog states must be generated independently; no inferred mirroring')
            _require(isinstance(animation.get('generation'), dict) and animation['generation'].get('instructions'),
                     name + ': generation instructions are required')
            _require(animation['generation'].get('requirements'), name + ': generation requirements are required')
            _require(isinstance(animation.get('playback'), dict), name + ': playback rule is required')
            _require('completion' not in animation['playback'], name + ': completion belongs in catalog metadata')
            _slug(state['animation_recipe'], name + '.animation_recipe')
            _require(state['animation_recipe'] in self.animation_recipes, name + ': unknown animation recipe')
            probe = load_profile({'schema_version': 2, 'id': 'catalog-probe',
                                  'layout': {'columns': animation.get('frames', 1), 'cell_width': 192, 'cell_height': 208},
                                  'states': [animation]})
            state['animation'] = probe['states'][0]
            _integer(reduced['frame'], 0, animation['frames'] - 1, name + '.reduced_motion.frame')
            _require(state['completion'] is None or animation['playback'].get('mode', 'loop') == 'once',
                     name + ': completion requires a once animation')
            _require(animation['playback'].get('interruptible', True) or animation['playback'].get('mode') == 'once',
                     name + ': noninterruptible states must finish to allow recovery')

    def _validate_references(self):
        _require('idle' in self.states, 'catalog requires the neutral idle recovery state')
        edges, fallbacks, completions = {}, {}, {}
        events = {}
        for name, state in self.states.items():
            references = state['legal_transitions'] + state['direction']['dependencies'] + [state['recovery'], state['anatomy']['fallback']]
            if state['completion']:
                references.append(state['completion'])
                _require(state['completion'] != name, name + ': completion cannot target itself')
                _require(state['completion'] in state['legal_transitions'], name + ': completion must be a legal transition')
            _require(set(references) <= set(self.states), name + ': missing state dependency/transition: ' + ', '.join(sorted(set(references) - set(self.states))))
            _require(state['recovery'] == name or state['recovery'] in state['legal_transitions'],
                     name + ': recovery must be a legal transition')
            edges[name] = state['direction']['dependencies']
            fallbacks[name] = [] if state['anatomy']['fallback'] == name else [state['anatomy']['fallback']]
            completions[name] = [state['completion']] if state['completion'] else []
            for event in state['events']:
                _require(event not in events or events[event] == name, 'conflicting catalog event: ' + event)
                events[event] = name
        _no_cycles(edges, 'direction dependency')
        _no_cycles(fallbacks, 'anatomy fallback')
        _no_cycles(completions, 'completion')
        legal_graph = {name: set(state['legal_transitions']) | set(completions[name]) for name, state in self.states.items()}
        _require(set(self.states) <= _reachable(legal_graph, 'idle'), 'catalog contains inaccessible states; declare explicit legal entry transitions')
        reverse = {name: set() for name in self.states}
        for source, targets in legal_graph.items():
            for target in targets: reverse[target].add(source)
        _require(set(self.states) <= _reachable(reverse, 'idle'), 'catalog contains an inaccessible idle recovery path')

    def _validate_packs(self):
        for name, pack in self.packs.items():
            _keys(pack, {'id', 'name', 'description', 'states', 'includes', 'exclude', 'archetypes', 'recommended_limit', 'selection_only'},
                  name + ' pack', {'id', 'name', 'description', 'states', 'includes', 'exclude', 'selection_only'})
            for field in ('name', 'description'):
                _text(pack[field], name + '.' + field)
            for field in ('states', 'includes', 'exclude'):
                _strings(pack[field], name + '.' + field, slugs=True)
            _require(set(pack['includes']) <= set(self.packs), name + ': missing included pack')
            for value in pack['states'] + pack['exclude']:
                self.resolve(value)
            _require(type(pack['selection_only']) is bool, name + ': selection_only must be boolean')
            pack.setdefault('archetypes', [])
            _strings(pack['archetypes'], name + '.archetypes', slugs=True)
            _require(set(pack['archetypes']) <= set(self.archetypes), name + ': unknown recommended archetype')
            pack.setdefault('recommended_limit', DEFAULT_STATE_LIMIT)
            _integer(pack['recommended_limit'], 1, 256, name + '.recommended_limit')
        _no_cycles({name: pack['includes'] for name, pack in self.packs.items()}, 'pack inclusion')
        for name in self.packs:
            _require(bool(self.expand_pack(name)), name + ': pack resolves to no states')

    def _validate_recipes(self):
        for name, recipe in self.recipes.items():
            _keys(recipe, {'id', 'name', 'description', 'states', 'initial', 'cancel_state', 'steps', 'completion', 'events', 'queue_limit'},
                  name + ' recipe', {'id', 'name', 'description', 'states', 'initial', 'cancel_state', 'steps', 'completion', 'events', 'queue_limit'})
            for field in ('name', 'description'):
                _text(recipe[field], name + '.' + field)
            _strings(recipe['states'], name + '.states', nonempty=True, slugs=True)
            _require(isinstance(recipe['steps'], list) and len(recipe['steps']) >= 2,
                     name + ': steps must describe at least one transition')
            _require(all(isinstance(x, str) and x in recipe['states'] for x in recipe['steps']), name + ': steps reference undeclared states')
            _require(set(recipe['states']) <= set(self.states), name + ': missing recipe state')
            _require(recipe['initial'] in recipe['states'] and recipe['cancel_state'] in recipe['states'],
                     name + ': initial/cancel_state must be selected')
            _require(recipe['steps'][0] == recipe['initial'], name + ': first step must be initial state')
            _integer(recipe['queue_limit'], 0, 32, name + '.queue_limit')
            _require(isinstance(recipe['completion'], dict), name + ': completion must be an object')
            for source, target in recipe['completion'].items():
                _require(source in recipe['states'] and target in recipe['states'] and source != target,
                         name + ': invalid completion target')
            _no_cycles({source: [target] for source, target in recipe['completion'].items()}, name + ' completion')
            _require(isinstance(recipe['events'], dict) and recipe['events'], name + ': event rules must be nonempty')
            for event, rule in recipe['events'].items():
                _text(event, name + ' event')
                _keys(rule, {'target', 'from', 'priority', 'interrupt', 'restart', 'resume'}, name + ' event ' + event, {'target'})
                _require(rule['target'] in recipe['states'], name + ': event target missing from recipe')
                if 'from' in rule:
                    _strings(rule['from'], name + ' event.from', nonempty=True, slugs=True)
                    _require(set(rule['from']) <= set(recipe['states']), name + ': missing legal source state')
                _integer(rule.get('priority', 0), 0, 100, name + ' event.priority')
                _require(rule.get('interrupt', 'always') in ('always', 'higher', 'never'), name + ': invalid interrupt')
                for flag in ('restart', 'resume'):
                    _require(type(rule.get(flag, False)) is bool, name + ': ' + flag + ' must be boolean')
                if rule.get('resume'):
                    target = rule['target']
                    effective_mode = 'once' if target in recipe['completion'] else self.states[target]['animation']['playback'].get('mode', 'loop')
                    _require(effective_mode == 'once', name + ': event resume requires a once target: ' + event)
            # Every illustrated step needs a real completion edge or legal event.
            for source, target in zip(recipe['steps'], recipe['steps'][1:]):
                legal = recipe['completion'].get(source) == target or any(
                    rule['target'] == target and ('from' not in rule or source in rule['from'])
                    for rule in recipe['events'].values())
                _require(legal, f'{name}: step {source} -> {target} has no implemented transition')
            adjacency = {state: set() for state in recipe['states']}
            for source, target in recipe['completion'].items():
                adjacency[source].add(target)
            for rule in recipe['events'].values():
                for source in rule.get('from', recipe['states']):
                    adjacency[source].add(rule['target'])
            visited = _reachable(adjacency, recipe['initial'])
            _require(set(recipe['states']) <= visited | {recipe['cancel_state']}, name + ': recipe contains unreachable states')
            reverse = {state: set() for state in recipe['states']}
            for source, targets in adjacency.items():
                for target in targets: reverse[target].add(source)
            _require(set(recipe['states']) <= _reachable(reverse, recipe['cancel_state']),
                     name + ': recipe has an inaccessible recovery path')

    def resolve(self, state):
        _text(state, 'state selector')
        if state in self.states:
            return state
        _require(state in self.aliases, 'unknown state or alias: ' + state)
        return self.aliases[state]

    def expand_pack(self, name):
        _text(name, 'pack selector')
        _require(name in self.packs, 'unknown pack: ' + str(name))
        pack = self.packs[name]
        result = []
        for included in pack['includes']:
            result.extend(self.expand_pack(included))
        result.extend(self.resolve(value) for value in pack['states'])
        excluded = {self.resolve(value) for value in pack['exclude']}
        return list(dict.fromkeys(value for value in result if value not in excluded))

    def character_capabilities(self, archetype='generic', capabilities=None):
        _text(archetype, 'archetype selector')
        _require(archetype in self.archetypes, 'unknown archetype: ' + str(archetype))
        if capabilities is not None:
            _strings(capabilities, 'character capabilities', slugs=True)
        result = list(self.archetypes[archetype]['capabilities'] if capabilities is None else capabilities)
        _strings(result, 'character capabilities', slugs=True)
        _require(set(result) <= set(self.capabilities), 'unknown capabilities: ' + ', '.join(sorted(set(result) - set(self.capabilities))))
        return sorted(result)

    def summary(self):
        return {'catalog_version': self.version, 'catalog_sha256': self.sha256,
                'states': len(self.states), 'aliases': len(self.aliases),
                'categories': len(self.categories), 'packs': len(self.packs),
                'archetypes': len(self.archetypes), 'capabilities': len(self.capabilities),
                'transition_recipes': len(self.recipes), 'animation_recipes': len(self.animation_recipes),
                'category_counts': {name: sum(state['category'] == name for state in self.states.values())
                                    for name in self.categories},
                'artwork_status': 'definitions-only'}

    def incompatibilities(self, name, archetype='generic', capabilities=None, approved_props=()):
        state = self.states[self.resolve(name)]
        available = set(self.character_capabilities(archetype, capabilities))
        anatomy = state['anatomy']
        reasons = []
        if state['archetypes'] != ['any'] and archetype not in state['archetypes']:
            reasons.append('archetype ' + archetype + ' is not applicable')
        missing = set(anatomy['requires_all']) - available
        if missing:
            reasons.append('requires anatomy: ' + ', '.join(sorted(missing)))
        if anatomy['requires_any'] and not available & set(anatomy['requires_any']):
            reasons.append('requires one of anatomy: ' + ', '.join(anatomy['requires_any']))
        forbidden = set(anatomy['excludes']) & available
        if forbidden:
            reasons.append('excludes anatomy: ' + ', '.join(sorted(forbidden)))
        props = set(state['props']['required']) - set(approved_props)
        if props:
            reasons.append('requires explicitly approved props: ' + ', '.join(sorted(props)))
        return reasons

    def search(self, query='', *, category=None, family=None, tags=(), archetype=None,
               capabilities=None, approved_props=(), compatibility=None):
        if category is not None:
            _require(category in self.categories, 'unknown category: ' + category)
        if compatibility is not None:
            _require(compatibility in ('custom-profile', 'codex'), 'compatibility must be custom-profile or codex')
        if archetype is not None:
            self.character_capabilities(archetype, capabilities)
        words = query.casefold().split()
        results = []
        for name in sorted(self.states):
            state = self.states[name]
            haystack = ' '.join([name, state['name'], state['description'], state['category'], state['family'],
                                 self.categories[state['category']]['name'], *state['tags'], *state['aliases'],
                                 state['expression'], *state['poses'], state['animation']['purpose'],
                                 state['animation']['generation']['instructions'],
                                 *state['animation']['generation']['requirements'],
                                 *state['semantic_review']]).casefold()
            if any(word not in haystack for word in words):
                continue
            if category and state['category'] != category or family and state['family'] != family:
                continue
            if tags and not set(tags) <= set(state['tags']):
                continue
            if compatibility == 'codex':
                continue  # The catalog is intentionally not an expanded Codex profile.
            if archetype and self.incompatibilities(name, archetype, capabilities, approved_props):
                continue
            results.append(copy.deepcopy(state))
        return results


def load_library(path=None, *, pack_files=(), catalog_files=()):
    """Load a complete library directory plus explicitly named JSON extensions.

    Identical duplicate extension records are idempotent; different records with
    the same ID fail. An extension-only ``entry_transitions`` map explicitly adds
    legal source-to-new-state edges, for example ``{"idle": ["my-bow"]}``.
    It cannot change existing state meanings or grant new entry to built-in IDs.
    """
    directory = Path(path or DEFAULT_LIBRARY)
    documents = {name: _read_json(directory / name) for name in LIBRARY_FILES}
    _root(documents['catalog.json'], 'states', {'catalog_version', 'categories'})
    _root(documents['packs.json'], 'packs')
    _root(documents['archetypes.json'], 'archetypes', {'capabilities'})
    _root(documents['recipes.json'], 'recipes')
    _root(documents['animation-recipes.json'], 'recipes')
    sources = [{'name': name, 'sha256': sha(directory / name)} for name in LIBRARY_FILES]
    builtin_state_ids = set(_records(documents['catalog.json']['states'], 'built-in state'))
    def merge(document, extension, key, label):
        current = _records(document[key], label)
        for record in extension[key]:
            _require(isinstance(record, dict) and isinstance(record.get('id'), str), label + ' requires record IDs')
            if record['id'] in current:
                _require(current[record['id']] == record, label + ' conflicts with existing definition: ' + record['id'])
            else:
                document[key].append(copy.deepcopy(record)); current[record['id']] = record
    for path in pack_files:
        extension = _read_json(path); _root(extension, 'packs')
        merge(documents['packs.json'], extension, 'packs', 'custom pack')
        sources.append({'name': Path(path).name, 'sha256': sha(path)})
    processed_extensions = set()
    for path in catalog_files:
        extension = _read_json(path); _root(extension, 'states', {'catalog_version', 'categories', 'entry_transitions'})
        extension_hash = hash_object(extension)
        if extension_hash in processed_extensions:
            sources.append({'name': Path(path).name, 'sha256': sha(path)})
            continue
        _require(extension.get('catalog_version') == documents['catalog.json']['catalog_version'],
                 'catalog extension version must match the base catalog')
        _require(isinstance(extension.get('categories'), list), 'catalog extension requires categories list')
        introduced_ids = set(_records(extension['states'], 'custom state')) - builtin_state_ids
        merge(documents['catalog.json'], extension, 'states', 'custom state')
        merge(documents['catalog.json'], extension, 'categories', 'custom category')
        entries = extension.get('entry_transitions', {})
        _require(isinstance(entries, dict), 'entry_transitions must be a source-to-new-state-list object')
        effective_states = {record['id']: record for record in documents['catalog.json']['states']}
        for source, targets in entries.items():
            _slug(source, 'entry transition source')
            _require(source in effective_states, 'unknown entry transition source: ' + source)
            _strings(targets, 'entry transition targets', nonempty=True, slugs=True)
            _require(set(targets) <= introduced_ids,
                     'entry transitions may target only new state definitions included in this extension')
            legal = effective_states[source].get('legal_transitions')
            _strings(legal, source + '.legal_transitions', slugs=True)
            legal.extend(target for target in targets if target not in legal)
        sources.append({'name': Path(path).name, 'sha256': sha(path)})
        processed_extensions.add(extension_hash)
    return StateLibrary(documents['catalog.json'], documents['packs.json'], documents['archetypes.json'],
                        documents['recipes.json'], documents['animation-recipes.json'], source_files=sources)


def validate_selection(value):
    """Strict portable saved compile options; this does not assert artwork exists."""
    _keys(value, SELECTION_KEYS, 'state selection', {'schema_version'})
    _require(type(value['schema_version']) is int and value['schema_version'] == 1, 'state selection schema_version must be 1')
    result = copy.deepcopy(value)
    for key in ('states', 'packs', 'capabilities', 'approved_props'):
        if key in result:
            _strings(result[key], 'state selection.' + key, slugs=key != 'approved_props', unique=key not in ('states', 'packs'))
    for key in ('profile_id', 'recipe', 'archetype'):
        if key in result:
            _slug(result[key], 'state selection.' + key)
    if 'layout' in result:
        _keys(result['layout'], {'columns', 'cell_width', 'cell_height'}, 'state selection.layout')
        for key, number in result['layout'].items():
            _integer(number, 1, 4096, 'state selection.layout.' + key)
    for key in ('max_states', 'limit'):
        if key in result:
            _integer(result[key], 1, 256, 'state selection.' + key)
    if 'queue_limit' in result:
        _integer(result['queue_limit'], 0, 32, 'state selection.queue_limit')
    for flag in ('allow_large', 'reduced_motion'):
        if flag in result:
            _require(type(result[flag]) is bool, 'state selection.' + flag + ' must be boolean')
    if 'anatomy_policy' in result:
        _require(result['anatomy_policy'] in ('error', 'substitute', 'filter'), 'anatomy_policy must be error, substitute, or filter')
    if 'animation_recipes' in result:
        _require(isinstance(result['animation_recipes'], dict), 'animation_recipes must be a state-to-recipe mapping')
        for state, recipe in result['animation_recipes'].items():
            _slug(state, 'animation recipe state'); _slug(recipe, 'animation recipe id')
    return result


def compile_selection(selection, *, library=None, **overrides):
    options = validate_selection(selection)
    options.pop('schema_version')
    layout = options.pop('layout', {})
    options.update(layout)
    options.update(overrides)
    return compile_profile(library=library, **options)


def compile_profile(states=None, packs=None, recipe=None, *, profile_id='character-states',
                    archetype='generic', capabilities=None, approved_props=None,
                    anatomy_policy='error', max_states=DEFAULT_STATE_LIMIT, allow_large=False,
                    limit=None, cell_width=192, cell_height=208, columns=None, queue_limit=None,
                    animation_recipes=None, reduced_motion=False, library=None):
    """Return ``{'profile': validated_profile, 'manifest': bound_selection}``.

    Explicit states and recipe states precede pack members. Canonical IDs are
    deduplicated in first-selection order. Mandatory completion/recovery and
    directional dependencies are added in deterministic order and count toward
    every limit. ``filter`` can omit incompatible pack members; explicit states
    require compatibility or the explicitly selected ``substitute`` policy.
    """
    lib = library or load_library()
    for value, label in ((states, 'states'), (packs, 'packs'), (approved_props, 'approved_props'), (capabilities, 'capabilities')):
        _require(value is None or isinstance(value, list), label + ' must be a list when supplied')
    _require(animation_recipes is None or isinstance(animation_recipes, dict), 'animation_recipes must be an object when supplied')
    states, packs = list(states or []), list(packs or [])
    approved_props = list(approved_props or [])
    animation_recipes = dict(animation_recipes or {})
    selection = {'schema_version': 1, 'profile_id': profile_id, 'states': states, 'packs': packs,
                 'archetype': archetype, 'approved_props': approved_props, 'anatomy_policy': anatomy_policy,
                 'layout': {'cell_width': cell_width, 'cell_height': cell_height},
                 'max_states': max_states, 'allow_large': allow_large, 'animation_recipes': animation_recipes,
                 'reduced_motion': reduced_motion}
    if recipe is not None: selection['recipe'] = recipe
    if capabilities is not None: selection['capabilities'] = list(capabilities)
    if columns is not None: selection['layout']['columns'] = columns
    if limit is not None: selection['limit'] = limit
    if queue_limit is not None: selection['queue_limit'] = queue_limit
    validate_selection(selection)
    _require(max_states <= DEFAULT_STATE_LIMIT or allow_large,
             f'max_states above {DEFAULT_STATE_LIMIT} requires explicit allow_large/--allow-large')
    available = lib.character_capabilities(archetype, capabilities)
    selection['capabilities'] = available
    _require(states or packs or recipe, 'select at least one state, pack, or transition recipe')
    _require(recipe is None or recipe in lib.recipes, 'unknown transition recipe: ' + str(recipe))
    recipe_record = copy.deepcopy(lib.recipes[recipe]) if recipe else None
    for pack in packs:
        _require(pack in lib.packs, 'unknown pack: ' + pack)
    selection_only = [pack for pack in packs if lib.packs[pack]['selection_only']]
    _require(not selection_only or states or limit is not None,
             'selection-only packs require an explicit --state subset or --limit; a complete studio is not a monolithic atlas')
    selected, reasons, substitutions, omitted, adaptations = [], {}, [], [], []
    explicit = {lib.resolve(value) for value in states}
    mandatory_recipe = set(recipe_record['states']) if recipe_record else set()
    def add(value, reason, *, allow_filter=False):
        name = lib.resolve(value)
        problems = lib.incompatibilities(name, archetype, available, approved_props)
        if problems:
            description = '; '.join(problems)
            if anatomy_policy == 'filter' and allow_filter:
                omitted.append({'state': name, 'reason': description})
                return None
            if anatomy_policy == 'substitute' and name not in mandatory_recipe:
                original, visited = name, set()
                while problems:
                    _require(name not in visited, 'no applicable fallback for ' + original + ': ' + description)
                    visited.add(name)
                    name = lib.states[name]['anatomy']['fallback']
                    problems = lib.incompatibilities(name, archetype, available, approved_props)
                substitutions.append({'requested': original, 'selected': name, 'reason': description})
                reason += '; explicit substitution for ' + original
            else:
                _require(False, name + ': ' + description + '; choose suitable anatomy/approved props, an explicit substitution policy, or filter pack members')
        if name not in selected:
            selected.append(name)
        reasons.setdefault(name, [])
        if reason not in reasons[name]: reasons[name].append(reason)
        return name
    for value in states:
        add(value, 'explicit state' + (' alias ' + value if value not in lib.states else ''))
    if recipe_record:
        for name in recipe_record['states']:
            add(name, 'transition recipe ' + recipe)
    if limit is not None:
        _require(len(selected) <= limit, 'explicit states and recipe exceed selection limit')
    for pack in packs:
        members = lib.expand_pack(pack)
        if lib.packs[pack]['selection_only'] and states and limit is None:
            _require(explicit <= set(members), 'explicit subset is not contained in selection-only pack ' + pack)
            for name in selected:
                if name in members:
                    reasons[name].append('selected subset of ' + pack)
            continue
        for name in members:
            if limit is not None and name not in selected and len(selected) >= limit:
                omitted.append({'state': name, 'reason': 'explicit selection limit'})
                continue
            add(name, 'pack ' + pack, allow_filter=name not in explicit and name not in mandatory_recipe)
    _require(selected, 'selection contains no applicable states')
    initial = recipe_record['initial'] if recipe_record else 'idle'
    cancel_state = recipe_record['cancel_state'] if recipe_record else 'idle'
    for name, reason in ((initial, 'initial state'), (cancel_state, 'cancellation recovery')):
        actual = add(name, reason)
        _require(actual == name, 'initial/cancellation state cannot be substituted')
    index = 0
    while index < len(selected):
        name = selected[index]; index += 1
        state = lib.states[name]
        completion = recipe_record['completion'].get(name) if recipe_record else state['completion']
        dependencies = [] if recipe_record else [('recovery', state['recovery'])]
        if completion: dependencies.append(('completion', completion))
        dependencies.extend(('direction dependency', target) for target in state['direction']['dependencies'])
        for kind, target in dependencies:
            actual = add(target, kind + ' for ' + name)
            _require(actual == target, name + ': mandatory ' + kind + ' cannot be substituted; select a compatible recipe/state')
        _require(len(selected) <= max_states,
                 f'selection plus dependencies requires {len(selected)} states, exceeding max_states={max_states}; use a smaller subset or an explicit bounded override')
    if recipe_record:
        _require(set(selected) == set(recipe_record['states']),
                 'a transition recipe declares the complete event graph; extra selected states or dependencies need an explicit custom recipe')
    overrides = {}
    for value, recipe_id in animation_recipes.items():
        name = lib.resolve(value)
        _require(name in selected, 'animation recipe override names unselected state: ' + name)
        _require(recipe_id in lib.animation_recipes, 'unknown animation recipe: ' + recipe_id)
        _require(name not in overrides, 'conflicting animation recipe aliases for ' + name)
        overrides[name] = recipe_id
    compiled_states, requirements = [], {}
    for name in selected:
        definition = lib.states[name]
        animation = copy.deepcopy(definition['animation'])
        generation = animation['generation']
        generation['instructions'] += '\nKey poses and ordered action: ' + ' -> '.join(definition['poses'])
        generation['instructions'] += '\nExpression and body language: ' + definition['expression']
        direction = definition['direction']
        generation['instructions'] += '\nOrientation: facing ' + direction['facing'] + '; travel ' + direction['travel'] + '. Preserve approved asymmetries; no inferred mirroring.'
        generation['instructions'] += '\nReduced-motion pose: ' + definition['reduced_motion']['description']
        generation['requirements'].extend(IDENTITY_REQUIREMENTS)
        generation['requirements'].extend('Negative constraint: ' + text for text in definition['negative_constraints'])
        generation['requirements'].extend('Semantic visual review: ' + text for text in definition['semantic_review'])
        generation['requirements'].append('Approved character capabilities for this selection: ' + (', '.join(available) or 'none declared') + '. Do not add missing anatomy.')
        generation['requirements'].append('Required approved props: ' + (', '.join(definition['props']['required']) or 'none') + '. Optional props may appear only if explicitly present in the approved identity.')
        playback = animation['playback']
        completion = recipe_record['completion'].get(name) if recipe_record else definition['completion']
        if recipe_record and name in recipe_record['completion']:
            if playback.get('mode', 'loop') != 'once':
                adaptations.append({'state': name, 'kind': 'recipe-once', 'reason': 'finite completion segment in ' + recipe})
            playback['mode'] = 'once'
        if completion:
            playback['completion'] = completion
        playback['reduced_motion_frame'] = definition['reduced_motion']['frame']
        if name in overrides:
            motion_recipe = lib.animation_recipes[overrides[name]]
            animation['frames'] = motion_recipe['frames']
            animation['durations'] = copy.deepcopy(motion_recipe['durations'])
            generation['instructions'] += '\nSelected animation recipe ' + overrides[name] + ': ' + ' -> '.join(motion_recipe['key_phases']) + '. Seam: ' + motion_recipe['loop_seam']
            adaptations.append({'state': name, 'kind': 'animation-recipe', 'reason': overrides[name]})
            _require(playback.get('hold_frame', 0) < animation['frames'] and playback['reduced_motion_frame'] < animation['frames'],
                     name + ': animation recipe makes the hold/reduced-motion frame invalid')
        if reduced_motion:
            generation['instructions'] = ('Create exactly one static expressive pose for ' + definition['description'] + '. '
                                          + definition['reduced_motion']['description'] + '\nExpression: ' + definition['expression']
                                          + '\nFacing: ' + direction['facing'] + '. Preserve approved asymmetries; no inferred mirroring.'
                                          + '\nThis is a deliberately static alternative. Do not render a motion sequence or duplicate animation frames.')
            generation['requirements'] = (copy.deepcopy(IDENTITY_REQUIREMENTS)
                                          + ['Negative constraint: ' + text for text in definition['negative_constraints']]
                                          + ['Semantic visual review: the single pose must communicate the named action or expression clearly while preserving the approved identity.'])
            animation['frames'], animation['durations'], animation['motion'] = 1, [1000], 'static'
            animation['validation']['min_motion'] = 0
            playback.clear(); playback.update(mode='hold', hold_frame=0, interruptible=True, reduced_motion_frame=0)
            adaptations.append({'state': name, 'kind': 'static-alternative', 'reason': 'explicit reduced-motion profile'})
        # All timing instructions reflect the actual compiled row after overrides.
        generation['requirements'].append('Render exactly ' + str(animation['frames']) + ' distinct frame slots with intended durations in milliseconds: ' + ', '.join(map(str, animation['durations'])) + '.')
        generation['requirements'] = list(dict.fromkeys(generation['requirements']))
        compiled_states.append(animation)
        requirements[name] = {'requires_all': copy.deepcopy(definition['anatomy']['requires_all']),
                              'requires_any': copy.deepcopy(definition['anatomy']['requires_any']),
                              'excludes': copy.deepcopy(definition['anatomy']['excludes']),
                              'required_props': copy.deepcopy(definition['props']['required']),
                              'direction': copy.deepcopy(direction),
                              'reduced_motion': copy.deepcopy(definition['reduced_motion']),
                              'semantic_review': copy.deepcopy(definition['semantic_review'])}
    events, rules = {}, {}
    for name in ([] if recipe_record else selected):
        definition = lib.states[name]
        for event in list(dict.fromkeys(['state:' + name, *definition['events']])):
            _require(event not in events or events[event] == name, 'conflicting selected event: ' + event)
            events[event] = name
            legal_sources = [source for source in selected if source == name or name in lib.states[source]['legal_transitions']]
            rules[event] = {'target': name, 'priority': definition['priority'],
                            'interrupt': definition['interrupt'], 'restart': definition['repeat'] == 'restart',
                            'from': legal_sources}
    if recipe_record:
        for event, rule in recipe_record['events'].items():
            _require(event not in events or events[event] == rule['target'], 'recipe event conflicts with selected state event: ' + event)
            events[event], rules[event] = rule['target'], copy.deepcopy(rule)
            if reduced_motion and rules[event].get('resume'):
                rules[event]['resume'] = False
    if reduced_motion and recipe_record:
        for source, target in recipe_record['completion'].items():
            event = 'next:' + source
            _require(event not in events, 'static completion event conflicts with recipe event: ' + event)
            events[event] = target
            rules[event] = {'target': target, 'from': [source], 'priority': 0,
                            'interrupt': 'always', 'restart': False}
            adaptations.append({'state': source, 'kind': 'static-recipe-step',
                                'reason': 'disabled animation completion is an explicit ' + event + ' event to ' + target})
        adaptations.append({'state': initial, 'kind': 'static-recipe',
                            'reason': 'completion animation is disabled; recipe events, explicit next:<source> steps, and cancellation select static poses'})
    actual_columns = columns if columns is not None else max(state['frames'] for state in compiled_states)
    _require(max(state['frames'] for state in compiled_states) * cell_width * cell_height <= MAX_SOURCE_PIXELS,
             'largest source strip exceeds the existing source pixel limit; reduce cells or frames')
    profile = load_profile({'schema_version': 1, 'id': profile_id,
                            'layout': {'columns': actual_columns, 'cell_width': cell_width, 'cell_height': cell_height},
                            'states': compiled_states,
                            'generation': {'skill': 'imagegen', 'requires_identity_reference': True,
                                           'instructions': 'Create selected reusable character states from one approved canonical identity. Keep a consistent character scale and the approved visual style.',
                                           'requirements': copy.deepcopy(IDENTITY_REQUIREMENTS)},
                            'validation': {'require_provenance': True, 'allow_detached_details': False},
                            'events': events,
                            'playback': {'initial': initial, 'cancel_state': cancel_state,
                                         'queue_limit': queue_limit if queue_limit is not None else (recipe_record['queue_limit'] if recipe_record else 8),
                                         'events': rules},
                            'export': {'formats': ['frames', 'atlas', 'browser'], 'static_state': initial,
                                       'static_frame': next(state['playback']['reduced_motion_frame'] for state in compiled_states if state['id'] == initial),
                                       'codex_compatible': False}})
    # Existing validation covers resource geometry; additionally reject finite
    # recipe cycles and ensure automatic completion cannot trap the consumer.
    _no_cycles({state['id']: [state['playback']['completion']] if state['playback'].get('completion') else []
                for state in profile['states']}, 'compiled completion')
    adjacency = {name: set() for name in selected}
    for state in profile['states']:
        if state['playback'].get('completion'):
            adjacency[state['id']].add(state['playback']['completion'])
    for rule in rules.values():
        for source in rule.get('from', selected): adjacency[source].add(rule['target'])
    _require(set(selected) <= _reachable(adjacency, initial), 'compiled event graph contains inaccessible states')
    reverse = {name: set() for name in selected}
    for source, targets in adjacency.items():
        for target in targets: reverse[target].add(source)
    _require(set(selected) <= _reachable(reverse, cancel_state), 'compiled event graph has an inaccessible recovery path')
    resources = check_resources(profile)
    atlas_pixels = profile['layout']['width'] * profile['layout']['height']
    estimates = {'state_count': len(selected), 'frame_count': resources['total_frames'],
                 'generation_jobs': len(selected) + 1, 'model_calls_baseline': len(selected) + 1,
                 'estimate_note': 'One canonical base plus one selected state job each; excludes retries. Explicitly imported artwork can use zero model calls. No generation is performed by compilation.',
                 'atlas_pixels': atlas_pixels, 'rgba_atlas_bytes': atlas_pixels * 4,
                 'largest_source_strip_pixels': max(state['frames'] for state in profile['states']) * cell_width * cell_height,
                 **resources}
    selection['layout'] = {key: profile['layout'][key] for key in ('columns', 'cell_width', 'cell_height')}
    selection['queue_limit'] = profile['playback']['queue_limit']
    manifest = {'schema_version': 1, 'kind': 'hatch-state-selection', 'catalog_version': lib.version,
                'catalog_sha256': lib.sha256, 'profile_sha256': profile_hash(profile),
                'selected_states': selected, 'selection': selection,
                'required_props': sorted({prop for name in selected for prop in requirements[name]['required_props']}),
                'state_requirements': requirements, 'selection_reasons': reasons,
                'substitutions': substitutions, 'omitted': omitted, 'adaptations': adaptations,
                'estimates': estimates, 'source_files': copy.deepcopy(lib.source_files),
                'artwork_status': 'definitions-only', 'production_review': 'not-performed'}
    manifest['manifest_sha256'] = hash_object(manifest)
    validate_selection_manifest(manifest, profile)
    return {'profile': profile, 'manifest': manifest}


def validate_selection_manifest(manifest, profile):
    """Validate self-consistency and profile binding without needing a catalog.

    Hashes bind portable metadata; they are not a signature or a human approval.
    Production preparation must reconcile required_props against its independently
    approved structured identity and still use the existing review gates.
    """
    _keys(manifest, MANIFEST_KEYS, 'state selection manifest', MANIFEST_KEYS)
    _require(type(manifest['schema_version']) is int and manifest['schema_version'] == 1,
             'state selection manifest schema_version must be 1')
    _require(manifest['kind'] == 'hatch-state-selection', 'incorrect state selection manifest kind')
    for name in ('catalog_sha256', 'profile_sha256', 'manifest_sha256'):
        _require(isinstance(manifest[name], str) and bool(HASH.fullmatch(manifest[name])), name + ' must be SHA-256')
    _require(isinstance(manifest['catalog_version'], str) and re.fullmatch(r'\d+\.\d+\.\d+', manifest['catalog_version']), 'invalid catalog version')
    payload = copy.deepcopy(manifest); payload.pop('manifest_sha256')
    _require(hash_object(payload) == manifest['manifest_sha256'], 'selection manifest hash mismatch')
    profile = load_profile(profile)
    _require(profile_hash(profile) == manifest['profile_sha256'], 'selection manifest profile hash mismatch')
    names = [state['id'] for state in profile['states']]
    _require(manifest['selected_states'] == names, 'selection manifest states must match profile order')
    selection = validate_selection(manifest['selection'])
    normalized_keys = {'schema_version', 'profile_id', 'states', 'packs', 'archetype', 'capabilities',
                       'approved_props', 'anatomy_policy', 'layout', 'max_states', 'allow_large',
                       'animation_recipes', 'reduced_motion', 'queue_limit'}
    _require(normalized_keys <= set(selection), 'manifest selection must retain normalized compilation options')
    _require(selection.get('profile_id') == profile['id'], 'selection profile id mismatch')
    _require(selection['layout'] == {key: profile['layout'][key] for key in ('columns', 'cell_width', 'cell_height')},
             'selection layout disagrees with profile')
    _require(selection['queue_limit'] == profile.get('playback', {}).get('queue_limit', 8), 'selection queue limit disagrees with profile')
    _require(len(names) <= selection['max_states'] and (selection['max_states'] <= DEFAULT_STATE_LIMIT or selection['allow_large']),
             'manifest selection exceeds its declared operational limit')
    _require(profile['export'].get('codex_compatible') is False, 'state catalog compilation must remain a custom profile')
    _strings(manifest['required_props'], 'selection required props')
    _require(set(manifest['required_props']) <= set(selection.get('approved_props', [])), 'required props lack declared compile approval')
    available = set(selection.get('capabilities', []))
    _require(isinstance(manifest['state_requirements'], dict) and set(manifest['state_requirements']) == set(names),
             'state requirements must cover exact selected states')
    all_props = set()
    for name, requirement in manifest['state_requirements'].items():
        _keys(requirement, {'requires_all', 'requires_any', 'excludes', 'required_props', 'direction', 'reduced_motion', 'semantic_review'}, name + ' selection requirements',
              {'requires_all', 'requires_any', 'excludes', 'required_props', 'direction', 'reduced_motion', 'semantic_review'})
        for field in ('requires_all', 'requires_any', 'excludes', 'required_props', 'semantic_review'):
            _strings(requirement[field], name + '.' + field, nonempty=field == 'semantic_review')
        _require(set(requirement['requires_all']) <= available and
                 (not requirement['requires_any'] or bool(set(requirement['requires_any']) & available)) and
                 not set(requirement['excludes']) & available, name + ': manifest anatomy is incompatible')
        all_props.update(requirement['required_props'])
        _keys(requirement['direction'], {'facing', 'travel', 'mirror_policy', 'dependencies'}, name + ' direction',
              {'facing', 'travel', 'mirror_policy', 'dependencies'})
        _require(requirement['direction']['facing'] in ('front', 'left', 'right', 'back', 'any') and
                 requirement['direction']['travel'] in ('none', 'left', 'right', 'up', 'down', 'forward', 'backward') and
                 requirement['direction']['mirror_policy'] == 'explicit-approval-only', name + ': unsafe direction metadata')
        _strings(requirement['direction']['dependencies'], name + ' direction dependencies', slugs=True)
        _require(set(requirement['direction']['dependencies']) <= set(names), name + ': missing direction dependencies')
        _keys(requirement['reduced_motion'], {'mode', 'frame', 'description'}, name + ' reduced motion', {'mode', 'frame', 'description'})
        _require(requirement['reduced_motion']['mode'] == 'static', name + ': invalid static alternative')
        _integer(requirement['reduced_motion']['frame'], 0, 63, name + ' static frame')
        if not selection['reduced_motion']:
            current = next(state for state in profile['states'] if state['id'] == name)
            _require(requirement['reduced_motion']['frame'] == current.get('playback', {}).get('reduced_motion_frame'),
                     name + ': reduced-motion selection disagrees with profile')
        _text(requirement['reduced_motion']['description'], name + ' static description')
    _no_cycles({name: requirement['direction']['dependencies'] for name, requirement in manifest['state_requirements'].items()},
               'manifest direction dependency')
    _require(all_props == set(manifest['required_props']), 'required prop union does not match states')
    _require(isinstance(manifest['selection_reasons'], dict) and set(manifest['selection_reasons']) == set(names), 'selection reasons must cover states')
    for name, reasons in manifest['selection_reasons'].items():
        _strings(reasons, name + ' selection reasons', nonempty=True)
    for key, fields in (('substitutions', {'requested', 'selected', 'reason'}),
                        ('omitted', {'state', 'reason'}), ('adaptations', {'state', 'kind', 'reason'})):
        _require(isinstance(manifest[key], list), key + ' must be a list')
        for record in manifest[key]:
            _keys(record, fields, key, fields)
            for value in record.values(): _text(value, key)
    _require(isinstance(manifest['source_files'], list), 'source files must be a list')
    for record in manifest['source_files']:
        _keys(record, {'name', 'sha256'}, 'source file', {'name', 'sha256'})
        _text(record['name'], 'source filename')
        _require(not any(character in record['name'] for character in '/\\') and record['name'] not in ('.', '..'),
                 'source filenames must be portable basenames')
        _require(isinstance(record['sha256'], str) and bool(HASH.fullmatch(record['sha256'])), 'source hash must be SHA-256')
    resources = check_resources(profile)
    expected_estimates = {'state_count': len(names), 'frame_count': resources['total_frames'],
                          'generation_jobs': len(names) + 1, 'model_calls_baseline': len(names) + 1,
                          'atlas_pixels': profile['layout']['width'] * profile['layout']['height'],
                          'rgba_atlas_bytes': profile['layout']['width'] * profile['layout']['height'] * 4,
                          'largest_source_strip_pixels': max(state['frames'] for state in profile['states']) * profile['layout']['cell_width'] * profile['layout']['cell_height'],
                          **resources}
    _keys(manifest['estimates'], set(expected_estimates) | {'estimate_note'}, 'selection estimates', set(expected_estimates) | {'estimate_note'})
    _text(manifest['estimates']['estimate_note'], 'selection estimate note')
    _require(all(type(manifest['estimates'][key]) is int and manifest['estimates'][key] == value
                 for key, value in expected_estimates.items()), 'selection estimates disagree with validated profile')
    _require(manifest['artwork_status'] == 'definitions-only' and manifest['production_review'] == 'not-performed',
             'selection manifests cannot claim production artwork or review')
    return copy.deepcopy(manifest)


def write_compilation(result, output, *, manifest_output=None):
    """Save an already validated profile and companion with no overwrite."""
    profile, manifest = load_profile(result['profile']), result['manifest']
    validate_selection_manifest(manifest, profile)
    output = Path(output).resolve()
    companion = Path(manifest_output).resolve() if manifest_output else output.with_suffix('.selection.json')
    _require(output != companion, 'profile and selection manifest need different paths')
    for path in (output, companion):
        _require(not path.exists() and not path.is_symlink(), 'output already exists; choose a new path: ' + str(path))
    written = []
    try:
        for path, value in ((output, profile), (companion, manifest)):
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open('x', encoding='utf-8') as stream:
                written.append(path)
                stream.write(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + '\n')
    except OSError:
        for path in written:
            path.unlink(missing_ok=True)
        raise
    return {'profile': str(output), 'selection_manifest': str(companion), 'profile_sha256': profile_hash(profile)}


def preview_states(states=None, *, library=None, run_dir=None, export_dir=None):
    """Inspect available real artifacts; never generate or fabricate a preview."""
    lib = library or load_library()
    _require(not (run_dir and export_dir), 'select either a run directory or an export directory')
    requested = list(dict.fromkeys(lib.resolve(value) for value in (states or sorted(lib.states))))
    result = {'artwork_generated': False, 'external_integration_verified': False, 'states': [], 'preview_html': None,
              'catalog_binding': {'status': 'no-selection-evidence', 'profile_matches': False, 'catalog_matches': False,
                                  'note': 'A matching state ID alone does not establish matching catalog semantics.'}}
    root = Path(export_dir or run_dir).resolve() if export_dir or run_dir else None
    profile, records, fixture, reviewed = None, {}, None, False
    provenance = {}
    if root:
        _require(root.is_dir(), 'preview source directory does not exist')
        profile = load_profile(root / 'profile.json')
        records = {state['id']: state for state in profile['states']}
        if export_dir:
            metadata = _read_json(root / 'animation.json')
            _require(metadata.get('profile_sha256') == profile_hash(profile), 'export animation/profile hash mismatch')
            receipt = _read_json(root / 'export-receipt.json')
            _require(receipt.get('profile_sha256') == profile_hash(profile) and isinstance(receipt.get('files'), dict), 'export receipt/profile mismatch')
            actual_files = {path.relative_to(root).as_posix() for path in root.rglob('*') if path.is_file()
                            and path.relative_to(root).as_posix() != 'export-receipt.json'}
            _require(set(receipt['files']) == actual_files, 'export receipt does not cover the complete artifact set')
            for relative, digest in receipt['files'].items():
                candidate = (root / relative).resolve()
                _require(candidate.is_relative_to(root) and candidate.is_file() and sha(candidate) == digest,
                         'export receipt has a missing, unsafe, or changed artifact: ' + relative)
            fixture = metadata.get('fixture') is True
            if (root / 'provenance.json').is_file():
                provenance = _read_json(root / 'provenance.json')
                fixture = fixture or provenance.get('fixture') is True
                reviewed = provenance.get('visual_review', {}).get('accepted') is True if isinstance(provenance.get('visual_review'), dict) else False
            if (root / 'preview.html').is_file(): result['preview_html'] = str(root / 'preview.html')
        else:
            import hatch
            provenance = hatch.manifest(root)
            fixture = provenance['fixture_mode']
            reviewed = hatch._review_ok(root, provenance)
            candidate = root / 'review' / 'review.html'
            if candidate.is_file(): result['preview_html'] = str(candidate)
        for candidate in (root / 'state-selection.json', root / 'profile.selection.json'):
            if candidate.is_file():
                try:
                    bound = validate_selection_manifest(_read_json(candidate), profile)
                    catalog_matches = bound['catalog_sha256'] == lib.sha256
                    result['catalog_binding'] = {'status': 'matching-bound-selection' if catalog_matches else 'different-catalog-version',
                                                 'profile_matches': True, 'catalog_matches': catalog_matches,
                                                 'profile_sha256': bound['profile_sha256'], 'catalog_sha256': bound['catalog_sha256'],
                                                 'note': 'The profile is bound to the retained selection; production semantic review is reported separately.'}
                except (ValueError, OSError) as exc:
                    result['catalog_binding'] = {'status': 'invalid-or-stale-selection', 'profile_matches': False,
                                                 'catalog_matches': False, 'note': str(exc)}
                break
    for name in requested:
        entry = {'id': name, 'status': 'not-generated', 'frames': [], 'fixture': fixture,
                 'visual_review': 'not-performed', 'production_artwork': False,
                 'matches_catalog_selection': result['catalog_binding']['profile_matches'] and result['catalog_binding']['catalog_matches']}
        if name in records:
            try:
                files = indexed_frames(root / 'frames', name, records[name]['frames'])
                from PIL import Image
                for path in files:
                    with Image.open(path) as image:
                        _require(image.size == (profile['layout']['cell_width'], profile['layout']['cell_height']), name + ': preview frame geometry mismatch')
                entry['frames'] = [str(path) for path in files]
                entry['status'] = 'available-fixture' if fixture else 'available-artwork'
                entry['visual_review'] = 'current-fixture-gate' if reviewed and fixture else ('recorded-production-review' if reviewed else 'not-current-or-unreviewed')
                entry['production_artwork'] = bool(not fixture and reviewed and provenance)
            except (OSError, ValueError) as exc:
                entry['status'] = 'not-generated' if not (root / 'frames' / name).exists() else 'incomplete-or-invalid-artwork'
                entry['reason'] = str(exc)
        result['states'].append(entry)
    return result


def _arguments(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    def common(target):
        target.add_argument('--library', default=argparse.SUPPRESS, help='Complete state-library directory')
        target.add_argument('--pack-file', action='append', default=argparse.SUPPRESS, help='Explicit custom packs JSON')
        target.add_argument('--catalog-file', action='append', default=argparse.SUPPRESS,
                            help='Catalog extension JSON; optional entry_transitions explicitly connects existing sources to newly declared states')
        target.add_argument('--json', action='store_true', default=argparse.SUPPRESS, help='Machine-readable result')
    common(parser)
    sub = parser.add_subparsers(dest='command', required=True)
    for command in ('list', 'search', 'show', 'packs', 'archetypes', 'recipes', 'compile', 'validate', 'preview'):
        child = sub.add_parser(command); common(child)
        if command in ('list', 'search'):
            if command == 'search': child.add_argument('query')
            child.add_argument('--category'); child.add_argument('--family')
            child.add_argument('--tag', action='append', default=[])
            child.add_argument('--archetype'); child.add_argument('--capability', action='append')
            child.add_argument('--approve-prop', action='append', default=[])
            child.add_argument('--compatibility', choices=('custom-profile', 'codex'))
        elif command == 'show': child.add_argument('state')
        elif command == 'packs': child.add_argument('pack', nargs='?')
        elif command == 'recipes':
            child.add_argument('recipe', nargs='?'); child.add_argument('--animation', action='store_true')
        elif command == 'compile':
            child.add_argument('--selection', help='Saved strict state-selection JSON options')
            child.add_argument('--state', '--states', action='append', help='State ID or alias; repeat or comma-separate')
            child.add_argument('--pack', '--packs', action='append', help='Pack ID; repeat or comma-separate')
            child.add_argument('--recipe')
            child.add_argument('--profile-id', '--id')
            child.add_argument('--archetype')
            child.add_argument('--capability', action='append')
            child.add_argument('--approve-prop', action='append')
            child.add_argument('--anatomy-policy', choices=('error', 'filter', 'substitute'))
            for key in ('max-states', 'limit', 'columns', 'cell-width', 'cell-height', 'queue-limit'):
                child.add_argument('--' + key, type=int)
            child.add_argument('--allow-large', action='store_true', default=None)
            child.add_argument('--reduced-motion', action='store_true', default=None)
            child.add_argument('--animation-recipe', action='append', help='Explicit state=recipe timing/phase override')
            child.add_argument('--output', help='New runtime profile JSON path; companion .selection.json is also written')
            child.add_argument('--manifest-output', help='Explicit new selection manifest JSON path')
        elif command == 'preview':
            child.add_argument('state', nargs='*')
            child.add_argument('--run-dir'); child.add_argument('--export-dir')
    return parser, parser.parse_args(argv)


def _split(values):
    return [value.strip() for item in values for value in item.split(',') if value.strip()]


def main(argv=None):
    parser, args = _arguments(argv)
    try:
        lib = load_library(getattr(args, 'library', None), pack_files=getattr(args, 'pack_file', []),
                           catalog_files=getattr(args, 'catalog_file', []))
        command, as_json = args.command, getattr(args, 'json', False)
        if command in ('list', 'search'):
            records = lib.search(getattr(args, 'query', ''), category=args.category, family=args.family,
                                 tags=args.tag, archetype=args.archetype, capabilities=args.capability,
                                 approved_props=args.approve_prop, compatibility=args.compatibility)
            result = {'catalog_version': lib.version, 'count': len(records),
                      'states': [{'id': state['id'], 'name': state['name'], 'category': state['category'],
                                  'family': state['family'], 'description': state['description'],
                                  'frames': state['animation']['frames'], 'mode': state['animation']['playback'].get('mode', 'loop'),
                                  'aliases': state['aliases'], 'artwork_status': 'definitions-only'} for state in records]}
            if not as_json:
                print('ID | Category | Frames | Behavior | Meaning')
                for state in result['states']:
                    print(f"{state['id']} | {state['category']} | {state['frames']} | {state['mode']} | {state['description']}")
                print(f"{len(records)} definitions. Artwork is not generated by catalog discovery.")
                return 0
        elif command == 'show':
            result = {'state': copy.deepcopy(lib.states[lib.resolve(args.state)]), 'artwork_status': 'definitions-only',
                      'catalog_sha256': lib.sha256}
        elif command == 'packs':
            names = [args.pack] if args.pack else list(lib.packs)
            result = {'packs': [{**copy.deepcopy(lib.packs[name]), 'resolved_states': lib.expand_pack(name),
                                  'state_count': len(lib.expand_pack(name))} for name in names if name in lib.packs]}
            _require(not args.pack or bool(result['packs']), 'unknown pack: ' + str(args.pack))
        elif command == 'archetypes':
            result = {'archetypes': list(lib.archetypes.values()), 'capabilities': list(lib.capabilities.values()),
                      'policy': 'Presets are starting assumptions. Explicit capabilities replace the preset; compare with the approved reference before generation.'}
        elif command == 'recipes':
            recipes = lib.animation_recipes if args.animation else lib.recipes
            _require(not args.recipe or args.recipe in recipes, 'unknown recipe: ' + str(args.recipe))
            result = {'kind': 'animation' if args.animation else 'transition',
                      'recipes': [recipes[args.recipe]] if args.recipe else list(recipes.values())}
        elif command == 'compile':
            selection = validate_selection(_read_json(args.selection)) if args.selection else {'schema_version': 1}
            mapping = {'state': 'states', 'pack': 'packs', 'capability': 'capabilities', 'approve_prop': 'approved_props'}
            for source, target in mapping.items():
                value = getattr(args, source)
                if value is not None: selection[target] = _split(value) if source in ('state', 'pack', 'capability') else value
            for name in ('recipe', 'profile_id', 'archetype', 'anatomy_policy', 'max_states', 'allow_large', 'limit', 'queue_limit', 'reduced_motion'):
                value = getattr(args, name)
                if value is not None: selection[name] = value
            for name in ('columns', 'cell_width', 'cell_height'):
                value = getattr(args, name)
                if value is not None: selection.setdefault('layout', {})[name] = value
            if args.animation_recipe:
                overrides = {}
                for raw in args.animation_recipe:
                    _require('=' in raw, '--animation-recipe requires state=recipe')
                    state, recipe_id = raw.split('=', 1)
                    _require(state not in overrides, 'duplicate animation recipe override')
                    overrides[state] = recipe_id
                selection['animation_recipes'] = overrides
            result = compile_selection(selection, library=lib)
            if args.output:
                paths = write_compilation(result, args.output, manifest_output=args.manifest_output)
                result = {'ok': True, **paths, 'selected_states': result['manifest']['selected_states'],
                          'estimates': result['manifest']['estimates'], 'substitutions': result['manifest']['substitutions'],
                          'omitted': result['manifest']['omitted'], 'artwork_status': 'definitions-only'}
            else:
                _require(args.manifest_output is None, '--manifest-output requires --output')
        elif command == 'validate':
            result = {'ok': True, 'catalog_version': lib.version, 'catalog_sha256': lib.sha256,
                      'states': len(lib.states), 'aliases': len(lib.aliases), 'packs': len(lib.packs),
                      'categories': len(lib.categories), 'archetypes': len(lib.archetypes),
                      'transition_recipes': len(lib.recipes), 'animation_recipes': len(lib.animation_recipes),
                      'artwork_status': 'definitions-only'}
        else:
            result = preview_states(args.state, library=lib, run_dir=args.run_dir, export_dir=args.export_dir)
        print(json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False))
        return 0
    except (ValueError, OSError, KeyError) as exc:
        parser.error(str(exc))


if __name__ == '__main__':
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8')
    raise SystemExit(main())

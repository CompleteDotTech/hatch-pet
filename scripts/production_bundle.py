#!/usr/bin/env python3
"""Bounded transport parts for complete hash-verified production archives.

Restoration always passes the assembled ZIP through the existing production
archive verifier and staged restore implementation. Parts change transport only.
"""
from __future__ import annotations
import argparse
from contextlib import contextmanager
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import shutil
import sys
import tempfile
import production_workflow as workflow

BUNDLE_INDEX = 'production-bundle.json'
MAX_PART_BYTES = 24 * 1024 * 1024
MAX_BUNDLE_BYTES = workflow.MAX_ARCHIVE_BYTES
MAX_BUNDLE_PARTS = 512
MAX_INDEX_BYTES = 1024 * 1024
BLOCK_BYTES = 1024 * 1024


def _keys(value, expected, label):
    if not isinstance(value, dict) or set(value) != set(expected):
        raise ValueError(label + ' has missing or unsupported fields')


def _digest(value, label):
    if not isinstance(value, str) or not re.fullmatch(r'[0-9a-f]{64}', value):
        raise ValueError(label + ' must be a lowercase SHA-256 digest')


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate JSON key in bundle index: ' + key)
        result[key] = value
    return result


def _load_index(bundle_index):
    path = Path(bundle_index).resolve()
    if path.is_dir():
        path = path / BUNDLE_INDEX
    if not path.is_file() or path.stat().st_size > MAX_INDEX_BYTES:
        raise ValueError('bundle index is missing or exceeds the 1 MiB index bound')
    raw = path.read_bytes()
    if len(raw) > MAX_INDEX_BYTES:
        raise ValueError('bundle index exceeds the 1 MiB index bound')
    value = json.loads(raw, object_pairs_hook=_unique_object)
    _keys(value, ('schema_version', 'kind', 'project_id', 'fixture', 'archive', 'parts'), 'bundle index')
    if type(value['schema_version']) is not int or value['schema_version'] != 1 or value['kind'] != 'hatch-production-bundle':
        raise ValueError('unsupported production bundle schema or kind')
    if not isinstance(value['project_id'], str) or not value['project_id'] or type(value['fixture']) is not bool:
        raise ValueError('bundle must retain an explicit project identity and fixture label')
    archive = value['archive']
    _keys(archive, ('format', 'sha256', 'bytes'), 'bundled archive')
    if archive['format'] != 'zip':
        raise ValueError('bundle transport must reconstruct a production ZIP archive')
    _digest(archive['sha256'], 'archive.sha256')
    if type(archive['bytes']) is not int or not 0 < archive['bytes'] <= MAX_BUNDLE_BYTES:
        raise ValueError('bundle archive exceeds the 1 GiB transport bound')
    parts = value['parts']
    if not isinstance(parts, list) or not 1 <= len(parts) <= MAX_BUNDLE_PARTS:
        raise ValueError('bundle needs between 1 and 512 ordered parts')
    seen, total = set(), 0
    for part in parts:
        _keys(part, ('path', 'bytes', 'sha256'), 'bundle part')
        relative = part['path']
        source = workflow.safe_path(path.parent, relative)
        if relative != PurePosixPath(relative).as_posix() or relative in seen or source == path:
            raise ValueError('bundle part paths must be canonical, distinct and separate from the index')
        seen.add(relative)
        if type(part['bytes']) is not int or not 0 < part['bytes'] <= MAX_PART_BYTES:
            raise ValueError('bundle part exceeds the 24 MiB per-part bound')
        _digest(part['sha256'], 'part.sha256')
        total += part['bytes']
    if total != archive['bytes'] or total > MAX_BUNDLE_BYTES:
        raise ValueError('ordered bundle part sizes do not match the bounded archive size')
    return path, value, hashlib.sha256(raw).hexdigest()


@contextmanager
def _assembled_archive(bundle_index):
    index_path, index, index_sha256 = _load_index(bundle_index)
    with tempfile.TemporaryDirectory(prefix='hatch-production-bundle-') as temporary:
        archive_path = Path(temporary) / 'project.zip'
        archive_digest = hashlib.sha256()
        with archive_path.open('xb') as output:
            for part in index['parts']:
                source = workflow.safe_path(index_path.parent, part['path'])
                if not source.is_file():
                    raise ValueError('missing bundle part: ' + part['path'])
                if source.stat().st_size != part['bytes']:
                    raise ValueError('bundle part size differs from its receipt: ' + part['path'])
                digest, count = hashlib.sha256(), 0
                with source.open('rb') as stream:
                    for block in iter(lambda: stream.read(BLOCK_BYTES), b''):
                        count += len(block)
                        if count > part['bytes']:
                            raise ValueError('bundle part grew beyond its declared bound: ' + part['path'])
                        digest.update(block)
                        archive_digest.update(block)
                        output.write(block)
                if count != part['bytes'] or digest.hexdigest() != part['sha256']:
                    raise ValueError('bundle part hash differs from its receipt: ' + part['path'])
        if archive_path.stat().st_size != index['archive']['bytes'] or archive_digest.hexdigest() != index['archive']['sha256']:
            raise ValueError('assembled archive size or hash differs; preserve the original ordered parts')
        receipt = workflow.verify_project_archive(archive_path)
        if receipt['project_id'] != index['project_id'] or receipt['fixture'] is not index['fixture']:
            raise ValueError('bundle identity or fixture label differs from its verified archive')
        yield archive_path, index_path, index, index_sha256, receipt


def verify_bundle(bundle_index):
    with _assembled_archive(bundle_index) as (_, path, index, digest, receipt):
        return {'verified': True, 'bundle': str(path), 'bundle_sha256': digest,
                'project_id': receipt['project_id'], 'fixture': receipt['fixture'],
                'archive_sha256': index['archive']['sha256'], 'archive_bytes': index['archive']['bytes'],
                'part_count': len(index['parts']), 'file_count': len(receipt['files']),
                'visual_review_performed': False, 'external_integration_verified': False}


def create_bundle(archive_path, destination, *, part_size=MAX_PART_BYTES):
    from production_sources import _new_destination, _publish_stage
    if type(part_size) is not int or not 1 <= part_size <= MAX_PART_BYTES:
        raise ValueError('part_size must be a positive integer no larger than 24 MiB')
    archive_path, destination = Path(archive_path).resolve(), _new_destination(destination)
    if not archive_path.is_file() or not 0 < archive_path.stat().st_size <= MAX_BUNDLE_BYTES:
        raise ValueError('source archive is missing or exceeds the 1 GiB transport bound')
    expected_size = archive_path.stat().st_size
    if (expected_size + part_size - 1) // part_size > MAX_BUNDLE_PARTS:
        raise ValueError('chosen part_size would exceed the 512-part bound')
    receipt = workflow.verify_project_archive(archive_path)
    source_sha256 = workflow.file_hash(archive_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix='.hatch-production-parts-', dir=destination.parent))
    try:
        parts, copied = [], 0
        with archive_path.open('rb') as stream:
            while block := stream.read(part_size):
                copied += len(block)
                if copied > expected_size or len(parts) >= MAX_BUNDLE_PARTS:
                    raise ValueError('source archive changed or exceeded its verified transport bound')
                relative = f'project.zip.part-{len(parts) + 1:04d}'
                (stage / relative).write_bytes(block)
                parts.append({'path': relative, 'bytes': len(block), 'sha256': hashlib.sha256(block).hexdigest()})
        index = {'schema_version': 1, 'kind': 'hatch-production-bundle',
                 'project_id': receipt['project_id'], 'fixture': receipt['fixture'],
                 'archive': {'format': 'zip', 'sha256': source_sha256, 'bytes': expected_size}, 'parts': parts}
        (stage / BUNDLE_INDEX).write_text(json.dumps(index, sort_keys=True, indent=2) + '\n', encoding='utf-8')
        result = verify_bundle(stage)
        _publish_stage(stage, destination)
    finally:
        if stage.exists():
            shutil.rmtree(stage)
    return {**result, 'bundle': str(destination / BUNDLE_INDEX), 'created': True}


def restore_bundle(bundle_index, destination):
    destination = Path(destination).resolve()
    if destination.exists():
        raise ValueError('restore destination must not exist; use a new directory')
    with _assembled_archive(bundle_index) as (archive, path, index, digest, receipt):
        result = workflow.restore_project(archive, destination)
        return {**result, 'bundle': str(path), 'bundle_sha256': digest,
                'archive_sha256': index['archive']['sha256'], 'verified_part_count': len(index['parts'])}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    create = commands.add_parser('create')
    create.add_argument('--archive', required=True)
    create.add_argument('--destination', required=True)
    create.add_argument('--part-mib', type=int, default=24)
    verify = commands.add_parser('verify')
    verify.add_argument('--bundle', required=True)
    restore = commands.add_parser('restore')
    restore.add_argument('--bundle', required=True)
    restore.add_argument('--destination', required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == 'create':
            result = create_bundle(args.archive, args.destination, part_size=args.part_mib * 1024 * 1024)
        elif args.command == 'verify':
            result = verify_bundle(args.bundle)
        else:
            result = restore_bundle(args.bundle, args.destination)
        print(json.dumps(result, sort_keys=True, indent=2))
        return 0
    except (ValueError, OSError, KeyError, TypeError) as exc:
        print(json.dumps({'error': str(exc), 'command': args.command, 'provider_called': False}), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())

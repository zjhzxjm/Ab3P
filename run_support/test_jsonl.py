"""Run only on ai-0; compare complete driver records to an independent native API probe."""
import argparse
import collections
import hashlib
import json
import os
from pathlib import Path
import subprocess


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_response(data, count):
    rows = [json.loads(line) for line in data.decode('utf-8').splitlines()]
    if len(rows) != count:
        raise ValueError('Incomplete response')
    for i, row in enumerate(rows):
        if row.get('schema_version') != 1 or row.get('line_index') != i or not isinstance(row.get('records'), list):
            raise ValueError('Invalid response')
    return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--build-root', required=True)
    parser.add_argument('--run-root', required=True)
    parser.add_argument('--baseline-root', required=True)
    args = parser.parse_args()
    run = Path(args.run_root).resolve()
    allowed = Path('/home/promer/dev/prome_pubtator/.test/runs')
    if allowed not in run.parents or Path(os.environ.get('PROME_TEST_RUN_ROOT', '')).resolve() != run:
        raise RuntimeError('Explicit isolated ai-0 run required')
    build, baseline = Path(args.build_root).resolve(), Path(args.baseline_root).resolve()
    if run not in build.parents or run not in baseline.parents:
        raise RuntimeError('Builds must belong to this run')
    work = run / 'run_support' / 'ab3p-validation'
    work.mkdir(parents=True, exist_ok=False)
    (work / 'path_Ab3P').write_text(str(build / 'WordData') + '/\n')
    report = {'checks': [], 'cases': {}, 'binary_sha256': digest(build / 'identify_abbr_jsonl')}

    def invoke(binary, data, name):
        source = work / (name + '.txt')
        source.write_bytes(data)
        result = subprocess.run([str(binary), str(source)], cwd=work, capture_output=True)
        (work / (name + '.stdout')).write_bytes(result.stdout)
        (work / (name + '.stderr')).write_bytes(result.stderr)
        return result

    fixtures = {
        'definitions': b'Tumor necrosis factor (TNF) and rheumatoid arthritis (RA).\nNo definitions here.\n\n',
        'conflicting': b'Rheumatoid arthritis (RA) was studied. Retinoic acid (RA) was administered.\n',
        'repeated': b'Tumor necrosis factor (TNF). Tumor necrosis factor (TNF).\n',
        'unicode_pipe': 'β-catenin and tumor  necrosis factor (TNF) | α.\n'.encode(),
        'controls_eof': b'Tumor\tnecrosis factor (TNF) and "quoted" words.\nNo definition',
        'empty': b'',
        'long': b'word ' * 10000 + b'tumor necrosis factor (TNF).\n',
        'official': (build / 'MED1250_unlabeled').read_bytes(),
    }
    for name, data in fixtures.items():
        driver = invoke(build / 'identify_abbr_jsonl', data, name)
        assert driver.returncode == 0, (name, driver.returncode)
        count = data.count(b'\n') + int(bool(data) and not data.endswith(b'\n'))
        rows = validate_response(driver.stdout, count)
        probe = invoke(build / 'native_probe', data, name + '-native')
        assert probe.returncode == 0, (name, probe.returncode)
        expected = []
        for line in probe.stdout.decode().splitlines():
            if line.startswith('ROW '):
                assert int(line[4:]) == len(expected)
                expected.append([])
            else:
                sf, lf, strategy, quality, so, lo = line.split('\t')
                expected[-1].append({'sf': bytes.fromhex(sf).decode(), 'lf': bytes.fromhex(lf).decode(),
                    'strategy': bytes.fromhex(strategy).decode(), 'pseudo_precision': float(quality),
                    'tool_sf_byte_offset': int(so), 'tool_lf_byte_offset': int(lo)})
        assert [r['records'] for r in rows] == expected, name
        report['cases'][name] = {'lines': count, 'records': sum(len(r['records']) for r in rows)}
        if name in ('definitions', 'repeated', 'conflicting'):
            assert any(r['records'] for r in rows), name
        if name == 'conflicting':
            pairs = {(r['sf'], r['lf']) for row in rows for r in row['records'] if r['sf'] == 'RA'}
            assert len(pairs) >= 2, pairs
        if name == 'repeated':
            pairs = [(r['sf'], r['lf']) for row in rows for r in row['records']]
            assert len(pairs) > len(set(pairs)), pairs
        if name == 'definitions':
            assert rows[1]['records'] == rows[2]['records'] == []
    for name, data in [('nul-before', b'\0Tumor necrosis factor (TNF).\n'),
                       ('nul-conflict', b'Rheumatoid arthritis (RA).\0Retinoic acid (RA).\n')]:
        result = invoke(build / 'identify_abbr_jsonl', data, name)
        assert result.returncode != 0 and result.stdout == b'', name
    missing = subprocess.run([str(build / 'identify_abbr_jsonl'), str(work / 'absent')], cwd=work, capture_output=True)
    assert missing.returncode != 0
    for malformed, count in [(b'', 1), (b'{}\n', 1), (b'{bad}\n', 1)]:
        try:
            validate_response(malformed, count)
        except (ValueError, UnicodeError):
            pass
        else:
            raise AssertionError('Invalid response accepted')
    report['checks'] += ['complete_native_record_equality', 'zero_empty_eof', 'conflict_and_duplicate_preservation',
                         'unicode_controls_pipe_long', 'nul_rejected', 'missing_input', 'incomplete_protocol_rejected']
    # Native golden comparison uses each build's own run-local WordData.
    outputs = {}
    for label, root in [('baseline', baseline), ('fixed', build)]:
        cwd = work / label
        cwd.mkdir()
        (cwd / 'path_Ab3P').write_text(str(root / 'WordData') + '/\n')
        result = subprocess.run([str(root / 'identify_abbr'), str(root / 'MED1250_unlabeled')], cwd=cwd, capture_output=True)
        (cwd / 'official.stdout').write_bytes(result.stdout)
        (cwd / 'official.stderr').write_bytes(result.stderr)
        assert result.returncode == 0, label
        outputs[label] = result.stdout
        report[label + '_matches_gold'] = result.stdout == (root / 'identify_abbr-out').read_bytes()
    report['fixed_matches_baseline'] = outputs['baseline'] == outputs['fixed']
    report['status'] = 'passed' if report['fixed_matches_gold'] and report['baseline_matches_gold'] else 'golden_difference_requires_review'
    (run / 'run_support' / 'ab3p-build-validation.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))
    if report['status'] != 'passed':
        raise SystemExit(1)


if __name__ == '__main__':
    main()

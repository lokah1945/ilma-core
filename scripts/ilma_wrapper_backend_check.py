#!/root/.hermes/hermes-agent/venv/bin/python
"""Check ILMA wrapper providers; --live sends only synthetic verification prompts.

Default: configuration, health, and catalog checks (no inference).
Usage: ./ilma_wrapper_backend_check.py [--live] [--provider wrapper-nous]
"""
from __future__ import annotations

import argparse
import contextlib
import io
import json
import logging
import os
from pathlib import Path
import secrets
import sys
from datetime import datetime, timezone

PROFILE = Path(__file__).resolve().parent.parent
WRAPPER = Path('/root/wrapper')
HERMES = Path('/root/.hermes/hermes-agent')
PYTHON = HERMES / 'venv/bin/python'


class CheckFailure(Exception):
    """Only fixed, secret-free diagnostic codes belong in this exception."""


def require(condition, code):
    if not condition:
        raise CheckFailure(code)


def safe_error(exc):
    result = {'type': type(exc).__name__}
    if isinstance(exc, CheckFailure):
        result['code'] = str(exc)
    status = getattr(exc, 'status_code', None)
    if isinstance(status, int):
        result['http_status'] = status
    return result


def live_checks(runtime, model, row, timeout):
    import httpx
    from openai import OpenAI

    # Follow the actual resolved transport and credential. No provider fallback.
    with OpenAI(api_key=runtime['api_key'], base_url=runtime['base_url'],
                max_retries=0, timeout=timeout,
                http_client=httpx.Client(trust_env=False, follow_redirects=False,
                                         timeout=timeout)) as client:
        options = dict(runtime.get('request_overrides') or {})
        options.update(model=model, max_tokens=1024)
        row['stage'] = 'stream'
        text, finished = '', False
        with client.chat.completions.create(
                **options, stream=True,
                messages=[{'role': 'user', 'content':
                           'Reply with exactly CHECK_OK. Do not explain.'}]) as stream:
            for chunk in stream:
                for choice in chunk.choices:
                    text += choice.delta.content or ''
                    finished |= choice.finish_reason == 'stop'
        require(finished and 'CHECK_OK' in text, 'stream_missing_expected_answer')
        row['checks']['stream'] = True

        row['stage'] = 'tool_call'
        nonce = 'ilma_' + secrets.token_hex(8)
        tool = {'type': 'function', 'function': {
            'name': 'echo_nonce', 'description': 'Return the supplied value unchanged.',
            'parameters': {'type': 'object', 'properties': {
                'value': {'type': 'string', 'description': 'Exact value to return'}},
                'required': ['value'], 'additionalProperties': False}}}
        messages = [{'role': 'user', 'content':
                     f'Call echo_nonce once with value "{nonce}". '
                     'After the tool result, reply with only its value.'}]
        response = client.chat.completions.create(
            **options, messages=messages, tools=[tool],
            tool_choice={'type': 'function', 'function': {'name': 'echo_nonce'}})
        require(bool(response.choices), 'tool_response_has_no_choices')
        assistant = response.choices[0].message
        calls = assistant.tool_calls or []
        require(len(calls) == 1, 'expected_one_tool_call')
        call = calls[0]
        require(call.function.name == 'echo_nonce', 'unexpected_tool_name')
        args = json.loads(call.function.arguments)
        require(args == {'value': nonce}, 'tool_arguments_mismatch')
        row['checks']['tool_call'] = True

        row['stage'] = 'tool_result'
        messages.append(assistant.model_dump(exclude_none=True))
        messages.append({'role': 'tool', 'tool_call_id': call.id,
                         'content': json.dumps({'value': args['value']})})
        final = client.chat.completions.create(
            **options, messages=messages, tools=[tool], tool_choice='none')
        require(bool(final.choices), 'tool_result_has_no_choices')
        require(nonce in (final.choices[0].message.content or ''),
                'tool_result_missing_expected_value')
        require(final.choices[0].finish_reason == 'stop', 'tool_result_incomplete')
        row['checks']['tool_roundtrip'] = True


def run(args):
    # Read lifecycle metadata before importing or inspecting wrapper components.
    metadata = json.loads((WRAPPER / 'wrappers.json').read_text())
    sys.path.insert(0, str(WRAPPER))
    from common.wrapper_scope import select_wrappers
    active = select_wrappers(include_registry=False)
    eligible = {f"wrapper-{name.removesuffix('-python')}": name for name in active}
    selected = args.provider or list(eligible)
    require(all(name in eligible for name in selected), 'provider_not_in_active_scope')

    # Set profile before any Hermes imports; only load secrets into this process.
    os.environ['HERMES_HOME'] = str(PROFILE)
    sys.path.insert(0, str(HERMES))
    from dotenv import load_dotenv
    load_dotenv(PROFILE / '.env', override=True)
    from hermes_cli.runtime_provider import resolve_runtime_provider
    import httpx

    report = {'profile': str(PROFILE), 'live': args.live,
              'checked_at': datetime.now(timezone.utc).isoformat(), 'providers': []}
    with httpx.Client(trust_env=False, follow_redirects=False, timeout=10) as http:
        for name in selected:
            row = {'provider': name, 'ok': False, 'checks': {}, 'stage': 'resolve'}
            report['providers'].append(row)
            try:
                runtime = resolve_runtime_provider(requested=name)
                entry = metadata['wrappers'][eligible[name]]
                expected = f"http://127.0.0.1:{entry['port']}/v1"
                base_url = str(runtime.get('base_url') or '').rstrip('/')
                require(base_url == expected, 'resolved_url_mismatch')
                require(runtime.get('api_mode') == 'chat_completions',
                        'resolved_transport_is_not_chat_completions')
                key = runtime.get('api_key')
                require(isinstance(key, str) and len(key.strip()) >= 8 and
                        key.lower() not in {'no-key-required', 'not-needed',
                                            'placeholder', 'dummy-key', 'test-key'} and
                        '${' not in key and key.isascii(), 'missing_or_placeholder_key')
                model = str(runtime.get('model') or '').strip()
                require(bool(model), 'provider_default_model_missing')
                row.update(base_url=base_url, model=model)
                row['checks']['runtime_resolution'] = True

                row['stage'] = 'health'
                response = http.get(base_url.removesuffix('/v1') + '/health')
                response.raise_for_status()
                health = response.json()
                require(health.get('status') == 'ok', 'wrapper_health_not_ok')
                row['checks']['health'] = True

                row['stage'] = 'catalog'
                response = http.get(base_url + '/models')
                response.raise_for_status()
                models = response.json().get('data', [])
                require(any(item.get('id') == model for item in models),
                        'default_model_absent_from_catalog')
                row['checks']['model_in_catalog'] = True
                row['catalog_size'] = len(models)
                if args.live:
                    live_checks(runtime, model, row, args.timeout)
                row['ok'] = True
                row.pop('stage')
            except Exception as exc:
                row['error'] = safe_error(exc)
    report['ok'] = all(row['ok'] for row in report['providers'])
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live', action='store_true',
                        help='Send synthetic streaming and tool requests to configured models')
    parser.add_argument('--provider', action='append',
                        help='Named active provider; repeat to select several (default: all active)')
    parser.add_argument('--timeout', type=float, default=120,
                        help='Live SDK request timeout in seconds (default: 120)')
    parser.add_argument('--output', type=Path, help='Also write the JSON report to this path')
    args = parser.parse_args()
    if Path(sys.prefix) != PYTHON.parent.parent:
        os.execv(str(PYTHON), [str(PYTHON), str(Path(__file__).resolve()), *sys.argv[1:]])
    logging.disable(logging.CRITICAL)
    try:
        require(args.timeout > 0, 'timeout_must_be_positive')
        # Libraries must not emit credential-bearing logs or upstream error bodies.
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            report = run(args)
    except Exception as exc:
        report = {'profile': str(PROFILE), 'live': args.live, 'ok': False,
                  'error': safe_error(exc)}
    output = json.dumps(report, indent=2) + '\n'
    if args.output:
        try:
            args.output.write_text(output)
        except OSError as exc:
            report['ok'] = False
            report['output_error'] = safe_error(exc)
            output = json.dumps(report, indent=2) + '\n'
    print(output, end='')
    return 0 if report['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())

#!/root/.hermes/hermes-agent/venv/bin/python
"""Exercise the real Hermes tool loop with wrapper credentials and a temporary home.

This sends synthetic prompts to the selected provider. No profile memories,
conversation history, MCP servers, plugins, or messaging tools are loaded.
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
import tempfile
import time

PROFILE = Path(__file__).resolve().parent.parent
HERMES = Path('/root/.hermes/hermes-agent')
WRAPPER = Path('/root/wrapper')


def run(provider):
    import yaml
    from dotenv import dotenv_values

    metadata = json.loads((WRAPPER / 'wrappers.json').read_text())
    sys.path.insert(0, str(WRAPPER))
    from common.wrapper_scope import select_wrappers
    eligible = {f"wrapper-{name.removesuffix('-python')}": name
                for name in select_wrappers(include_registry=False)}
    if provider not in eligible:
        raise ValueError('Provider is outside the active wrapper scope')
    original = yaml.safe_load((PROFILE / 'config.yaml').read_text())
    settings = original['providers'][provider]
    model = settings['default_model']
    expected_url = f"http://127.0.0.1:{metadata['wrappers'][eligible[provider]]['port']}/v1"
    if settings['base_url'].rstrip('/') != expected_url:
        raise ValueError('Configured provider URL differs from wrapper metadata')
    key_env = settings['key_env']
    key = dotenv_values(PROFILE / '.env').get(key_env)
    if not key:
        raise ValueError('Profile wrapper credential is missing')

    with tempfile.TemporaryDirectory(prefix='ilma-wrapper-agent-') as tmp:
        home = Path(tmp)
        work = home / 'work'
        work.mkdir()
        nonce = 'ILMA_WRAPPER_' + secrets.token_hex(12)
        fixture = work / 'probe.txt'
        fixture.write_text(nonce + '\n')
        model_config = dict(original['model']) if provider == original['model']['provider'] else {}
        model_config.update(default=model, provider=provider)
        effort = original.get('agent', {}).get('reasoning_effort', 'none')
        config = {
            'model': model_config,
            'providers': {provider: settings},
            'agent': {'api_max_retries': 0, 'reasoning_effort': effort},
            'terminal': {'cwd': str(work)},
            'compression': {'enabled': False},
            'memory': {'enabled': False},
            'curator': {'enabled': False},
        }
        (home / 'config.yaml').write_text(yaml.safe_dump(config))
        os.environ['HERMES_HOME'] = str(home)
        os.environ['TERMINAL_CWD'] = str(work)
        os.environ[key_env] = key
        os.chdir(work)
        sys.path.insert(0, str(HERMES))
        from hermes_cli.runtime_provider import resolve_runtime_provider
        from run_agent import AIAgent
        runtime = resolve_runtime_provider(requested=provider)
        calls = []
        started = time.monotonic()
        agent = AIAgent(
            model=model, provider=runtime['provider'],
            base_url=runtime['base_url'], api_key=runtime['api_key'],
            api_mode=runtime['api_mode'], enabled_toolsets=['file'],
            max_iterations=3, reasoning_config={'effort': effort}, quiet_mode=True,
            skip_context_files=True, skip_memory=True, fallback_model=[],
            tool_complete_callback=lambda call_id, name, args, result: calls.append(name),
        )
        agent.tools = [tool for tool in agent.tools
                       if tool.get('function', {}).get('name') == 'read_file']
        agent.valid_tool_names = {'read_file'}
        try:
            result = agent.run_conversation(
                f'Use read_file to read the local file {fixture}. '
                'Then reply only with the exact contents of that file. '
                'You must call the tool to find the answer.'
            )
            response = result.get('final_response') or ''
            return {
                'passed': 'read_file' in calls and nonce in response,
                'provider': provider, 'base_url': runtime['base_url'], 'model': model,
                'tool_calls': calls, 'nonce_in_final_response': nonce in response,
                'elapsed_s': round(time.monotonic() - started, 2),
                'isolation': 'temporary HERMES_HOME, read_file only, no fallback',
                'reasoning_effort': effort,
            }
        finally:
            agent.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--provider', default='wrapper-nvidia')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    output_path = args.output.resolve() if args.output else None
    logging.disable(logging.CRITICAL)
    try:
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            report = run(args.provider)
    except Exception as exc:
        report = {'passed': False, 'provider': args.provider, 'error_type': type(exc).__name__}
    output = json.dumps(report, indent=2) + '\n'
    if output_path:
        output_path.write_text(output)
    print(output, end='')
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())

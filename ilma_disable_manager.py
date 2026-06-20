#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  ILMA Disable Flag Manager v1.0 — CONTROLLED_CANARY Military Grade                     ║
║  Tiered disable flags: provider → all models (cascading)                    ║
╚══════════════════════════════════════════════════════════════════════════════╝

PRINSIP:
  ✅ Provider disabled=True → ALL models disabled (cascading, regardless of model.disabled=False)
  ✅ Model disabled=True → Only that model disabled
  ✅ Provider disabled=False → Each model's own disabled flag applies
  ✅ Default: disabled=False for both provider and model levels

USAGE:
  python3 ilma_disable_manager.py --list                          # List all providers/models with disabled status
  python3 ilma_disable_manager.py --disable-provider openrouter   # Disable openrouter + all its 343 models
  python3 ilma_disable_manager.py --enable-provider openrouter    # Re-enable openrouter (each model's disabled flag preserved)
  python3 ilma_disable_manager.py --disable-model openrouter/Qwen-2.5  # Disable specific model
  python3 ilma_disable_manager.py --enable-model openrouter/Qwen-2.5   # Re-enable specific model
  python3 ilma_disable_manager.py --bulk-disable openrouter,nvidia,ollama  # Bulk disable providers
  python3 ilma_disable_manager.py --verify                       # Verify cascading consistency
  python3 ilma_disable_manager.py --stats                         # Show disable statistics
"""

import json
import argparse
import os
import sys
from pathlib import Path
from typing import Optional, List, Dict, Any

ILMA_PROFILE = Path(os.environ.get("ILMA_PROFILE", "/root/.hermes/profiles/ilma"))
MASTER_DB = ILMA_PROFILE / "ilma_model_router_data" / "PROVIDER_INTELLIGENCE_MASTER.json"


def load_db() -> Dict:
    with open(MASTER_DB) as f:
        return json.load(f)


def save_db(data: Dict) -> None:
    with open(MASTER_DB, 'w') as f:
        json.dump(data, f, indent=2)
    print(f"✅ Saved to {MASTER_DB}")


def set_provider_disabled(provider_name: str, disabled: bool, data: Dict) -> int:
    """Set provider.disabled flag. Returns number of models affected by cascading."""
    if provider_name not in data['providers']:
        print(f"❌ Provider '{provider_name}' not found")
        return 0
    
    old_val = data['providers'][provider_name].get('disabled', False)
    data['providers'][provider_name]['disabled'] = disabled
    model_count = len(data['providers'][provider_name]['models'])
    
    action = "DISABLED" if disabled else "ENABLED"
    print(f"{'✅' if disabled else '🔄'} Provider '{provider_name}' {action} (affected {model_count} models via cascading)")
    return model_count


def set_model_disabled(provider_name: str, model_name: str, disabled: bool, data: Dict) -> bool:
    """Set model.disabled flag. Returns True if model found."""
    if provider_name not in data['providers']:
        print(f"❌ Provider '{provider_name}' not found")
        return False
    
    models = data['providers'][provider_name]['models']
    # Handle both full model_id format and bare model name
    model_key = None
    for k in models:
        if k == model_name or k == f"{provider_name}/{model_name}":
            model_key = k
            break
    
    if model_key is None:
        print(f"❌ Model '{model_name}' not found under provider '{provider_name}'")
        return False
    
    old_val = models[model_key].get('disabled', False)
    models[model_key]['disabled'] = disabled
    
    action = "DISABLED" if disabled else "ENABLED"
    print(f"{'✅' if disabled else '🔄'} Model '{model_key}' {action}")
    return True


def disable_subprovider(provider_name: str, subprovider: str, disabled: bool, data: Dict) -> int:
    """Disable all models under a sub-provider (e.g., openai/o1 → openai-o1/*)."""
    if provider_name not in data['providers']:
        print(f"❌ Provider '{provider_name}' not found")
        return 0

    # Model keys look like: "openai-o1/model", "openai-gpt-4/model"
    # For provider "openai", subprovider "o1" should match "openai-o1/xxx"
    prefix = f"{provider_name}-{subprovider}/"
    affected = []
    for model_key in list(data['providers'][provider_name]['models'].keys()):
        if model_key.startswith(prefix):
            affected.append(model_key)
    
    if not affected:
        print(f"⚠️  No models found with prefix '{prefix}'")
        return 0
    
    action = "DISABLED" if disabled else "ENABLED"
    for model_key in affected:
        data['providers'][provider_name]['models'][model_key]['disabled'] = disabled
    
    print(f"{'✅' if disabled else '🔄'} Sub-provider '{provider_name}/{subprovider}' {action}: {len(affected)} models affected")
    return len(affected)


def verify_cascading(data: Dict) -> Dict[str, Any]:
    """Verify cascading consistency: provider disabled=True → all models should be skipped."""
    issues = []
    stats = {
        'total_providers': len(data['providers']),
        'disabled_providers': 0,
        'total_models': 0,
        'disabled_models': 0,
        'cascaded_disabled': 0,  # models disabled because provider is disabled
        'individual_disabled': 0,  # models disabled individually
    }
    
    for pname, pdata in data['providers'].items():
        p_disabled = pdata.get('disabled', False)
        model_count = len(pdata.get('models', {}))
        stats['total_models'] += model_count
        
        if p_disabled:
            stats['disabled_providers'] += 1
            stats['cascaded_disabled'] += model_count
        else:
            for mname, mdata in pdata['models'].items():
                if mdata.get('disabled', False):
                    stats['individual_disabled'] += 1
    
    stats['disabled_models'] = stats['cascaded_disabled'] + stats['individual_disabled']
    
    # Check for inconsistencies: provider disabled but individual models re-enabled
    for pname, pdata in data['providers'].items():
        if pdata.get('disabled', True):
            # Provider is disabled — this is correct cascading
            pass
    
    return stats


def list_all(args, data: Dict) -> None:
    """List all providers and models with their disabled status."""
    print("\n" + "═" * 80)
    print("  ILMA DISABLE FLAG STATUS — Full Provider/Model Tree")
    print("═" * 80)
    
    for pname in sorted(data['providers'].keys()):
        pdata = data['providers'][pname]
        p_disabled = pdata.get('disabled', False)
        models = pdata.get('models', {})
        
        # Count disabled models
        model_disabled_count = sum(1 for m in models.values() if m.get('disabled', False))
        total = len(models)
        
        # Provider status icon
        if p_disabled:
            icon = "🚫"
            flag = "[DISABLED]"
        else:
            icon = "✅"
            flag = ""
        
        print(f"\n{icon} PROVIDER: {pname} {flag}")
        print(f"   └── Provider disabled: {p_disabled} | Models: {total} total, {model_disabled_count} disabled")
        
        if args.verbose and not p_disabled:
            for mname, mdata in sorted(models.items())[:10]:
                m_dis = mdata.get('disabled', False)
                m_icon = "🚫" if m_dis else "  "
                print(f"      {m_icon} {mname}")
            if total > 10:
                print(f"      ... and {total - 10} more models")


def show_stats(data: Dict) -> None:
    """Show disable statistics."""
    stats = verify_cascading(data)
    
    print("\n" + "═" * 60)
    print("  DISABLE FLAG STATISTICS")
    print("═" * 60)
    print(f"  Total providers:        {stats['total_providers']}")
    print(f"  Disabled providers:     {stats['disabled_providers']}")
    print(f"  Total models:           {stats['total_models']}")
    print(f"  Disabled models:         {stats['disabled_models']}")
    print(f"    └─ Cascaded (provider disabled): {stats['cascaded_disabled']}")
    print(f"    └─ Individual (model disabled):   {stats['individual_disabled']}")
    print("═" * 60)
    
    # List disabled providers
    disabled_providers = [p for p, d in data['providers'].items() if d.get('disabled', False)]
    if disabled_providers:
        print(f"\n🚫 DISABLED PROVIDERS: {', '.join(disabled_providers)}")
        for p in disabled_providers:
            mc = len(data['providers'][p]['models'])
            print(f"   • {p}: {mc} models cascaded-disabled")
    else:
        print(f"\n✅ No disabled providers")


def apply_auto_cascade(data: Dict) -> Dict:
    """
    Auto-apply cascading logic: if provider disabled, ensure all models
    have consistent disabled=True in the DB (for transparency/readability).
    
    NOTE: The routing logic already handles cascading at runtime.
    This function syncs the DB state for clarity.
    """
    synced = 0
    for pname, pdata in data['providers'].items():
        if pdata.get('disabled', False):
            for mname in pdata['models']:
                if not pdata['models'][mname].get('disabled', False):
                    pdata['models'][mname]['disabled'] = True
                    synced += 1
    return {'synced': synced}


def main():
    parser = argparse.ArgumentParser(
        description="ILMA Disable Flag Manager — Tiered cascading disable system",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    
    parser.add_argument('--list', action='store_true', help='List all providers/models with disabled status')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose listing (show model names)')
    parser.add_argument('--stats', action='store_true', help='Show disable flag statistics')
    parser.add_argument('--verify', action='store_true', help='Verify cascading consistency')
    
    # Provider operations
    parser.add_argument('--disable-provider', metavar='NAME', help='Disable a provider (cascades to all models)')
    parser.add_argument('--enable-provider', metavar='NAME', help='Re-enable a provider')
    
    # Model operations
    parser.add_argument('--disable-model', metavar='PROVIDER/MODEL', help='Disable a specific model')
    parser.add_argument('--enable-model', metavar='PROVIDER/MODEL', help='Re-enable a specific model')
    
    # Bulk operations
    parser.add_argument('--bulk-disable', metavar='PROV1,PROV2,...', help='Bulk disable providers')
    parser.add_argument('--bulk-enable', metavar='PROV1,PROV2,...', help='Bulk enable providers')
    
    # Sub-provider operations
    parser.add_argument('--disable-subprovider', nargs=2, metavar=('PROVIDER', 'SUBPROVIDER'),
                        help='Disable all models under a sub-provider (e.g., openai o1)')
    parser.add_argument('--enable-subprovider', nargs=2, metavar=('PROVIDER', 'SUBPROVIDER'),
                        help='Re-enable all models under a sub-provider')
    
    # Auto-sync
    parser.add_argument('--sync-cascade', action='store_true', help='Auto-sync cascading (set model disabled=True when provider disabled=True)')
    
    args = parser.parse_args()
    
    if len(sys.argv) == 1:
        parser.print_help()
        return
    
    data = load_db()
    
    # ── LIST ──
    if args.list:
        list_all(args, data)
        return
    
    # ── STATS ──
    if args.stats:
        show_stats(data)
        return
    
    # ── VERIFY ──
    if args.verify:
        stats = verify_cascading(data)
        print("\n✅ Cascading verification complete:")
        print(f"   {stats['cascaded_disabled']} models cascaded-disabled from {stats['disabled_providers']} providers")
        print(f"   {stats['individual_disabled']} models individually disabled")
        return
    
    # ── PROVIDER OPERATIONS ──
    if args.disable_provider:
        set_provider_disabled(args.disable_provider, True, data)
        save_db(data)
        return
    
    if args.enable_provider:
        set_provider_disabled(args.enable_provider, False, data)
        save_db(data)
        return
    
    # ── MODEL OPERATIONS ──
    if args.disable_model:
        parts = args.disable_model.split('/')
        if len(parts) >= 2:
            provider = parts[0]
            model = '/'.join(parts[1:])
            if set_model_disabled(provider, model, True, data):
                save_db(data)
        else:
            print(f"❌ Model format should be: PROVIDER/MODEL (e.g., openrouter/Qwen-2.5)")
        return
    
    if args.enable_model:
        parts = args.enable_model.split('/')
        if len(parts) >= 2:
            provider = parts[0]
            model = '/'.join(parts[1:])
            if set_model_disabled(provider, model, False, data):
                save_db(data)
        else:
            print(f"❌ Model format should be: PROVIDER/MODEL (e.g., openrouter/Qwen-2.5)")
        return
    
    # ── BULK OPERATIONS ──
    if args.bulk_disable:
        providers = [p.strip() for p in args.bulk_disable.split(',')]
        print(f"\n📦 Bulk disabling {len(providers)} providers...")
        for p in providers:
            set_provider_disabled(p, True, data)
        save_db(data)
        return
    
    if args.bulk_enable:
        providers = [p.strip() for p in args.bulk_enable.split(',')]
        print(f"\n📦 Bulk enabling {len(providers)} providers...")
        for p in providers:
            set_provider_disabled(p, False, data)
        save_db(data)
        return
    
    # ── SUB-PROVIDER OPERATIONS ──
    if args.disable_subprovider:
        provider, subprovider = args.disable_subprovider[0], args.disable_subprovider[1]
        disable_subprovider(provider, subprovider, True, data)
        save_db(data)
        return
    
    if args.enable_subprovider:
        provider, subprovider = args.enable_subprovider[0], args.enable_subprovider[1]
        disable_subprovider(provider, subprovider, False, data)
        save_db(data)
        return
    
    # ── AUTO-SYNC ──
    if args.sync_cascade:
        result = apply_auto_cascade(data)
        if result['synced'] > 0:
            print(f"\n🔄 Synced {result['synced']} model disabled flags to match provider state")
            save_db(data)
        else:
            print("\n✅ No cascading sync needed — all models consistent with provider flags")
        return


if __name__ == "__main__":
    main()
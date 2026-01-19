#!/usr/bin/env python3
"""CLI helper to inspect RadioReference WSDL and optionally call a method.

Usage:
  python scripts/rr_wsdl_inspect.py --list
  python scripts/rr_wsdl_inspect.py --op GetRepeatersByCTID --params '{"ctid":606}' --key ENV_OR_PASS

This script uses the rr_api module's inspect_wsdl and call_soap_method helpers.
"""
import json
import os
import argparse

from rr_api import inspect_wsdl, call_soap_method

WSLD_URL = 'http://api.radioreference.com/soap2/?wsdl&v=latest'


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--wsdl', default=WSLD_URL)
    p.add_argument('--list', action='store_true')
    p.add_argument('--op', help='Operation name to call')
    p.add_argument('--params', help='JSON object of params for the operation')
    p.add_argument('--key', help='API key (or read RR_API_PASS env var for passphrase)')
    args = p.parse_args()

    ops = inspect_wsdl(args.wsdl)
    if args.list:
        for k, v in sorted(ops.items()):
            print(k)
            print('  input:', v.get('input'))
            print('  output:', v.get('output'))
            print('')
        return

    if args.op:
        if args.op not in ops:
            print('Operation not found. Use --list to see available operations')
            return
        params = {}
        if args.params:
            params = json.loads(args.params)
        key = args.key or os.environ.get('RR_API_KEY') or os.environ.get('RR_API_PASS')
        if not key:
            print('API key required; pass --key or set RR_API_KEY/RR_API_PASS env var')
            return
        print('Calling', args.op, 'with', params)
        resp = call_soap_method(key, args.op, **params)
        try:
            print(json.dumps(resp, default=lambda o: o.__dict__, indent=2))
        except Exception:
            print(resp)

if __name__ == '__main__':
    main()
